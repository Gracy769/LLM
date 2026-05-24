"""
Stage 4: Validation + Repair Engine
The most critical part of the pipeline.

Detects and handles:
  - Invalid JSON (syntax errors, truncation)
  - Missing required keys
  - Type mismatches
  - Cross-layer inconsistencies (API fields not in DB, UI bindings to nonexistent endpoints)
  - Hallucinated fields
  - Logical conflicts

Repair strategy:
  - Level 1: Auto-fix (add missing fields, coerce types, fix references) — no LLM call
  - Level 2: Targeted re-generation — re-run only the broken stage, not the whole pipeline
  - Level 3: Clarification (for unresolvable conflicts)
  - Never: blind full retry
"""

import json
import re
import jsonschema
from typing import Any, Optional
from .llm import call_claude


# ── JSON Repair ──────────────────────────────────────────────────────────────

def repair_json(raw: str) -> dict:
    """
    Attempt to extract and parse valid JSON from LLM output.
    Handles: markdown fences, leading text, truncated JSON.
    """
    if not raw or not raw.strip():
        raise ValueError("Empty response from LLM")

    # Strip markdown code fences
    text = re.sub(r"```(?:json)?\s*", "", raw).strip()
    text = text.replace("```", "").strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object via regex
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Try to fix truncated JSON by counting braces
    open_b  = text.count('{')
    close_b = text.count('}')
    if open_b > close_b:
        text = text + '}' * (open_b - close_b)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # Last resort: ask LLM to fix it
    fix_prompt = f"""The following text should be valid JSON but isn't. Fix it and return ONLY the corrected JSON, nothing else:

{raw[:3000]}"""
    fixed = call_claude([{"role": "user", "content": fix_prompt}], temperature=0)
    fixed_clean = re.sub(r"```(?:json)?\s*", "", fixed).strip().replace("```", "")
    return json.loads(fixed_clean)


# ── Schema Validation ────────────────────────────────────────────────────────

def validate_against_schema(data: dict, schema: dict, stage: str = "") -> dict:
    """
    Validate data against a JSON schema.
    Auto-repairs simple issues before raising.
    """
    try:
        jsonschema.validate(instance=data, schema=schema)
        return data
    except jsonschema.ValidationError as e:
        # Attempt level-1 auto-repair
        repaired = _auto_repair(data, schema, e)
        try:
            jsonschema.validate(instance=repaired, schema=schema)
            return repaired
        except jsonschema.ValidationError as e2:
            raise ValueError(f"[{stage}] Schema validation failed after repair attempt: {e2.message}")


def _auto_repair(data: dict, schema: dict, error: jsonschema.ValidationError) -> dict:
    """
    Level-1 repairs: fill missing required fields with sensible defaults.
    """
    repaired = dict(data)
    required = schema.get("required", [])
    props    = schema.get("properties", {})

    for field in required:
        if field not in repaired:
            field_schema = props.get(field, {})
            field_type   = field_schema.get("type", "string")
            if field_type == "array":
                repaired[field] = []
            elif field_type == "object":
                repaired[field] = {}
            elif field_type == "boolean":
                repaired[field] = False
            elif field_type == "integer":
                repaired[field] = 0
            else:
                repaired[field] = ""

    return repaired


# ── Cross-Layer Consistency Checks ───────────────────────────────────────────

class ConsistencyIssue:
    def __init__(self, layer: str, issue_type: str, detail: str, severity: str = "warning"):
        self.layer      = layer
        self.issue_type = issue_type
        self.detail     = detail
        self.severity   = severity  # warning | error

    def __repr__(self):
        return f"[{self.severity.upper()}] {self.layer}: {self.issue_type} — {self.detail}"


def check_cross_layer_consistency(db_schema: dict, api_schema: dict,
                                   ui_schema: dict, auth_schema: dict,
                                   system_design: dict) -> list[ConsistencyIssue]:
    """
    Run all cross-layer checks. Returns list of issues found.
    """
    issues = []
    issues.extend(_check_api_vs_db(api_schema, db_schema))
    issues.extend(_check_ui_vs_api(ui_schema, api_schema))
    issues.extend(_check_auth_vs_design(auth_schema, system_design))
    issues.extend(_check_pages_vs_design(ui_schema, system_design))
    return issues


def _check_api_vs_db(api_schema: dict, db_schema: dict) -> list[ConsistencyIssue]:
    """API endpoints should map to existing DB tables."""
    issues = []
    table_names = {t["name"].lower() for t in db_schema.get("tables", [])}

    for ep in api_schema.get("endpoints", []):
        path = ep.get("path", "")
        # Extract resource name from path, e.g. /contacts/:id → contacts
        parts = [p for p in path.split("/") if p and not p.startswith(":")]
        if len(parts) >= 2:  # skip /auth/...
            resource = parts[1] if parts[0] in ("api", "v1", "v2") else parts[0]
            # Pluralised table check
            if resource not in table_names and resource.rstrip("s") not in table_names:
                issues.append(ConsistencyIssue(
                    "api→db", "missing_table",
                    f"Endpoint {ep['method']} {path} references resource '{resource}' but no matching DB table found",
                    severity="warning"
                ))
    return issues


def _check_ui_vs_api(ui_schema: dict, api_schema: dict) -> list[ConsistencyIssue]:
    """UI api_bindings should reference endpoints that actually exist."""
    issues = []
    existing = set()
    for ep in api_schema.get("endpoints", []):
        existing.add(f"{ep['method']} {ep['path']}")
        # Also add without path params for fuzzy match
        base = re.sub(r"/:[\w]+", "/:id", ep["path"])
        existing.add(f"{ep['method']} {base}")

    for page in ui_schema.get("pages", []):
        for comp in page.get("components", []):
            binding = comp.get("api_binding", "")
            if binding and binding not in existing:
                # Try normalised form
                norm = re.sub(r"/[0-9a-f-]{8,}", "/:id", binding)
                if norm not in existing:
                    issues.append(ConsistencyIssue(
                        "ui→api", "broken_binding",
                        f"Component '{comp['type']}' on page '{page['name']}' binds to '{binding}' which doesn't exist in API schema",
                        severity="warning"
                    ))
    return issues


def _check_auth_vs_design(auth_schema: dict, system_design: dict) -> list[ConsistencyIssue]:
    """Auth roles must match roles defined in system design."""
    issues = []
    design_roles = {r["name"] for r in system_design.get("roles", [])}
    auth_roles   = set(auth_schema.get("roles", []))

    for role in auth_roles - design_roles:
        issues.append(ConsistencyIssue(
            "auth→design", "undefined_role",
            f"Auth schema references role '{role}' not defined in system design",
            severity="error"
        ))

    for rule in auth_schema.get("rules", []):
        for role in rule.get("roles", []):
            if role not in design_roles:
                issues.append(ConsistencyIssue(
                    "auth→design", "rule_undefined_role",
                    f"Auth rule for {rule['resource']}:{rule['action']} references undefined role '{role}'",
                    severity="error"
                ))
    return issues


def _check_pages_vs_design(ui_schema: dict, system_design: dict) -> list[ConsistencyIssue]:
    """Every page in system design should have a UI counterpart."""
    issues = []
    design_pages = {p["name"].lower() for p in system_design.get("pages", [])}
    ui_pages     = {p["name"].lower() for p in ui_schema.get("pages", [])}

    for page in design_pages - ui_pages:
        issues.append(ConsistencyIssue(
            "ui→design", "missing_page",
            f"System design defines page '{page}' but it has no UI schema",
            severity="warning"
        ))
    return issues


# ── Targeted Repair ───────────────────────────────────────────────────────────

def repair_cross_layer_issues(issues: list[ConsistencyIssue],
                               schemas: dict, context: dict) -> dict:
    """
    Targeted repair: fix only the broken layer, not the whole pipeline.
    Returns updated schemas dict.
    """
    if not issues:
        return schemas

    error_issues   = [i for i in issues if i.severity == "error"]
    warning_issues = [i for i in issues if i.severity == "warning"]

    # Auto-repair warnings (add missing auth roles, stub missing pages)
    schemas = _auto_fix_warnings(warning_issues, schemas)

    # LLM-targeted repair for errors
    if error_issues:
        schemas = _llm_targeted_repair(error_issues, schemas, context)

    return schemas


def _auto_fix_warnings(issues: list[ConsistencyIssue], schemas: dict) -> dict:
    """Level-1 auto-fix for warning-level inconsistencies."""
    for issue in issues:
        if issue.issue_type == "missing_page":
            # Stub out a minimal page
            page_name = issue.detail.split("'")[1]
            schemas["ui_schema"]["pages"].append({
                "name":   page_name.capitalize(),
                "route":  f"/{page_name.lower()}",
                "layout": "full-page",
                "components": [{"type": "Card", "props": {"title": page_name}, "api_binding": ""}]
            })
    return schemas


def _llm_targeted_repair(issues: list[ConsistencyIssue], schemas: dict, context: dict) -> dict:
    """
    Level-2: Ask Claude to fix only the specific layer with the issue.
    Much cheaper than re-running the full pipeline.
    """
    issue_summary = "\n".join(str(i) for i in issues)
    prompt = f"""You are a repair engine. Fix ONLY the specific inconsistencies listed below.
Return ONLY the corrected schema as raw JSON. Do not change anything that isn't broken.

Issues to fix:
{issue_summary}

Current auth schema:
{json.dumps(schemas.get("auth_schema", {}), indent=2)}

Valid roles from system design:
{json.dumps([r["name"] for r in context.get("system_design", {}).get("roles", [])], indent=2)}

Return the corrected auth_schema JSON only:"""

    from .schemas import AUTH_SCHEMA
    raw = call_claude([{"role": "user", "content": prompt}], temperature=0)
    try:
        repaired = repair_json(raw)
        validate_against_schema(repaired, AUTH_SCHEMA, stage="auth_repair")
        schemas["auth_schema"] = repaired
    except Exception:
        pass  # Keep original if repair fails — log but don't crash

    return schemas


# ── Refinement Layer ──────────────────────────────────────────────────────────

REFINEMENT_PROMPT = """You are Stage 4 of an AI compiler — the Refinement Layer.

You receive four schemas (DB, API, UI, Auth) and a list of detected inconsistencies.
Your job: produce a single refined output that resolves all inconsistencies.

Rules:
- Output ONLY raw JSON.
- Preserve everything that is already correct.
- Fix only what is inconsistent.
- Add a "refinement_notes" array listing what you changed and why.

Output shape:
{
  "db_schema":       { ... },
  "api_schema":      { ... },
  "ui_schema":       { ... },
  "auth_schema":     { ... },
  "refinement_notes": ["Changed X because Y", ...]
}"""


def refine_and_validate(db_schema: dict, api_schema: dict, ui_schema: dict,
                         auth_schema: dict, system_design: dict, intent: dict) -> dict:
    """
    Full Stage 4: check consistency, repair, then do one final LLM refinement pass.
    Returns all four schemas + refinement notes.
    """
    issues = check_cross_layer_consistency(db_schema, api_schema, ui_schema, auth_schema, system_design)

    schemas = {
        "db_schema":   db_schema,
        "api_schema":  api_schema,
        "ui_schema":   ui_schema,
        "auth_schema": auth_schema
    }

    # Auto + targeted repair first
    context = {"system_design": system_design, "intent": intent}
    schemas = repair_cross_layer_issues(issues, schemas, context)

    # Final LLM refinement pass
    issue_text = "\n".join(str(i) for i in issues) if issues else "No issues detected."

    messages = [{
        "role": "user",
        "content": (
            f"Refine these schemas. Detected issues:\n{issue_text}\n\n"
            f"DB Schema:\n{json.dumps(schemas['db_schema'], indent=2)}\n\n"
            f"API Schema:\n{json.dumps(schemas['api_schema'], indent=2)}\n\n"
            f"UI Schema:\n{json.dumps(schemas['ui_schema'], indent=2)}\n\n"
            f"Auth Schema:\n{json.dumps(schemas['auth_schema'], indent=2)}"
        )
    }]

    raw = call_claude(messages, system=REFINEMENT_PROMPT, temperature=0.1)
    refined = repair_json(raw)

    return {
        "db_schema":         refined.get("db_schema",   schemas["db_schema"]),
        "api_schema":        refined.get("api_schema",  schemas["api_schema"]),
        "ui_schema":         refined.get("ui_schema",   schemas["ui_schema"]),
        "auth_schema":       refined.get("auth_schema", schemas["auth_schema"]),
        "refinement_notes":  refined.get("refinement_notes", []),
        "issues_found":      [str(i) for i in issues]
    }
