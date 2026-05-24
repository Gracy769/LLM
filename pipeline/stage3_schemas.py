"""
Stage 3: Schema Generator
Generates four schemas in parallel (conceptually):
  - DB schema  (tables, columns, relations, indexes)
  - API schema (endpoints, methods, validation, roles)
  - UI schema  (pages, components, layouts, api_bindings)
  - Auth schema (strategy, roles, rules)

Each is generated separately with its own focused prompt,
then cross-checked in Stage 4.
"""

import json
from .llm import call_claude
from .schemas import DB_SCHEMA, API_SCHEMA, UI_SCHEMA, AUTH_SCHEMA
from .validator import validate_against_schema, repair_json

# ── DB Schema ────────────────────────────────────────────────────────────────

DB_PROMPT = """You are a database architect. Generate a complete SQL-compatible DB schema.

Rules:
- Output ONLY raw JSON. No markdown. No explanation.
- Every table must have a primary key column.
- Foreign keys must reference existing tables by exact name.
- Use types: uuid, string, text, integer, float, boolean, timestamp, enum, json
- Add indexes for all foreign keys and frequently queried fields.

Output shape:
{
  "tables": [
    {
      "name": "users",
      "columns": [
        {"name": "id",         "type": "uuid",      "nullable": false, "unique": true},
        {"name": "email",      "type": "string",    "nullable": false, "unique": true},
        {"name": "role",       "type": "enum",      "nullable": false},
        {"name": "created_at", "type": "timestamp", "nullable": false}
      ],
      "primary_key": "id",
      "indexes": ["email", "role"]
    }
  ]
}"""

# ── API Schema ───────────────────────────────────────────────────────────────

API_PROMPT = """You are an API architect. Generate a complete REST API schema.

Rules:
- Output ONLY raw JSON. No markdown. No explanation.
- Every endpoint must specify: path, method, auth_required, roles, request_body, response.
- paths use kebab-case and :param for path params. e.g. /contacts/:id
- Include CRUD endpoints for every entity plus business-logic endpoints.
- request_body and response use JSON schema format (type, properties, required).

Output shape:
{
  "endpoints": [
    {
      "path":          "/auth/login",
      "method":        "POST",
      "description":   "Authenticate user and return JWT",
      "auth_required": false,
      "roles":         [],
      "request_body":  {"type": "object", "properties": {"email": {"type": "string"}, "password": {"type": "string"}}, "required": ["email","password"]},
      "response":      {"type": "object", "properties": {"token": {"type": "string"}, "user": {"type": "object"}}}
    }
  ]
}"""

# ── UI Schema ────────────────────────────────────────────────────────────────

UI_PROMPT = """You are a frontend architect. Generate a complete UI schema.

Rules:
- Output ONLY raw JSON. No markdown. No explanation.
- Every page must list its components with props and the API endpoint they bind to.
- layout must be one of: full-page, sidebar, centered, split
- Component types: Table, Form, Card, Chart, Modal, Button, Input, Select, Badge, Tabs, Sidebar, Header

Output shape:
{
  "pages": [
    {
      "name":   "Login",
      "route":  "/login",
      "layout": "centered",
      "components": [
        {
          "type":        "Form",
          "props":       {"title": "Sign In", "fields": ["email","password"], "submit_label": "Login"},
          "api_binding": "POST /auth/login"
        }
      ]
    }
  ]
}"""

# ── Auth Schema ───────────────────────────────────────────────────────────────

AUTH_PROMPT = """You are a security architect. Generate a complete auth and permissions schema.

Rules:
- Output ONLY raw JSON. No markdown. No explanation.
- strategy must be: jwt
- Every resource must have rules for every action it supports.
- Be explicit — list every role that can access each resource+action.

Output shape:
{
  "strategy": "jwt",
  "roles": ["admin", "user"],
  "rules": [
    {"resource": "contacts", "action": "read",   "roles": ["admin","user"]},
    {"resource": "contacts", "action": "write",  "roles": ["admin"]},
    {"resource": "contacts", "action": "delete", "roles": ["admin"]}
  ],
  "token_config": {
    "expiry_seconds": 86400,
    "refresh_enabled": true,
    "algorithm": "HS256"
  }
}"""


def _generate_schema(schema_type: str, prompt: str, context: dict, output_schema: dict) -> dict:
    system_map = {
        "db":   DB_PROMPT,
        "api":  API_PROMPT,
        "ui":   UI_PROMPT,
        "auth": AUTH_PROMPT
    }
    messages = [
        {
            "role": "user",
            "content": (
                f"Generate the {schema_type.upper()} schema for this app.\n\n"
                f"Intent:\n{json.dumps(context['intent'], indent=2)}\n\n"
                f"System Design:\n{json.dumps(context['system_design'], indent=2)}"
            )
        }
    ]
    raw = call_claude(messages, system=system_map[schema_type], temperature=0.1)
    parsed = repair_json(raw)
    return validate_against_schema(parsed, output_schema, stage=f"schema_gen_{schema_type}")


def generate_schemas(intent: dict, system_design: dict) -> dict:
    """
    Generate all four schemas from intent + system design.
    Returns dict with keys: db_schema, api_schema, ui_schema, auth_schema
    """
    context = {"intent": intent, "system_design": system_design}

    db_schema   = _generate_schema("db",   DB_PROMPT,   context, DB_SCHEMA)
    api_schema  = _generate_schema("api",  API_PROMPT,  context, API_SCHEMA)
    ui_schema   = _generate_schema("ui",   UI_PROMPT,   context, UI_SCHEMA)
    auth_schema = _generate_schema("auth", AUTH_PROMPT, context, AUTH_SCHEMA)

    return {
        "db_schema":   db_schema,
        "api_schema":  api_schema,
        "ui_schema":   ui_schema,
        "auth_schema": auth_schema
    }
