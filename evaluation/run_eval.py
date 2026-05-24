"""
Evaluation Runner
Runs all 20 prompts (10 real + 10 edge cases) through the pipeline.
Tracks: success rate, retries, failure types, latency.
Saves results to evaluation/results.json
"""

import sys, os, json, time, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("eval")

DATASET_PATH = os.path.join(os.path.dirname(__file__), "dataset.json")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results.json")


def score_result(result, expected: dict) -> dict:
    """Score a pipeline result against expectations."""
    score = {"passed": [], "failed": []}

    if not result.success:
        score["failed"].append("pipeline_crashed")
        return score

    # Check entities extracted
    if "expected_entities" in expected:
        found_entities = [e["name"] for e in result.system_design.get("entities", [])]
        for entity in expected["expected_entities"]:
            if any(entity.lower() in f.lower() for f in found_entities):
                score["passed"].append(f"entity:{entity}")
            else:
                score["failed"].append(f"missing_entity:{entity}")

    # Check roles
    if "expected_roles" in expected:
        found_roles = result.intent.get("roles", [])
        for role in expected["expected_roles"]:
            if any(role.lower() in r.lower() for r in found_roles):
                score["passed"].append(f"role:{role}")
            else:
                score["failed"].append(f"missing_role:{role}")

    # Check schemas generated
    if result.db_schema.get("tables"):
        score["passed"].append("db_schema_generated")
    else:
        score["failed"].append("db_schema_empty")

    if result.api_schema.get("endpoints"):
        score["passed"].append("api_schema_generated")
    else:
        score["failed"].append("api_schema_empty")

    if result.ui_schema.get("pages"):
        score["passed"].append("ui_schema_generated")
    else:
        score["failed"].append("ui_schema_empty")

    if result.auth_schema.get("rules"):
        score["passed"].append("auth_schema_generated")
    else:
        score["failed"].append("auth_schema_empty")

    return score


def run_evaluation(subset: str = "all", limit: int = None):
    """
    Run evaluation on dataset.
    subset: 'all' | 'real' | 'edge'
    limit: max prompts to run (for quick tests)
    """
    with open(DATASET_PATH) as f:
        dataset = json.load(f)

    prompts = []
    if subset in ("all", "real"):
        prompts.extend([{"type": "real", **p} for p in dataset["real_prompts"]])
    if subset in ("all", "edge"):
        prompts.extend([{"type": "edge", **p} for p in dataset["edge_cases"]])

    if limit:
        prompts = prompts[:limit]

    results = []
    summary = {
        "total":          len(prompts),
        "success":        0,
        "failed":         0,
        "total_retries":  0,
        "avg_latency":    0.0,
        "failure_types":  {},
        "by_type":        {"real": {"success": 0, "total": 0}, "edge": {"success": 0, "total": 0}}
    }

    for i, prompt_data in enumerate(prompts):
        logger.info(f"[{i+1}/{len(prompts)}] Running: {prompt_data['name']}")
        t0 = time.time()

        result = run_pipeline(prompt_data["prompt"])
        latency = round(time.time() - t0, 2)

        score = score_result(result, prompt_data)
        passed = len(score["passed"])
        total_checks = passed + len(score["failed"])
        pass_rate = round(passed / total_checks, 2) if total_checks else 0

        entry = {
            "id":           prompt_data["id"],
            "name":         prompt_data["name"],
            "type":         prompt_data["type"],
            "prompt":       prompt_data["prompt"][:200],
            "success":      result.success,
            "latency":      latency,
            "retries":      result.metrics.get("retries", 0),
            "pass_rate":    pass_rate,
            "checks":       score,
            "issues_found": result.issues_found,
            "assumptions":  result.assumptions,
            "metrics":      result.metrics,
            "error":        result.error
        }
        results.append(entry)

        # Update summary
        ptype = prompt_data["type"]
        summary["by_type"][ptype]["total"] += 1
        if result.success:
            summary["success"] += 1
            summary["by_type"][ptype]["success"] += 1
        else:
            summary["failed"] += 1
            if result.error:
                err_key = result.error[:50]
                summary["failure_types"][err_key] = summary["failure_types"].get(err_key, 0) + 1

        summary["total_retries"] += result.metrics.get("retries", 0)

        logger.info(f"  → {'OK' if result.success else 'FAIL'} | {latency}s | pass_rate={pass_rate}")

    latencies = [r["latency"] for r in results]
    summary["avg_latency"] = round(sum(latencies) / len(latencies), 2) if latencies else 0
    summary["success_rate"] = round(summary["success"] / summary["total"], 2) if summary["total"] else 0

    output = {"summary": summary, "results": results}
    with open(RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print("\n" + "="*60)
    print(f"EVALUATION COMPLETE")
    print(f"="*60)
    print(f"Total:        {summary['total']}")
    print(f"Success:      {summary['success']} ({summary['success_rate']*100:.0f}%)")
    print(f"Failed:       {summary['failed']}")
    print(f"Avg latency:  {summary['avg_latency']}s")
    print(f"Total retries:{summary['total_retries']}")
    print(f"Results saved to: {RESULTS_PATH}")
    print("="*60)

    return output


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset", default="all", choices=["all","real","edge"])
    parser.add_argument("--limit",  type=int, default=None)
    args = parser.parse_args()
    run_evaluation(subset=args.subset, limit=args.limit)
