"""SurveyClaw CLI — literature review agent."""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from surveyclaw.adapters import AdapterBundle
from surveyclaw.config import RCConfig, resolve_config_path
from surveyclaw.pipeline.runner import execute_pipeline
from surveyclaw.pipeline.stages import Stage


def _generate_run_id(topic: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    topic_hash = hashlib.sha256(topic.encode()).hexdigest()[:6]
    return f"survey-{ts}-{topic_hash}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="surveyclaw",
        description="SurveyClaw — Autonomous Survey Paper Generator",
    )
    sub = parser.add_subparsers(dest="command")

    # ── surveyclaw review ──────────────────────────────────────────────────
    review = sub.add_parser("review", help="Run a full literature survey pipeline")
    review.add_argument(
        "--topic", type=str, default=None,
        help="Survey topic (overrides research.topic in config.yaml)",
    )
    review.add_argument(
        "--config", type=str, default=None,
        help="Path to config.yaml (defaults to config.yaml in current directory)",
    )
    review.add_argument(
        "--output", type=str, default=None,
        help="Output directory (defaults to artifacts/<run-id>)",
    )
    review.add_argument(
        "--auto-approve", action="store_true", default=False,
        help="Skip gate approvals at stages 5 and 13",
    )
    review.add_argument(
        "--from-stage", type=str, default=None,
        help="Resume from a specific stage name (e.g. EXPORT_PUBLISH)",
    )

    # ── surveyclaw validate ────────────────────────────────────────────────
    validate = sub.add_parser("validate", help="Validate a config.yaml file")
    validate.add_argument("--config", type=str, default="config.yaml")

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "validate":
        return _cmd_validate(args)

    if args.command == "review" or args.command is None:
        return _cmd_review(args)

    parser.print_help()
    return 1


def _cmd_validate(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        return 1
    try:
        config = RCConfig.load(config_path, check_paths=False)
        print(f"Config valid: {config_path}")
        print(f"  topic:  {config.research.topic}")
        print(f"  model:  {config.llm.primary_model}")
        print(f"  mode:   {config.project.mode}")
        return 0
    except Exception as exc:
        print(f"Config invalid: {exc}", file=sys.stderr)
        return 1


def _cmd_review(args: argparse.Namespace) -> int:
    import dataclasses

    # Load config
    config_arg = getattr(args, "config", None)
    resolved = resolve_config_path(config_arg)
    if resolved is not None and resolved.exists():
        config = RCConfig.load(resolved, check_paths=False)
    else:
        config_path = Path("config.yaml")
        if config_path.exists():
            config = RCConfig.load(config_path, check_paths=False)
        else:
            print("No config.yaml found. Run: cp config.surveyclaw.example.yaml config.yaml", file=sys.stderr)
            return 1

    # Apply CLI overrides
    topic = getattr(args, "topic", None) or config.research.topic
    if not topic:
        print("No topic set. Use --topic or set research.topic in config.yaml", file=sys.stderr)
        return 1

    new_proj = dataclasses.replace(config.project, mode="survey")
    new_res = dataclasses.replace(config.research, topic=topic)
    config = dataclasses.replace(config, project=new_proj, research=new_res)

    auto_approve = getattr(args, "auto_approve", False)

    # Resolve from-stage
    from_stage = Stage.TOPIC_INIT
    from_stage_arg = getattr(args, "from_stage", None)
    if from_stage_arg:
        try:
            from_stage = Stage[from_stage_arg.upper()]
        except KeyError:
            print(f"Unknown stage: {from_stage_arg}", file=sys.stderr)
            return 1

    run_id = _generate_run_id(topic)
    run_dir = Path(getattr(args, "output", None) or f"artifacts/{run_id}")
    run_dir.mkdir(parents=True, exist_ok=True)

    adapters = AdapterBundle()

    print(f"SurveyClaw — Starting literature review")
    print(f"  Topic:   {topic}")
    print(f"  Run ID:  {run_id}")
    print(f"  Output:  {run_dir}")
    print(f"  Gates:   {'auto-approved' if auto_approve else 'require approval'}")

    results = execute_pipeline(
        run_dir=run_dir,
        run_id=run_id,
        config=config,
        adapters=adapters,
        from_stage=from_stage,
        auto_approve_gates=auto_approve,
        stop_on_gate=not auto_approve,
        skip_noncritical=True,
    )

    failed = sum(1 for r in results if r.status.value == "failed")
    done = sum(1 for r in results if r.status.value == "done")

    if failed == 0:
        print(f"\nSurvey complete: {done}/{len(results)} stages done.")
        print(f"Paper: {run_dir}/deliverables/paper_final.md")
        return 0
    else:
        print(f"\nSurvey stopped with {failed} failure(s). Check logs in {run_dir}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
