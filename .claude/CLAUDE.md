@../AGENTS.md

# Claude Code specific

The canonical agent instructions live in [AGENTS.md](../AGENTS.md) (tool-agnostic; imported above). Keep all project guidance there so every coding agent reads the same source — add only Claude Code-specific notes below.

- When the user types `/<skill-name>`, invoke it via the Skill tool (only skills that are actually available).
- If you need the user to run an interactive command themselves (e.g. `gcloud auth login`), suggest they prefix it with `!` in the prompt so its output lands in the session.
