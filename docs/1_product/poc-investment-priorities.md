# POC Investment Priorities

Status: Living document
Date: 2026-07-04

## Why this exists

An internal AI-tooling knowledge-share with the LearnVia project team (2026-07-01) prompted a review of several testing tools and an orchestration alternative against this project's own architecture (see [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) addendum and [ADR-0021](../decisions/0021-llm-testing-tooling-extensions.md)). That review produced several "if we had more runway, this is what it would buy us" conclusions worth surfacing on their own, separate from the ADRs' technical reasoning, since they're a direct answer to "what's on the horizon for this project" — a question worth revisiting as the POC progresses, not a one-time snapshot.

## Prioritized by expected payoff

Ranked by how much each would likely move the needle on this POC's actual verdict, most to least:

| # | Investment | What it would buy | Rough effort |
|---|---|---|---|
| 1 | Argilla for synthetic learner-persona scenarios | Closes a real false-positive risk: a small hand-curated corpus can make the LLM Decision Services look more viable than they'd hold up against realistic data variety | Medium — new tool to stand up, but the larger cost is the human-authored canonical answers new scenarios need for at least some services |
| 2 | DSPy prompt optimization | Could turn a "promising but not reliable" service verdict into "viable" by iterating prompts against real eval scores instead of hand-tuning | Medium-high — but only pays off *after* a stable DeepEval baseline exists; sequenced behind #1 in practice |
| 3 | Embeddings/re-ranker hybrid for Field Mapping | A second, cheaper, more debuggable path to Field Mapping as a hedge if the pure-LLM approach underperforms — also answers ADR-0005's own open question on hybrid mapping models | High — a second implementation path competing for the same runway as the first |
| 4 | Port one orchestrator seam to LangGraph | Lower long-term maintenance burden and bus-factor risk if this becomes a real product, not just a POC — doesn't change whether the POC itself succeeds | Medium — but the payoff is about total cost of ownership post-POC, not POC-time value |
| 5 | NVIDIA Nemotron guardrails | More accurate content moderation than Bedrock's keyword-based guardrails — only matters if the project ever gets a free-text/chatbot-like surface, which it doesn't have today | Low-medium, but solves a problem this POC likely won't hit |

## How to use this

Each item's full technical reasoning and explicit revisit trigger lives in its ADR ([0011](../decisions/0011-orchestration-runtime-technology.md) for the orchestrator item, [0021](../decisions/0021-llm-testing-tooling-extensions.md) for the rest). This doc exists to keep the prioritized, stakeholder-facing summary in one place as those triggers fire or the team's available runway changes, rather than requiring a re-read of both ADRs to answer "what would more investment buy us right now."
