# SurveyClaw

## What This Is

SurveyClaw is a **fully autonomous academic survey pipeline**. Given a research topic, it automatically completes literature search, screening, knowledge extraction, taxonomy construction, survey writing, peer review simulation, and final export — all through a 16-stage state machine driven by LLM calls.

## Quick Start

```bash
# 1. Copy and edit config
cp config.surveyclaw.example.yaml config.yaml
# Fill in your LLM API key and base URL

# 2. Install
pip install -e .

# 3. Run
surveyclaw review --topic "Your survey topic" --auto-approve
```

Or programmatically:

```python
from surveyclaw.pipeline.runner import execute_pipeline
from surveyclaw.config import RCConfig
from surveyclaw.adapters import AdapterBundle
from pathlib import Path

config = RCConfig.load("config.yaml", check_paths=False)
results = execute_pipeline(
    run_dir=Path("artifacts/my-run"),
    run_id="test-001",
    config=config,
    adapters=AdapterBundle(),
    auto_approve_gates=True,
)
```

## Project Structure

```
surveyclaw/
├── __init__.py              # Version (0.3.2)
├── config.py                # RCConfig dataclass, validation, YAML loading
├── adapters.py              # AdapterBundle (recording stubs for notifications, OpenClaw bridge)
├── cli.py                   # CLI: `surveyclaw review` and `surveyclaw validate`
├── prompts.py               # PromptManager: 16-stage survey prompt templates
├── pipeline/
│   ├── stages.py            # 16-stage IntEnum, transitions, gate logic, rollback rules
│   ├── contracts.py         # StageContract for each stage (input/output files, DoD)
│   ├── executor.py          # 16 stage executor functions + dispatch table (_STAGE_EXECUTORS)
│   └── runner.py            # execute_pipeline(), execute_iterative_pipeline()
├── llm/
│   └── client.py            # LLMClient (OpenAI-compatible), from_rc_config() factory
├── assessor/
│   └── rubrics.py           # Survey quality rubrics (coverage, depth, taxonomy, clarity, citations)
└── knowledge/
    └── base.py              # KnowledgeBase (markdown file write, stage category map)
```

## 16-Stage Survey Pipeline

```
Phase A: Survey Scoping
  1: TOPIC_INIT           — Define survey scope, SMART goal, inclusion/exclusion criteria
  2: PROBLEM_DECOMPOSE    — Decompose into survey themes and search questions

Phase B: Literature Discovery
  3: SEARCH_STRATEGY      — Search strategy + data source verification
  4: LITERATURE_COLLECT   — Execute search, collect candidate papers
  5: LITERATURE_SCREEN    — Relevance + quality screening [GATE]
  6: KNOWLEDGE_EXTRACT    — Structured knowledge card extraction per paper

Phase C: Survey Synthesis
  7: SYNTHESIS            — Thematic clustering + cross-paper insights + gap analysis
  8: TAXONOMY_BUILD       — Formal taxonomy construction with paper classification

Phase D: Paper Writing
  9:  PAPER_OUTLINE       — Generate survey paper outline with section goals
  10: PAPER_DRAFT         — Write full survey draft (8,000-15,000 words)
  11: PEER_REVIEW         — Simulated peer review (coverage, depth, taxonomy, citations)
  12: PAPER_REVISION      — Revise based on review feedback

Phase E: Finalization
  13: QUALITY_GATE        — Automated quality scoring against survey rubric [GATE]
  14: KNOWLEDGE_ARCHIVE   — Archive survey retrospective and methodology notes
  15: EXPORT_PUBLISH      — LaTeX conversion, BibTeX, PDF compilation
  16: CITATION_VERIFY     — Cross-check all citations against real APIs
```

## Gate Stages

Stages 5 and 13 are **gate stages** requiring approval (or `--auto-approve`):
- Stage 5 (LITERATURE_SCREEN): reject → rollback to Stage 4
- Stage 13 (QUALITY_GATE): reject → rollback to Stage 9

## Configuration

Config file: `config.yaml` (or `config.surveyclaw.example.yaml` as template).

Key sections:
- `project.name` / `project.mode` — Project identity (`survey`)
- `research.topic` — The survey topic
- `llm.base_url` / `llm.api_key` / `llm.primary_model` — LLM provider (Ollama or OpenAI-compatible)
- `security.hitl_required_stages` — Gate stage numbers (default: [5, 13])
- `knowledge_base.root` — Directory for knowledge base files
- `prompts.custom_file` — Optional path to custom prompt overrides (see `prompts.default.yaml`)

## Important Constraints

- **Python 3.11+** required
- **Dependencies**: `pyyaml`, `rich`, `matplotlib` (for visualization)
- **LLM**: Any OpenAI-compatible API; Ollama (local) supported natively (tested with `qwen3.5:35b`)
- No code execution — SurveyClaw is a pure survey pipeline with no experiment or code-gen stages

## Testing

```bash
# Run all unit tests (2400+ tests)
python -m pytest tests/test_rc_*.py -q --tb=short

# Run real LLM E2E test (requires API key in config)
python tests/e2e_real_llm.py

# Validate config
surveyclaw validate --config config.yaml
```

## Key APIs

```python
# Main pipeline entry
from surveyclaw.pipeline.runner import execute_pipeline, execute_iterative_pipeline

# Single stage execution
from surveyclaw.pipeline.executor import execute_stage

# Prompt management (customize survey prompts)
from surveyclaw.prompts import PromptManager

# Survey quality rubrics
from surveyclaw.assessor.rubrics import RUBRICS

# Config loading
from surveyclaw.config import RCConfig, load_config
```
