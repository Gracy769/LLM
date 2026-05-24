"""
Stage 2: System Design Layer
Converts structured intent → app architecture.
Defines entities with fields, user flows, role-permission matrix, and pages.
"""

import json
from .llm import call_claude
from .schemas import SYSTEM_DESIGN_SCHEMA
from .validator import validate_against_schema, repair_json

SYSTEM_PROMPT = """You are Stage 2 of an AI application compiler — the System Designer.

You receive a structured intent object and produce a complete app architecture.

Rules:
- Output ONLY raw JSON. No markdown, no explanation, no backticks.
- Every entity must have realistic fields (include id, created_at, updated_at always).
- Every role must have explicit permissions listed.
- Every page must list which roles can access it.
- Flows must cover the happy path AND error path.
- Relations use format: "entity_name via field_name" e.g. "User via user_id"

Output this exact shape:
{
  "entities": [
    {
      "name": "User",
      "fields": ["id:uuid", "email:string", "role:enum", "created_at:timestamp"],
      "relations": ["Profile via user_id", "Order via user_id"]
    }
  ],
  "flows": [
    {
      "name": "User Registration",
      "steps": ["POST /auth/register", "Validate email unique", "Hash password", "Create user record", "Send verification email", "Return JWT"],
      "actors": ["guest"]
    }
  ],
  "roles": [
    {
      "name": "admin",
      "permissions": ["users:read", "users:write", "users:delete", "analytics:read"]
    }
  ],
  "permissions": {
    "users:read":   ["admin", "manager"],
    "users:write":  ["admin"],
    "users:delete": ["admin"]
  },
  "pages": [
    {
      "name": "Dashboard",
      "route": "/dashboard",
      "allowed_roles": ["admin", "user"],
      "components": ["StatsCard", "RecentActivityTable", "QuickActions"]
    }
  ]
}"""


def design_system(intent: dict) -> dict:
    """
    Convert intent → system architecture with entities, flows, roles, pages.
    """
    messages = [
        {
            "role": "user",
            "content": f"Design the full system architecture for this app intent:\n\n{json.dumps(intent, indent=2)}"
        }
    ]

    raw = call_claude(messages, system=SYSTEM_PROMPT, temperature=0.1)
    parsed = repair_json(raw)
    validated = validate_against_schema(parsed, SYSTEM_DESIGN_SCHEMA, stage="system_design")

    # Enforce: every entity always has id + timestamps
    for entity in validated.get("entities", []):
        fields = entity.get("fields", [])
        field_names = [f.split(":")[0] for f in fields]
        if "id" not in field_names:
            entity["fields"].insert(0, "id:uuid")
        if "created_at" not in field_names:
            entity["fields"].append("created_at:timestamp")
        if "updated_at" not in field_names:
            entity["fields"].append("updated_at:timestamp")

    return validated
