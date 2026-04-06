# SurveyClaw — Literature Review Agent Configuration

## Overview

SurveyClaw is a specialized, autonomous agent designed to generate high-quality, conference-grade Survey Papers and Literature Reviews. By default, it is **Ollama-native**, optimized for running large language models (like `qwen3.5:35b`) locally to ensure zero API costs and absolute data privacy. It intelligently skips empirical experiment stages to focus entirely on literature search, taxonomy generation, and structural analysis.

## Agent Role: Literature Review Orchestrator

You are an AI research assistant operating SurveyClaw. Your job is to:

1. **Understand the user's research topic** — clarify the domain and specific area for the review.
2. **Execute the survey pipeline** — run `surveyclaw review --topic "Topic"` to generate the paper.
3. **Ensure strict quality** — SurveyClaw inherently filters for top-tier CS/AI conferences/journals (e.g., NeurIPS, ICLR, ICML, CVPR) and verifies reputable affiliations for arXiv preprints.
4. **Local inference specialist** — leverage local Ollama models (e.g., Qwen, Llama) for all extraction and synthesis tasks.

## Quick Setup

```bash
# Install
pip install -e .

# Configure for Local Ollama (default)
cp config.surveyclaw.example.yaml config.yaml
# Ensure Ollama is running and the model is pulled: 'ollama pull qwen3.5:35b'

# Run an autonomous literature review survey
surveyclaw review --topic "Large Language Models for Code Generation"
```

## Survey Pipeline Stages

SurveyClaw uses a streamlined 16-stage pipeline:

| Phase | Stages | Description |
|-------|--------|-------------|
| A: Research Scoping | 1-2 | Define survey scope and structure |
| B: Literature Discovery | 3-6 | Search, collect top-tier papers, strict screening |
| C: Survey Synthesis | 7-8 | Cluster topics, generate taxonomies |
| D: Paper Writing | 9-12 | Outline, draft Survey Paper (Taxonomy, Analysis, Future Work) |
| E: Finalization | 13-16 | Quality review, export, LaTeX generation |

## Integration Platforms

SurveyClaw is designed to be easily invoked by orchestrating agents:
- **OpenClaw**: Use `surveyclaw review` as a primary tool for "literature review" or "survey paper" requests.
- **Claude Code**: Direct CLI usage via standard bash tools.
- **Standalone**: Direct CLI usage.
