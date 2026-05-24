"""
Strict JSON contracts for every pipeline stage.
All stages must produce output that validates against these schemas.
"""

INTENT_SCHEMA = {
    "type": "object",
    "required": ["app_name", "app_type", "features", "entities", "roles", "integrations", "ambiguities"],
    "properties": {
        "app_name":      {"type": "string"},
        "app_type":      {"type": "string", "enum": ["crm", "ecommerce", "saas", "dashboard", "marketplace", "custom"]},
        "features":      {"type": "array", "items": {"type": "string"}},
        "entities":      {"type": "array", "items": {"type": "string"}},
        "roles":         {"type": "array", "items": {"type": "string"}},
        "integrations":  {"type": "array", "items": {"type": "string"}},
        "ambiguities":   {"type": "array", "items": {"type": "string"}},
        "assumptions":   {"type": "array", "items": {"type": "string"}}
    }
}

SYSTEM_DESIGN_SCHEMA = {
    "type": "object",
    "required": ["entities", "flows", "roles", "permissions", "pages"],
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "fields", "relations"],
                "properties": {
                    "name":      {"type": "string"},
                    "fields":    {"type": "array", "items": {"type": "string"}},
                    "relations": {"type": "array", "items": {"type": "string"}}
                }
            }
        },
        "flows": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "steps", "actors"],
                "properties": {
                    "name":   {"type": "string"},
                    "steps":  {"type": "array", "items": {"type": "string"}},
                    "actors": {"type": "array", "items": {"type": "string"}}
                }
            }
        },
        "roles": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "permissions"],
                "properties": {
                    "name":        {"type": "string"},
                    "permissions": {"type": "array", "items": {"type": "string"}}
                }
            }
        },
        "permissions": {"type": "object"},
        "pages": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "route", "allowed_roles", "components"],
                "properties": {
                    "name":          {"type": "string"},
                    "route":         {"type": "string"},
                    "allowed_roles": {"type": "array", "items": {"type": "string"}},
                    "components":    {"type": "array", "items": {"type": "string"}}
                }
            }
        }
    }
}

DB_SCHEMA = {
    "type": "object",
    "required": ["tables"],
    "properties": {
        "tables": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "columns", "primary_key"],
                "properties": {
                    "name":        {"type": "string"},
                    "columns": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["name", "type"],
                            "properties": {
                                "name":       {"type": "string"},
                                "type":       {"type": "string"},
                                "nullable":   {"type": "boolean"},
                                "unique":     {"type": "boolean"},
                                "references": {"type": "string"}
                            }
                        }
                    },
                    "primary_key": {"type": "string"},
                    "indexes":     {"type": "array", "items": {"type": "string"}}
                }
            }
        }
    }
}

API_SCHEMA = {
    "type": "object",
    "required": ["endpoints"],
    "properties": {
        "endpoints": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["path", "method", "description", "auth_required", "roles", "request_body", "response"],
                "properties": {
                    "path":         {"type": "string"},
                    "method":       {"type": "string", "enum": ["GET","POST","PUT","PATCH","DELETE"]},
                    "description":  {"type": "string"},
                    "auth_required":{"type": "boolean"},
                    "roles":        {"type": "array", "items": {"type": "string"}},
                    "request_body": {"type": "object"},
                    "response":     {"type": "object"}
                }
            }
        }
    }
}

UI_SCHEMA = {
    "type": "object",
    "required": ["pages"],
    "properties": {
        "pages": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "route", "layout", "components"],
                "properties": {
                    "name":   {"type": "string"},
                    "route":  {"type": "string"},
                    "layout": {"type": "string"},
                    "components": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["type", "props"],
                            "properties": {
                                "type":       {"type": "string"},
                                "props":      {"type": "object"},
                                "api_binding":{"type": "string"}
                            }
                        }
                    }
                }
            }
        }
    }
}

AUTH_SCHEMA = {
    "type": "object",
    "required": ["strategy", "roles", "rules"],
    "properties": {
        "strategy": {"type": "string", "enum": ["jwt", "session", "oauth"]},
        "roles": {"type": "array", "items": {"type": "string"}},
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["resource", "action", "roles"],
                "properties": {
                    "resource": {"type": "string"},
                    "action":   {"type": "string"},
                    "roles":    {"type": "array", "items": {"type": "string"}}
                }
            }
        },
        "token_config": {"type": "object"}
    }
}

FULL_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["intent", "system_design", "db_schema", "api_schema", "ui_schema", "auth_schema", "assumptions", "metrics"],
    "properties": {
        "intent":        {"type": "object"},
        "system_design": {"type": "object"},
        "db_schema":     {"type": "object"},
        "api_schema":    {"type": "object"},
        "ui_schema":     {"type": "object"},
        "auth_schema":   {"type": "object"},
        "assumptions":   {"type": "array"},
        "metrics":       {"type": "object"}
    }
}
