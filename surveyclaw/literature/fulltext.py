"""Full-text retrieval for academic papers.

Priority cascade per paper:
  1. Semantic Scholar full-text API (structured, no download needed)
  2. arXiv HTML endpoint (arxiv.org/html/{id}) — clean HTML → plain text
  3. arXiv PDF download + PyMuPDF text extraction (requires [pdf] extra)
  4. Abstract fallback (always succeeds)

Public API
----------
- ``fetch_fulltext(paper)`` → ``(text, source_label)``
- ``split_sections(text)`` → ``list[tuple[str, str]]``  (heading, body)
- ``estimate_tokens(text)`` → ``int``
"""

from __future__ import annotations

import html
import html.parser
import json
import logging
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_S2_PAPER_URL = "https://api.semanticscholar.org/graph/v1/paper/{id}"
_S2_FIELDS = "title,openAccessPdf,tldr,externalIds"
_S2_TIMEOUT = 20
_S2_RATE_DELAY = 1.5  # seconds between S2 calls

_ARXIV_HTML_BASE = "https://arxiv.org/html/{arxiv_id}"
_ARXIV_HTML_TIMEOUT = 30

_PDF_DOWNLOAD_TIMEOUT = 60

# ~1.33 tokens per word for most LLMs
_TOKENS_PER_WORD = 1.33
MAX_SINGLE_PASS_TOKENS = 120_000  # leave headroom in 200k context window

# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


def estimate_tokens(text: str) -> int:
    """Rough token count estimate (word-based)."""
    return int(len(text.split()) * _TOKENS_PER_WORD)


# ---------------------------------------------------------------------------
# HTML → plain text extractor (stdlib only)
# ---------------------------------------------------------------------------


class _HTMLTextExtractor(html.parser.HTMLParser):
    """Extract visible text from HTML, skipping scripts/styles/nav."""

    _SKIP_TAGS = frozenset(
        {"script", "style", "nav", "header", "footer", "aside", "noscript",
         "figure", "figcaption", "table", "meta", "link"}
    )
    _BLOCK_TAGS = frozenset(
        {"p", "div", "section", "h1", "h2", "h3", "h4", "h5", "h6",
         "li", "dd", "dt", "blockquote", "pre", "br"}
    )

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        elif tag in self._BLOCK_TAGS and self._skip_depth == 0:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in self._BLOCK_TAGS and self._skip_depth == 0:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        raw = html.unescape(raw)
        # Collapse excessive whitespace while preserving paragraph breaks
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _html_to_text(html_content: str) -> str:
    """Convert HTML string to plain text."""
    extractor = _HTMLTextExtractor()
    try:
        extractor.feed(html_content)
        return extractor.get_text()
    except Exception:  # noqa: BLE001
        # Fallback: strip all tags with regex
        text = re.sub(r"<[^>]+>", " ", html_content)
        text = html.unescape(text)
        return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Layer 1: Semantic Scholar full-text
# ---------------------------------------------------------------------------

_s2_last_call: float = 0.0


def _fetch_s2_fulltext(paper: dict[str, Any]) -> str | None:
    """Fetch full text via Semantic Scholar paper detail endpoint.

    Returns plain text if available via openAccessPdf, otherwise None.
    The S2 API returns a PDF URL for open-access papers; we then fetch
    the arXiv HTML equivalent when possible rather than downloading the PDF.
    """
    global _s2_last_call  # noqa: PLW0603

    # Rate limiting
    elapsed = time.monotonic() - _s2_last_call
    if elapsed < _S2_RATE_DELAY:
        time.sleep(_S2_RATE_DELAY - elapsed)
    _s2_last_call = time.monotonic()

    # Determine S2 paper ID
    paper_id = str(paper.get("paper_id", ""))
    arxiv_id = str(paper.get("arxiv_id", ""))
    s2_id = ""

    if paper_id.startswith("s2-"):
        s2_id = paper_id[3:]
    elif arxiv_id:
        s2_id = f"ARXIV:{arxiv_id}"

    if not s2_id:
        doi = str(paper.get("doi", "")).strip()
        if doi:
            s2_id = f"DOI:{doi}"

    if not s2_id:
        return None

    url = _S2_PAPER_URL.format(id=s2_id) + f"?fields={_S2_FIELDS}"
    try:
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "SurveyClaw/0.3"},
        )
        with urllib.request.urlopen(req, timeout=_S2_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            logger.debug("S2 paper not found: %s", s2_id)
        else:
            logger.debug("S2 API error %d for %s", exc.code, s2_id)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.debug("S2 fetch failed for %s: %s", s2_id, exc)
        return None

    # S2 returns openAccessPdf with a URL if available
    oa_pdf = data.get("openAccessPdf") or {}
    pdf_url = oa_pdf.get("url", "") if isinstance(oa_pdf, dict) else ""

    if pdf_url:
        # If it's an arXiv PDF, redirect to HTML endpoint (much cleaner)
        m = re.search(r"arxiv\.org/(?:pdf|abs)/([\d.]+)", pdf_url)
        if m:
            html_text = _fetch_arxiv_html(m.group(1))
            if html_text:
                return html_text
        # Non-arXiv open-access PDF: download and extract directly
        text = _fetch_pdf_from_url(pdf_url)
        if text:
            return text

    # If we found this paper by DOI, check externalIds for an arXiv ID
    # so the caller's arXiv HTML/PDF layers can use it
    ext_ids = data.get("externalIds") or {}
    if isinstance(ext_ids, dict) and ext_ids.get("ArXiv"):
        # Store back into the paper dict so fetch_fulltext() can pick it up
        paper["arxiv_id"] = ext_ids["ArXiv"]
        logger.debug("[fulltext] S2 externalIds gave arXiv ID %s", ext_ids["ArXiv"])

    return None


# ---------------------------------------------------------------------------
# Layer 2: arXiv HTML endpoint
# ---------------------------------------------------------------------------


def _fetch_arxiv_html(arxiv_id: str) -> str | None:
    """Fetch paper from arxiv.org/html/{arxiv_id} and return plain text."""
    if not arxiv_id:
        return None

    url = _ARXIV_HTML_BASE.format(arxiv_id=arxiv_id)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "SurveyClaw/0.3 (research pipeline)"},
        )
        with urllib.request.urlopen(req, timeout=_ARXIV_HTML_TIMEOUT) as resp:
            # arXiv HTML returns 200 for papers that have HTML versions
            content_type = resp.headers.get("Content-Type", "")
            if "html" not in content_type.lower():
                return None
            raw_html = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 403):
            logger.debug("arXiv HTML not available for %s (HTTP %d)", arxiv_id, exc.code)
        else:
            logger.debug("arXiv HTML error %d for %s", exc.code, arxiv_id)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.debug("arXiv HTML fetch failed for %s: %s", arxiv_id, exc)
        return None

    text = _html_to_text(raw_html)
    if len(text) < 500:
        logger.debug("arXiv HTML too short for %s (%d chars)", arxiv_id, len(text))
        return None

    logger.info("[fulltext] arXiv HTML: %s (%d chars)", arxiv_id, len(text))
    return text


# ---------------------------------------------------------------------------
# Layer 2b: Generic PDF download via PyMuPDF (for non-arXiv open-access PDFs)
# ---------------------------------------------------------------------------


def _fetch_pdf_from_url(url: str) -> str | None:
    """Download a PDF from any URL and extract text using PyMuPDF."""
    try:
        import fitz  # PyMuPDF — optional
    except ImportError:
        logger.debug("PyMuPDF not installed — skipping PDF download from %s", url[:80])
        return None

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "SurveyClaw/0.3 (research pipeline)"},
        )
        with urllib.request.urlopen(req, timeout=_PDF_DOWNLOAD_TIMEOUT) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "pdf" not in content_type.lower() and not url.lower().endswith(".pdf"):
                logger.debug(
                    "Not a PDF at %s (content-type: %s)", url[:80], content_type
                )
                return None
            pdf_bytes = resp.read()
    except Exception as exc:  # noqa: BLE001
        logger.debug("PDF download failed from %s: %s", url[:80], exc)
        return None

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "paper.pdf"
            pdf_path.write_bytes(pdf_bytes)
            doc = fitz.open(str(pdf_path))
            pages: list[str] = [page.get_text() for page in doc]
            doc.close()
        text = "\n".join(pages)
    except Exception as exc:  # noqa: BLE001
        logger.debug("PyMuPDF extraction failed from %s: %s", url[:80], exc)
        return None

    if len(text) < 500:
        return None

    logger.info("[fulltext] PDF download: %s... (%d chars)", url[:60], len(text))
    return text


# ---------------------------------------------------------------------------
# Layer 3: arXiv PDF via PyMuPDF
# ---------------------------------------------------------------------------


def _fetch_arxiv_pdf(arxiv_id: str) -> str | None:
    """Download arXiv PDF and extract text using PyMuPDF (optional dep)."""
    if not arxiv_id:
        return None

    try:
        import fitz  # PyMuPDF — optional
    except ImportError:
        logger.debug("PyMuPDF not installed — skipping PDF extraction. "
                     "Install with: pip install PyMuPDF")
        return None

    try:
        from surveyclaw.literature.arxiv_client import download_pdf
    except ImportError:
        return None

    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = download_pdf(arxiv_id, dirpath=tmp_dir)
        if pdf_path is None or not Path(pdf_path).exists():
            return None

        try:
            doc = fitz.open(str(pdf_path))
            pages: list[str] = []
            for page in doc:
                pages.append(page.get_text())
            doc.close()
            text = "\n".join(pages)
        except Exception as exc:  # noqa: BLE001
            logger.debug("PyMuPDF extraction failed for %s: %s", arxiv_id, exc)
            return None

    if len(text) < 500:
        return None

    logger.info("[fulltext] arXiv PDF: %s (%d chars)", arxiv_id, len(text))
    return text


# ---------------------------------------------------------------------------
# Public: fetch_fulltext
# ---------------------------------------------------------------------------


def _resolve_arxiv_id(title: str) -> str:
    """Search arXiv by title to find the arXiv ID of a paper.

    Returns the arXiv ID string (e.g. "2012.05876") or "" if not found.
    Most CS/AI papers have arXiv preprints even when indexed via OpenAlex
    or Semantic Scholar with a DOI.
    """
    if not title.strip():
        return ""
    try:
        from surveyclaw.literature.arxiv_client import search_arxiv

        # Use title: field prefix for more precise matching
        query = f'ti:"{title[:120]}"'
        results = search_arxiv(query, limit=3, sort_by="relevance")
        if not results:
            # Retry with keyword-only query (no quotes) — handles titles with
            # special characters that break the quoted search
            plain = re.sub(r'[^a-zA-Z0-9 ]', ' ', title)[:100]
            results = search_arxiv(plain, limit=3, sort_by="relevance")

        if results:
            from surveyclaw.literature.verify import title_similarity
            best = max(results, key=lambda p: title_similarity(title, p.title))
            sim = title_similarity(title, best.title)
            if sim >= 0.70 and best.arxiv_id:
                logger.info(
                    "[fulltext] resolved arXiv ID %s for %r (sim=%.2f)",
                    best.arxiv_id, title[:50], sim,
                )
                return best.arxiv_id
            logger.debug(
                "[fulltext] arXiv title search: best sim=%.2f for %r — skipping",
                sim, title[:50],
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("[fulltext] arXiv title lookup failed for %r: %s", title[:50], exc)
    return ""


def fetch_fulltext(paper: dict[str, Any]) -> tuple[str, str]:
    """Fetch the best available full text for a paper.

    Parameters
    ----------
    paper:
        Paper dict from shortlist.jsonl — must contain at least ``title``
        and ideally ``arxiv_id``, ``paper_id``, and ``abstract``.

    Returns
    -------
    (text, source_label)
        ``source_label`` is one of:
        ``"s2_fulltext"``, ``"arxiv_html"``, ``"arxiv_pdf"``, ``"abstract_only"``
    """
    arxiv_id = str(paper.get("arxiv_id", "")).strip()
    abstract = str(paper.get("abstract", "")).strip()
    title = str(paper.get("title", "Unknown")).strip()

    # Extract arXiv ID from URL if not set directly
    if not arxiv_id:
        url = str(paper.get("url", ""))
        m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", url)
        if m:
            arxiv_id = m.group(1)

    # Layer 1: Semantic Scholar (may redirect to arXiv HTML internally,
    #           and may populate paper["arxiv_id"] via S2 externalIds)
    text = _fetch_s2_fulltext(paper)
    if text:
        return text, "s2_fulltext"

    # Re-read arxiv_id — S2 may have found it via externalIds
    if not arxiv_id:
        arxiv_id = str(paper.get("arxiv_id", "")).strip()

    # Layer 1b: If arxiv_id still missing, search arXiv by title
    # (handles papers from OpenAlex/DOI sources that have arXiv preprints)
    if not arxiv_id:
        arxiv_id = _resolve_arxiv_id(title)

    # Layer 2: arXiv HTML
    if arxiv_id:
        text = _fetch_arxiv_html(arxiv_id)
        if text:
            return text, "arxiv_html"

    # Layer 3: arXiv PDF
    if arxiv_id:
        text = _fetch_arxiv_pdf(arxiv_id)
        if text:
            return text, "arxiv_pdf"

    # Layer 4: Abstract fallback
    logger.warning("[fulltext] abstract_only for: %s", title[:60])
    return abstract or f"No full text available for: {title}", "abstract_only"


# ---------------------------------------------------------------------------
# Section splitting for long papers
# ---------------------------------------------------------------------------

# Heading patterns: Markdown (#) headings, numbered sections, or ALL-CAPS keywords.
# The ALL-CAPS branch only fires on short lines (≤60 chars) that are entirely
# a known section keyword — not on content sentences that happen to start with
# "Results" or "Methods".
_HEADING_RE = re.compile(
    r"^(?:"
    r"#{1,3}\s+.+"                          # Markdown: # Introduction
    r"|(?:\d+\.)+\s+[A-Z].{5,}"             # Numbered: 1.2 Related Work
    r"|(?:ABSTRACT|INTRODUCTION|RELATED WORK|BACKGROUND|"
    r"METHODS?|METHODOLOGY|EXPERIMENTS?|RESULTS?|DISCUSSION|"
    r"CONCLUSIONS?|FUTURE WORK|REFERENCES|APPENDIX|ACKNOWLEDGEMENTS?)"
    r"\s*(?:\d+\.?\d*)?$"                   # ALL-CAPS keyword alone on the line
    r")$",
    re.MULTILINE,                            # no IGNORECASE — keeps prose safe
)


def split_sections(text: str) -> list[tuple[str, str]]:
    """Split paper text into (heading, body) pairs.

    Returns a list of sections. The first element is always
    (\"FULL_TEXT\", text) if no sections are detected (safety fallback).
    """
    matches = list(_HEADING_RE.finditer(text))
    if len(matches) < 3:
        return [("FULL_TEXT", text)]

    sections: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        heading = m.group(0).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections.append((heading, body))

    return sections if sections else [("FULL_TEXT", text)]


def extract_skeleton(text: str) -> str:
    """Extract a ~10k-token skeleton from a long paper.

    Returns: abstract + introduction + all section headings + conclusion.
    Used as context for hierarchical reading.
    """
    sections = split_sections(text)
    parts: list[str] = []
    word_budget = 7_000  # ~10k tokens

    for heading, body in sections:
        h_lower = heading.lower()
        # Always include: abstract, intro, conclusion
        if any(k in h_lower for k in ("abstract", "introduction", "conclusion", "summary")):
            words = body.split()[:2_000]
            parts.append(f"## {heading}\n{' '.join(words)}")
            word_budget -= len(words)
        else:
            # Include heading only (no body)
            parts.append(f"## {heading}")

    return "\n\n".join(parts)
