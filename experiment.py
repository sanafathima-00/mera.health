"""Bounded historical-revision experiment runner. Default mode never calls Gemini."""
import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import time
import types
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

import evaluate

ROOT = Path(__file__).resolve().parent
REVISIONS = {"original": "df3de423ac889a084b0cd7fd02a04f5d1c95dc29",
             "improved": "9933806ac76fe1efc951c2ec77f42334065d71d5"}
MODEL = "gemini-3.6-flash"
CONFIG = {"temperature": 0, "maxOutputTokens": 16000}
MATRIX = [(r, v, 60) for r, order in [("06", ("original", "improved")),
          ("11", ("improved", "original")), ("03", ("original", "improved")),
          ("08", ("improved", "original"))] for v in order] + [
          ("11", "improved", 150), ("11", "improved", 300)]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def policy_fingerprints():
    paths = [ROOT / name for name in ("evaluate.py", "evaluation_cases.json", "EVALUATION.md", "schema.json")]
    return {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in paths + sorted((ROOT / "gold").glob("*.json"))}


def load_revision(version, dpi):
    source = subprocess.check_output(["git", "show", REVISIONS[version] + ":extract.py"], cwd=ROOT)
    module = types.ModuleType("historical_" + version)
    exec(compile(source, REVISIONS[version] + ":extract.py", "exec"), module.__dict__)
    module.MODEL, module.DPI = MODEL, dpi
    return module, digest(source)


def local_key(path):
    entries = re.findall(r"^\s*GEMINI_API_KEY\s*=\s*(.*?)\s*$", path.read_text(encoding="utf-8-sig"), re.M)
    if len(entries) != 1:
        raise ValueError("Expected exactly one local API key entry")
    key = entries[0]
    if key[:1] in ("'", '"'):
        if len(key) < 2 or key[-1] != key[0]:
            raise ValueError("Unbalanced API key quotes")
        key = key[1:-1].strip()
    if not key or key == "PASTE_YOUR_API_KEY_HERE" or re.search(r"\s", key):
        raise ValueError("Local API key is missing or a placeholder")
    return key


def write_json(path, data, key=""):
    text = json.dumps(data, indent=2, ensure_ascii=True, allow_nan=False)
    if key:
        text = text.replace(key, "[REDACTED_SECRET]")
    path.write_text(text + "\n", encoding="utf-8")


def classify(code, body=b""):
    try:
        error = json.loads(body).get("error", {})
        status = error.get("status")
        message = str(error.get("message", "")).lower()
    except (ValueError, AttributeError, UnicodeError):
        status, message = None, ""
    if "billing" in message or "payment" in message:
        category = "billing"
    elif code == 401 or "api_key_invalid" in str(body).lower() or status == "UNAUTHENTICATED":
        category = "authentication"
    elif code == 429 or status == "RESOURCE_EXHAUSTED" or "quota" in message:
        category = "quota"
    elif code == 403:
        category = "permission"
    elif code == 503:
        category = "overload" if any(x in message for x in ("overload", "high demand")) else "unavailable"
    else:
        category = "http_error"
    return category, status if status in ("UNAVAILABLE", "RESOURCE_EXHAUSTED", "UNAUTHENTICATED", "PERMISSION_DENIED", "INVALID_ARGUMENT") else None


def attempt(report, version, dpi, directory, key, transport):
    module, source_hash = load_revision(version, dpi)
    record = {"report": "report_" + report, "revision": REVISIONS[version], "source_sha256": source_hash,
              "model": MODEL, "dpi": dpi, "prompt_sha256": digest(module.PROMPT.encode()),
              "generation_calls": 0, "http_status": None, "usage": None, "schema_valid": False,
              "status": "failed", "category": "preparation", "cost_estimate": None}
    response_body = None
    raw_text = None
    original_parse = module.parse

    def capture_parse(text):
        nonlocal raw_text
        raw_text = text
        return original_parse(text)

    def observed(request, timeout):
        nonlocal response_body
        body = json.loads(request.data)
        parts = body["contents"][0]["parts"]
        expected_prompt = module.PROMPT
        images = [p["inlineData"] for p in parts if "inlineData" in p]
        if version == "improved" and len(images) > 1:
            expected_prompt = "Images are consecutive document pages in order. Extract all pages.\n" + expected_prompt
        if (request.full_url != f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
                or body.get("generationConfig") != CONFIG or timeout != 180
                or parts != [{"inlineData": image} for image in images] + [{"text": expected_prompt}]
                or not images or request.get_header("X-goog-api-key") != key):
            raise RuntimeError("Request configuration mismatch; no call made")
        if record["generation_calls"]:
            raise RuntimeError("Second generation call prohibited")
        record.update(generation_calls=1, category="provider", generation_config=body["generationConfig"],
                      timeout_seconds=timeout, request_prompt=expected_prompt, image_count=len(images),
                      image_sha256=[digest(p["data"].encode()) for p in images])
        try:
            with transport(request, timeout=timeout) as response:
                record["http_status"] = response.status
                record["retry_headers"] = {h: response.headers[h] for h in ("Retry-After", "Date", "Content-Type") if h in response.headers}
                response_body = response.read()
            provider = json.loads(response_body)
            record["usage"] = provider.get("usageMetadata")
            record["response_model_version"] = provider.get("modelVersion")
            record["finish_reasons"] = [c.get("finishReason") for c in provider.get("candidates", []) if isinstance(c, dict)]
            record["category"] = "extraction"
            return io.BytesIO(response_body)
        except urllib.error.HTTPError as error:
            record["http_status"] = error.code
            record["retry_headers"] = {h: error.headers[h] for h in ("Retry-After", "Date", "Content-Type") if error.headers and h in error.headers}
            record["category"], record["provider_status"] = classify(error.code, error.read())
            raise
        except (TimeoutError, urllib.error.URLError):
            record["category"] = "transport"
            raise

    start = time.perf_counter()
    module.parse = capture_parse
    path = ROOT / "reports" / ("report_" + report + (".jpg" if report == "08" else ".pdf"))
    with patch.dict(os.environ, {"GEMINI_API_KEY": key}), patch("urllib.request.urlopen", observed):
        try:
            output = module.extract(path)
            serialized = json.dumps(output, ensure_ascii=True, allow_nan=False)
            record["category"] = "schema"
            evaluate.validate(json.loads(serialized, parse_constant=evaluate.reject_constant,
                                         object_pairs_hook=evaluate.unique_object))
            if key in serialized:
                raise ValueError("Secret echoed in prediction; do not persist")
            record.update(status="success", category=None, schema_valid=True)
            (directory / (record["report"] + ".json")).write_text(serialized + "\n", encoding="utf-8")
        except Exception as error:
            record["error_type"] = type(error).__name__
    record["latency_seconds"] = time.perf_counter() - start
    if raw_text is not None:
        (directory / (record["report"] + ".raw.txt")).write_text(raw_text.replace(key, "[REDACTED_SECRET]"), encoding="utf-8")
    if response_body is not None:
        (directory / (record["report"] + ".response.txt")).write_text(response_body.decode("utf-8", errors="replace").replace(key, "[REDACTED_SECRET]"), encoding="utf-8")
    write_json(directory / (record["report"] + ".attempt.json"), record, key)
    return record


def run_matrix(destination, key, transport):
    destination.mkdir(parents=True, exist_ok=False)
    fingerprints = policy_fingerprints()
    results, consecutive_503, reason = [], 0, "matrix_complete"
    for report, version, dpi in MATRIX:
        if sum(r["generation_calls"] for r in results) >= 10:
            reason = "budget_exhausted"
            break
        if dpi != 60 and not any(r["report"] == "report_11" and r["revision"] == REVISIONS["improved"] and r["schema_valid"] for r in results):
            continue
        directory = destination / f"{version}-{dpi}"
        directory.mkdir(exist_ok=True)
        result = attempt(report, version, dpi, directory, key, transport)
        results.append(result)
        write_json(directory / "run.json", {"reports": {r["report"]: {"status": r["status"], "error": r.get("category")} for r in results if r["revision"] == REVISIONS[version] and r["dpi"] == dpi}}, key)
        consecutive_503 = consecutive_503 + 1 if result["http_status"] == 503 else 0
        if result["category"] in ("authentication", "billing", "quota", "permission"):
            reason = result["category"]
            break
        if consecutive_503 == 2:
            reason = "two_consecutive_503"
            break
        if len(results) == 2 and not all(r["schema_valid"] for r in results):
            reason = "first_pair_invalid"
            break
    pairs = [report for report in ("06", "11", "03", "08") if sum(r["report"] == "report_" + report and r["dpi"] == 60 and r["schema_valid"] for r in results) == 2]
    summary = {"attempts": results, "stop_reason": reason, "generation_calls": sum(r["generation_calls"] for r in results),
               "valid_paired_reports": pairs, "accuracy_improvement": "unproven; inspect valid paired scores" if pairs else "unproven; no valid pairs",
               "successes": sum(r["status"] == "success" for r in results), "cost_estimate": None}
    scored = {}
    for directory in destination.iterdir():
        if directory.is_dir():
            scored[directory.name] = evaluate.evaluate(directory, ROOT / "gold", ROOT / "evaluation_cases.json")
            write_json(directory / "metrics.json", scored[directory.name], key)
    summary["paired_quality"] = {view: {"reports": {"report_" + report: {
        version: scored[version + "-60"]["views"][view]["reports"]["report_" + report]
        for version in REVISIONS} for report in pairs},
        "aggregate": {version: evaluate.aggregate([scored[version + "-60"]["views"][view]["reports"]["report_" + report] for report in pairs]) if pairs else None for version in REVISIONS}}
        for view in ("original", "adjudicated")}
    summary["policy_fingerprints"] = fingerprints
    summary["policy_unchanged"] = fingerprints == policy_fingerprints()
    if not summary["policy_unchanged"]:
        raise RuntimeError("Evaluation inputs changed during execution; comparison invalid")
    write_json(destination / "run.json", summary, key)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.generate:
        print(json.dumps({"generation_calls": 0, "model": MODEL, "generation_config": CONFIG,
                          "revisions": REVISIONS, "matrix": MATRIX, "maximum_calls": 10}, indent=2))
        return
    if not args.preflight or not args.output:
        parser.error("Generation requires reviewed --preflight and a new --output directory")
    preflight = json.loads(args.preflight.read_text(encoding="utf-8"))
    key = local_key(ROOT / ".env")
    if (preflight.get("model") != MODEL or any(preflight.get(k) is not True for k in
            ("authentication_verified", "project_association_verified", "free_tier_verified", "quota_available_verified", "generation_approved"))
            or not 0 <= time.time() - preflight.get("verified_at_unix", 0) <= 3600
            or preflight.get("credential_sha256") != digest(key.encode())
            or not all(preflight.get(k) for k in ("project_id", "association_evidence", "quota_evidence"))):
        parser.error("Generation blocked: prerequisites require current documented verification")
    result = run_matrix(args.output, key, urllib.request.urlopen)
    write_json(args.output / "preflight.json", preflight, key)
    print(json.dumps({"generation_calls": result["generation_calls"], "stop_reason": result["stop_reason"]}))


if __name__ == "__main__":
    main()
