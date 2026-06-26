"""Prompt templates for post-generation code refinement.

A refinement request takes:
- The *existing* generated files (current code on disk)
- The *original* Figma design context (so the AI can re-read intent)
- The *user's natural-language change request*

And returns only the files that need to change.

The flow is:
1. ``build_refinement_prompt(...)`` → ``PromptRequest``
2. AI engine executes the prompt
3. ``parse_refinement_response(...)`` → ``Dict[file_path, new_content]``
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import json

from prompting.prompt_builder import PromptRequest


@dataclass
class RefinementContext:
    """Inputs that shape a refinement prompt."""

    user_prompt: str
    current_files: Dict[str, str]
    target_files: Optional[List[str]] = None
    design_summary: str = ""
    framework: str = ""
    style_engine: str = ""
    component_library: str = ""
    refinement_iteration: int = 1
    previous_summary: str = ""


def _truncate_text(text: str, max_chars: int) -> str:
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [truncated {len(text) - max_chars} chars]"


def _format_files_block(
    current_files: Dict[str, str],
    target_files: Optional[List[str]],
    per_file_chars: int = 4000,
) -> str:
    """Render the ``CURRENT CODE`` block of the prompt.

    Always includes the *entire* project tree, with each file's content
    truncated to keep tokens bounded. If ``target_files`` is set, only
    those are emphasised in the prompt and everything else is summarised.
    """
    if not current_files:
        return "(no files generated yet)"

    focus = set(target_files or [])
    lines: List[str] = ["CURRENT GENERATED FILES:\n"]
    sorted_paths = sorted(current_files.keys())

    for path in sorted_paths:
        content = current_files.get(path, "")
        is_focus = path in focus if focus else True
        marker = "🎯 EDIT TARGET" if is_focus and focus else "  "
        if is_focus or not focus:
            lines.append(f"-- {marker} {path} ({len(content):,} chars) --")
            lines.append(_truncate_text(content, per_file_chars))
            lines.append("")
        else:
            lines.append(f"-- {marker} {path} ({len(content):,} chars) --")
            lines.append("(content omitted — available if needed for context)")

    return "\n".join(lines)


def build_refinement_prompt(ctx: RefinementContext) -> PromptRequest:
    """Construct the prompt that asks the AI to refine generated code."""

    target_label = ""
    if ctx.target_files:
        target_label = (
            f"\n\n🎯 TARGET FILES (focus your changes on these):\n- "
            + "\n- ".join(ctx.target_files)
        )

    files_block = _format_files_block(
        ctx.current_files,
        ctx.target_files,
    )

    style_engine = ctx.style_engine or "(not specified — defaults to plain CSS)"
    component_library = ctx.component_library or "(not specified — raw elements)"

    system_prompt = (
        "You are an expert frontend engineer specialising in iterative code "
        "refinement. The user has already generated code from a Figma design and "
        "now wants to make focused changes. You produce diff-style output — i.e. "
        "return full file contents ONLY for the files you change, NOT the whole "
        "project.\n\n"
        "OUTPUT RULES:\n"
        "1. ALWAYS respond with strict JSON only (no markdown, no commentary).\n"
        "2. Use the exact schema requested by the user prompt.\n"
        "3. Make the smallest feasible change; do NOT rewrite unrelated code.\n"
        "4. Preserve all imports, exports, and routing unless explicitly asked to change them.\n"
        "5. If a requested change is risky or unclear, prefer the safest interpretation "
        "   and explain your choice in the `summary` field.\n"
        "6. Do NOT invent new file paths; only return files that already exist in CURRENT GENERATED FILES.\n"
    )

    user_prompt = f"""REFINE THE GENERATED CODE for framework: {ctx.framework}

=== USER REQUEST (iteration {ctx.refinement_iteration}) ===
"{ctx.user_prompt}"
{target_label}

=== CONTEXT ===
Framework: {ctx.framework}
Style Engine: {style_engine}
Component Library: {component_library}
Previous summary: {ctx.previous_summary or "(no prior refinement)"}

=== DESIGN CONTEXT ===
{_truncate_text(ctx.design_summary, 1500) or "(no design summary available)"}

=== {files_block} ===

=== OUTPUT FORMAT ===
Return a JSON object with EXACTLY this shape:

{{
  "summary": "Plain-text description of what changed and why (1–3 sentences)",
  "updated_files": {{
    "path/to/file1.ext": "FULL NEW FILE CONTENT — not a diff",
    "path/to/file2.ext": "FULL NEW FILE CONTENT — not a diff"
  }},
  "changed_files": ["path/to/file1.ext", "path/to/file2.ext"]
}}

CRITICAL:
- Only include files in `updated_files` if you actually changed them.
- `changed_files` must exactly match the keys of `updated_files`.
- The content must be COMPLETE — the file will be written verbatim.
- Do not include files from the original list that you didn't change.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    debug_context = {
        "refinement_iteration": ctx.refinement_iteration,
        "framework": ctx.framework,
        "target_files": ctx.target_files or "all",
        "file_count": len(ctx.current_files),
        "user_prompt_length": len(ctx.user_prompt),
    }

    return PromptRequest(
        messages=messages,
        temperature=0.25,
        autodecide=False,
        debug_context=debug_context,
    )


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def parse_refinement_response(raw_text: str, valid_paths: Optional[List[str]] = None) -> Dict[str, Any]:
    """Parse the AI's refinement response into structured changes.

    Returns a dict with keys:
    ``updated_files`` — Dict[path, new content]
    ``changed_files`` — List[path]
    ``summary`` — str

    Filters out entries where:
    - The file path isn't in ``valid_paths`` (when provided)
    - The new content is identical to nothing (empty string is allowed)
    - The JSON is malformed (raises ValueError)
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Empty AI response")

    text = raw_text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    # Try direct JSON parse, then fall back to extracting the first JSON block
    parsed: Optional[Dict[str, Any]] = None
    try:
        loaded = json.loads(text)
        if isinstance(loaded, dict):
            parsed = loaded
    except json.JSONDecodeError:
        # Find first '{' and last '}'
        first = text.find("{")
        last = text.rfind("}")
        if first >= 0 and last > first:
            try:
                loaded = json.loads(text[first:last + 1])
                if isinstance(loaded, dict):
                    parsed = loaded
            except json.JSONDecodeError:
                pass

    if parsed is None:
        raise ValueError("Refinement response was not valid JSON")

    summary = str(parsed.get("summary", "") or "").strip()
    updated_files = parsed.get("updated_files") or {}
    changed_files = parsed.get("changed_files") or []

    if not isinstance(updated_files, dict):
        raise ValueError("`updated_files` must be a dict")

    # Coerce keys to str; coerce values to str (skip non-string sneaky entries)
    cleaned_files: Dict[str, str] = {}
    for k, v in updated_files.items():
        if not isinstance(v, str):
            continue
        cleaned_files[str(k)] = v

    # Optional path validation: ignore files the user doesn't know about
    if valid_paths is not None:
        valid_set = set(valid_paths)
        cleaned_files = {k: v for k, v in cleaned_files.items() if k in valid_set}

    # Use cleaned_files keys as authoritative list if `changed_files` is missing
    if not changed_files and isinstance(changed_files, list):
        changed_files = []

    if not isinstance(changed_files, list):
        changed_files = []

    # Normalise changed_files — keep only string entries, drop duplicates
    seen = set()
    cleaned_changed: List[str] = []
    for entry in changed_files:
        if isinstance(entry, str) and entry not in seen:
            seen.add(entry)
            cleaned_changed.append(entry)

    # Make sure changed_files reflects keys in updated_files
    if set(cleaned_changed) != set(cleaned_files.keys()):
        cleaned_changed = sorted(cleaned_files.keys())

    return {
        "summary": summary,
        "updated_files": cleaned_files,
        "changed_files": cleaned_changed,
    }


# ---------------------------------------------------------------------------
# Diff convenience helper
# ---------------------------------------------------------------------------


def render_diff(old_content: str, new_content: str, file_path: str = "") -> str:
    """Render a unified-text diff for two strings.

    Returns an empty string when the contents are identical.
    Otherwise returns a ``Diff:`` block with ``-`` / ``+`` markers per line.

    Only used by the web UI to show the user what the AI changed.
    """
    if old_content == new_content:
        return ""

    lines_old = old_content.splitlines()
    lines_new = new_content.splitlines()
    # Simple line-by-line diff using difflib for readable output
    import difflib
    label = f"Diff: {file_path}" if file_path else "Diff"
    diff_iter = difflib.unified_diff(
        lines_old,
        lines_new,
        fromfile=f"{file_path} (old)",
        tofile=f"{file_path} (new)",
        lineterm="",
    )
    body = "\n".join(line for line in diff_iter)
    if body and not body.startswith(label):
        body = f"{label}\n{body}"
    return body
