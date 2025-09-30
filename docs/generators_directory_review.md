# Legacy Generators Cleanup

_Last updated: 2025-09-30_

> Snapshot of the legacy `generators/` package, why it was safe to delete, and the path forward for dedicated prompt orchestration modules.

## What changed on 2025-09-30

| Removed path | Notes | Why it was safe |
| --- | --- | --- |
| `generators/framework_generators.py` | Corrupted CRA-oriented templates with duplicated strings and no imports. | No references anywhere in the runtime or tests; `main.py` defines its own `generate_framework_code`. |
| `generators/ai_code_generator.py` | Experimental async CLI wrapper around `AIPromptEngineer`. | Unused class (`AICodeGenerator`) never imported; relied on deprecated prompt engineer. |
| `generators/__init__.py` | Re-exported the two modules above. | Provided no unique functionality once the unused modules were removed. |

## Key findings

1. **Legacy package fully removed** – All unused code under `generators/` is gone; `main.py` now relies solely on its internal implementations.
2. **Prompt ownership remains inline** – The cleanup highlights the need to extract prompt builders from `main.py` into an explicit module (see migration path below).
3. **Static analysis clarity** – Removing the duplicate `generate_framework_code` export eliminates name collisions and simplifies future refactors.

## Recommendations

- **✅ Remove legacy package** – Completed on 2025-09-30; no further action needed.
- **➡️ Extract prompt builders** – ✅ Initial `prompting/` package now exists with builders, runner, and orchestrators; continue migrating remaining prompt flows from `main.py`.
- **➡️ Add contract tests** – Snapshot prompts and parsed outputs to guard future prompt edits.
- **➡️ Re-evaluate fallbacks** – If deterministic templates are still desired, design a new `templates/` module with modern assumptions (Vite-first, Tailwind, etc.) and explicit tests rather than resurrecting the deleted files.

## Suggested migration path

1. Maintain the new `prompting/` package (`prompt_builder.py`, `ai_runner.py`, `orchestrators.py`) as the single source of truth for AI prompt construction.
2. Move the remaining active prompt flows from `main.py` (frame generation, main app generation, dependency reconciliation) into the prompting module and update imports.
3. Introduce lightweight contract tests that feed fixture data into each prompt builder and snapshot the output so future changes are reviewable.
4. Update documentation (this file and `docs/ai_prompt_flow.md`) once the prompt package lands to keep contributors oriented.

Keeping the repo honest about what runs today will make it much easier to reason about “better prompting” without tripping over abandoned experiments.
