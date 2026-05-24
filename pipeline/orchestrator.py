"""
Main Pipeline Orchestrator
Runs all 5 stages in sequence, tracks metrics, handles failures gracefully.
"""

import time, json, logging, traceback
from typing import Optional
from .stage1_intent   import extract_intent
from .stage2_design   import design_system
from .stage3_schemas  import generate_schemas
from .validator       import refine_and_validate, repair_json

logger = logging.getLogger("ai-compiler")


class PipelineResult:
    def __init__(self):
        self.success         = False
        self.intent          = {}
        self.system_design   = {}
        self.db_schema       = {}
        self.api_schema      = {}
        self.ui_schema       = {}
        self.auth_schema     = {}
        self.assumptions     = []
        self.refinement_notes= []
        self.issues_found    = []
        self.metrics         = {}
        self.error           = None
        self.stage_timings   = {}

    def to_dict(self) -> dict:
        return {
            "success":           self.success,
            "intent":            self.intent,
            "system_design":     self.system_design,
            "db_schema":         self.db_schema,
            "api_schema":        self.api_schema,
            "ui_schema":         self.ui_schema,
            "auth_schema":       self.auth_schema,
            "assumptions":       self.assumptions,
            "refinement_notes":  self.refinement_notes,
            "issues_found":      self.issues_found,
            "metrics":           self.metrics,
            "error":             self.error
        }


def run_pipeline(user_prompt: str) -> PipelineResult:
    """
    Execute the full 5-stage pipeline.
    Returns a PipelineResult with all schemas + metrics.
    """
    result  = PipelineResult()
    t_total = time.time()
    retries = 0

    def run_stage(name: str, fn, *args):
        nonlocal retries
        t0 = time.time()
        try:
            output = fn(*args)
            result.stage_timings[name] = round(time.time() - t0, 2)
            logger.info(f"Stage '{name}' completed in {result.stage_timings[name]}s")
            return output
        except Exception as e:
            retries += 1
            logger.warning(f"Stage '{name}' failed: {e}. Retrying once...")
            time.sleep(1)
            try:
                output = fn(*args)
                result.stage_timings[name] = round(time.time() - t0, 2)
                return output
            except Exception as e2:
                result.stage_timings[name] = round(time.time() - t0, 2)
                raise RuntimeError(f"Stage '{name}' failed after retry: {e2}") from e2

    try:
        # ── Stage 1: Intent Extraction ───────────────────────────────────────
        intent = run_stage("1_intent_extraction", extract_intent, user_prompt)
        result.intent      = intent
        result.assumptions = intent.get("assumptions", [])

        # ── Stage 2: System Design ───────────────────────────────────────────
        system_design = run_stage("2_system_design", design_system, intent)
        result.system_design = system_design

        # ── Stage 3: Schema Generation ───────────────────────────────────────
        schemas = run_stage("3_schema_generation", generate_schemas, intent, system_design)

        # ── Stage 4: Validation + Refinement ─────────────────────────────────
        refined = run_stage(
            "4_validation_refinement",
            refine_and_validate,
            schemas["db_schema"],
            schemas["api_schema"],
            schemas["ui_schema"],
            schemas["auth_schema"],
            system_design,
            intent
        )

        result.db_schema        = refined["db_schema"]
        result.api_schema       = refined["api_schema"]
        result.ui_schema        = refined["ui_schema"]
        result.auth_schema      = refined["auth_schema"]
        result.refinement_notes = refined.get("refinement_notes", [])
        result.issues_found     = refined.get("issues_found", [])

        result.success = True

    except Exception as e:
        result.success = False
        result.error   = str(e)
        logger.error(f"Pipeline failed: {traceback.format_exc()}")

    finally:
        total_time = round(time.time() - t_total, 2)
        result.metrics = {
            "total_latency_seconds": total_time,
            "stage_timings":         result.stage_timings,
            "retries":               retries,
            "issues_detected":       len(result.issues_found),
            "assumptions_made":      len(result.assumptions),
            "tables_generated":      len(result.db_schema.get("tables", [])),
            "endpoints_generated":   len(result.api_schema.get("endpoints", [])),
            "pages_generated":       len(result.ui_schema.get("pages", [])),
            "auth_rules_generated":  len(result.auth_schema.get("rules", [])),
        }

    return result
