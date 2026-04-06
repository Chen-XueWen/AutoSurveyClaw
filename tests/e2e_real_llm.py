#!/usr/bin/env python3
"""Real E2E test: run all 16 stages with actual LLM API calls.

Usage:
    .venv_arc/bin/python3 tests/e2e_real_llm.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import yaml

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from surveyclaw.config import RCConfig
from surveyclaw.adapters import AdapterBundle
from surveyclaw.llm.client import LLMClient
from surveyclaw.pipeline.stages import Stage, STAGE_SEQUENCE
from surveyclaw.pipeline.executor import execute_stage, StageResult
from surveyclaw.pipeline.runner import execute_pipeline


def main() -> None:
    # --- Load config ---
    config_path = Path("config.surveyclaw.example.yaml")
    if not config_path.exists():
        print("ERROR: config.surveyclaw.example.yaml not found")
        sys.exit(1)

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    # Override for test
    raw["research"]["topic"] = "Neurosymbolic AI"
    # Ensure Ollama LLM is correctly configured
    if "llm" not in raw:
        raw["llm"] = {}
    raw["llm"]["provider"] = "ollama"
    raw["llm"]["primary_model"] = "qwen3.5:35b"
    raw["llm"]["embedding_model"] = "qwen3-embedding:4b"  # Local Ollama embedding

    config = RCConfig.from_dict(raw, check_paths=False)
    adapters = AdapterBundle()

    # --- Create run directory ---
    run_dir = Path("artifacts/e2e-real-llm-run")
    run_dir.mkdir(parents=True, exist_ok=True)
    run_id = f"e2e-real-{int(time.time())}"

    print(f"=" * 70)
    print(f"SurveyClaw E2E Test — Real LLM API")
    print(f"Topic: {config.research.topic}")
    print(f"Run ID: {run_id}")
    print(f"Output: {run_dir}")
    print(f"=" * 70)

    # --- Run full pipeline ---
    start = time.time()
    results = execute_pipeline(
        run_dir=run_dir,
        run_id=run_id,
        config=config,
        adapters=adapters,
        auto_approve_gates=True,  # Auto-approve all gates for E2E test
        kb_root=run_dir / "kb",
    )
    total_time = time.time() - start

    # --- Report ---
    print(f"\n{'=' * 70}")
    print(f"RESULTS: {len(results)}/16 stages executed in {total_time:.1f}s")
    print(f"{'=' * 70}")

    passed = 0
    failed = 0
    for r in results:
        status_icon = "✅" if r.status.value == "done" else "❌"
        print(
            f"  {status_icon} Stage {int(r.stage):02d} {r.stage.name}: {r.status.value} | artifacts: {r.artifacts}"
        )
        if r.status.value == "done":
            passed += 1
        else:
            failed += 1

    print(f"\n{'=' * 70}")
    print(f"SUMMARY: {passed} passed, {failed} failed, {total_time:.1f}s total")
    print(f"{'=' * 70}")

    # --- Validate key artifacts ---
    checks = [
        ("Stage 1 goal.md", "stage-01/goal.md"),
        ("Stage 10 paper_draft.md", "stage-10/paper_draft.md"),
        ("Stage 15 export files", "stage-15"),
    ]
    print("\nArtifact Checks:")
    for label, path in checks:
        full = run_dir / path
        exists = full.exists()
        if full.is_file():
            size = full.stat().st_size
            print(f"  {'✅' if exists else '❌'} {label}: {size} bytes")
        elif full.is_dir():
            count = len(list(full.iterdir())) if exists else 0
            print(f"  {'✅' if exists else '❌'} {label}: {count} items")
        else:
            print(f"  {'❌'} {label}: NOT FOUND")

    # --- Check paper draft has real data (not placeholder) ---
    draft_path = run_dir / "stage-10" / "paper_draft.md"
    if draft_path.exists():
        draft = draft_path.read_text()
        has_template = draft.count("Template") > 3
        print(
            f"  📝 Paper draft: {len(draft)} chars, template={has_template}"
        )

    # Final verdict
    # Total stages = 16
    if passed >= 16 and failed == 0:
        print(f"\n🎉 ALL 16 STAGES PASSED!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {failed} stages did not pass.")
        sys.exit(1)


if __name__ == "__main__":
    main()
