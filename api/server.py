"""
FastAPI server — AI Compiler backend
Endpoints:
  POST /compile         — run full pipeline, returns JSON
  GET  /health          — health check
  GET  /evaluation      — return evaluation dataset + metrics
"""

import sys, os, json, logging, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ai-compiler")

app = FastAPI(
    title="AI Compiler",
    description="Natural language → executable app configuration",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CompileRequest(BaseModel):
    prompt: str
    debug:  bool = False


class CompileResponse(BaseModel):
    success:           bool
    intent:            dict
    system_design:     dict
    db_schema:         dict
    api_schema:        dict
    ui_schema:         dict
    auth_schema:       dict
    assumptions:       list
    refinement_notes:  list
    issues_found:      list
    metrics:           dict
    error:             str | None


@app.get("/health")
def health():
    return {"status": "ok", "model": "claude-sonnet-4-20250514"}


@app.post("/compile")
def compile_app(req: CompileRequest):
    if not req.prompt or len(req.prompt.strip()) < 10:
        raise HTTPException(status_code=400, detail="Prompt too short. Please describe your app in detail.")

    if len(req.prompt) > 5000:
        raise HTTPException(status_code=400, detail="Prompt too long. Keep it under 5000 characters.")

    logger.info(f"Compiling: {req.prompt[:100]}...")
    result = run_pipeline(req.prompt)
    return JSONResponse(content=result.to_dict())


@app.get("/evaluation")
def get_evaluation():
    """Return the evaluation dataset."""
    try:
        with open(os.path.join(os.path.dirname(__file__), "..", "evaluation", "dataset.json")) as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Evaluation dataset not generated yet. Run: python evaluation/run_eval.py")


@app.get("/")
def root():
    return {
        "name": "AI Compiler API",
        "version": "1.0.0",
        "endpoints": {
            "POST /compile":    "Run the full pipeline on a prompt",
            "GET  /health":     "Health check",
            "GET  /evaluation": "Evaluation results"
        }
    }
