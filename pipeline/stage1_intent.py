"""
Stage 1: Intent Extractor
Parses raw natural language into a structured intermediate form.
Identifies: app type, features, entities, roles, integrations, ambiguities.
"""

import json, re
from .llm import call_claude
from .schemas import INTENT_SCHEMA
from .validator import validate_against_schema, repair_json

SYSTEM_PROMPT = """You are Stage 1 of an AI application compiler — an Intent Extractor.

Your ONLY job: parse the user's natural language description into a strict JSON structure.

Rules:
- Output ONLY raw JSON. No markdown, no explanation, no backticks.
- Be exhaustive — extract every entity and feature mentioned, even implicit ones.
- If something is ambiguous, add it to "ambiguities".
- If you fill in something unstated, add it to "assumptions".
- app_type must be one of: crm, ecommerce, saas, dashboard, marketplace, custom

Output this exact shape:
{
  "app_name": "string — inferred from description",
  "app_type": "crm|ecommerce|saas|dashboard|marketplace|custom",
  "features": ["list of all features mentioned or implied"],
  "entities": ["list of all data entities, e.g. User, Contact, Order"],
  "roles":    ["list of all user roles mentioned"],
  "integrations": ["list of third-party integrations, e.g. Stripe, SendGrid"],
  "ambiguities": ["things that are unclear and need clarification"],
  "assumptions": ["decisions you made because input was underspecified"]
}"""


def extract_intent(user_prompt: str) -> dict:
    """
    Convert natural language prompt → structured intent dict.
    Returns validated intent or raises with repair attempt.
    """
    messages = [
        {"role": "user", "content": f"Extract the intent from this app description:\n\n{user_prompt}"}
    ]

    raw = call_claude(messages, system=SYSTEM_PROMPT, temperature=0.1)
    parsed = repair_json(raw)
    validated = validate_against_schema(parsed, INTENT_SCHEMA, stage="intent_extraction")

    # Ensure minimum viable output
    validated.setdefault("assumptions", [])
    validated.setdefault("ambiguities", [])
    if not validated.get("roles"):
        validated["roles"] = ["user", "admin"]
        validated["assumptions"].append("Default roles (user, admin) assumed since none specified")

    return validated
