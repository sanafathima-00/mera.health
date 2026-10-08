"""Score saved extraction JSON offline. No extractor imports or provider calls."""

import argparse
import copy
import hashlib
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIELDS = ("test_name", "value", "unit", "reference_range")
NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
GROUPED = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3})(?:\.\d+)?"


def text(value):
    return " ".join(unicodedata.normalize("NFKC", value).split())


def name_key(value):
    return text(value).casefold()


def scalar_key(value):
    """Normalize representation, never clinical meaning or unit scale."""
    if value is None:
        return ("null",)
    if isinstance(value, bool):
        raise ValueError("Boolean is not a lab value")
    value = text(str(value)).translate(str.maketrans({"–": "-", "−": "-", "≤": "<=", "≥": ">="}))
    # Only remove syntactically valid digit grouping, including within bounds.
    atom = rf"(?:{GROUPED}|{NUMBER})"

    def decimal(token):
        return Decimal(token.replace(",", ""))

    if re.fullmatch(atom, value):
        return ("number", decimal(value))
    match = re.fullmatch(rf"(<=|>=|<|>)\s*({atom})", value)
    if match:
        return ("inequality", match[1], decimal(match[2]))
    match = re.fullmatch(rf"({atom})\s*-\s*({atom})", value)
    if match:
        return ("interval", decimal(match[1]), decimal(match[2]))
    return ("text", value.casefold())


def unit_key(value, aliases):
    if value is None:
        return None
    value = text(value)  # NFKC makes micro sign µ and Greek μ equivalent.
    return aliases.get(value, value)


def reject_constant(value):
    raise ValueError(f"Non-finite JSON number: {value}")


def finite_decimal(value):
    number = Decimal(value)
    if not number.is_finite() or not math.isfinite(float(number)):
        raise ValueError("Non-finite JSON number")
    return number


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=reject_constant,
                      parse_float=finite_decimal, object_pairs_hook=unique_object)


def validate(payload):
    """Validate the supplied schema's shape; extras are explicitly allowed."""
    if not isinstance(payload, dict) or not isinstance(payload.get("tests"), list):
        raise ValueError("Expected an object with a tests array")
    for index, row in enumerate(payload["tests"], 1):
        if not isinstance(row, dict) or not all(field in row for field in FIELDS):
            raise ValueError(f"Row {index}: missing required fields or non-object row")
        if not isinstance(row["test_name"], str):
            raise ValueError(f"Row {index}: test_name must be a string")
        value = row["value"]
        if value is not None and (isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal))):
            raise ValueError(f"Row {index}: invalid value type")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"Row {index}: non-finite value")
        if isinstance(value, Decimal) and not value.is_finite():
            raise ValueError(f"Row {index}: non-finite value")
        for field in ("unit", "reference_range"):
            if row[field] is not None and not isinstance(row[field], str):
                raise ValueError(f"Row {index}: {field} must be string or null")
    return payload["tests"]


def alias_map(cases):
    result = {}
    for index, group in enumerate(cases["aliases"]):
        for name in group["names"]:
            key = name_key(name)
            if key in result:
                raise ValueError(f"Overlapping alias: {name}")
            result[key] = index
    return result


def match_rows(gold, predicted, aliases):
    """Exact names first, aliases second. Never optimize using result fields."""
    pairs = []
    used_gold, used_predictions = set(), set()
    for alias_pass in (False, True):
        for gi, expected in enumerate(gold):
            if gi in used_gold:
                continue
            expected_key = name_key(expected["test_name"])
            if not expected_key:
                continue
            for pi, actual in enumerate(predicted):
                if pi in used_predictions:
                    continue
                actual_key = name_key(actual["test_name"])
                equal = actual_key == expected_key
                if alias_pass:
                    equal = expected_key in aliases and actual_key in aliases and aliases[expected_key] == aliases[actual_key]
                if equal:
                    pairs.append((gi, pi))
                    used_gold.add(gi)
                    used_predictions.add(pi)
                    break
    return sorted(pairs), [i for i in range(len(gold)) if i not in used_gold], [i for i in range(len(predicted)) if i not in used_predictions]


def rates(correct, predicted, expected):
    if expected == 0:
        return {"precision": None, "recall": None, "f1": None}
    return {"precision": correct / predicted if predicted else None,
            "recall": correct / expected,
            "f1": 2 * correct / (predicted + expected)}


def score_rows(gold, predicted, cases):
    pairs, missing, extra = match_rows(gold, predicted, alias_map(cases))
    correct_fields = dict.fromkeys(FIELDS, 0)
    mismatches, complete, exact_names = [], 0, 0
    qualifier_expected = sum(scalar_key(row["value"])[0] in ("inequality", "interval", "text") for row in gold)
    qualifier_correct, invented_ranges = 0, 0
    for gi, pi in pairs:
        expected, actual = gold[gi], predicted[pi]
        equality = {"test_name": True,
                    "value": scalar_key(expected["value"]) == scalar_key(actual["value"]),
                    "unit": unit_key(expected["unit"], cases["unit_aliases"]) == unit_key(actual["unit"], cases["unit_aliases"]),
                    "reference_range": scalar_key(expected["reference_range"]) == scalar_key(actual["reference_range"])}
        exact_names += name_key(expected["test_name"]) == name_key(actual["test_name"])
        complete += all(equality.values())
        qualifier_correct += equality["value"] and scalar_key(expected["value"])[0] in ("inequality", "interval", "text")
        invented_ranges += expected["reference_range"] is None and actual["reference_range"] is not None
        for field, equal in equality.items():
            correct_fields[field] += equal
            if not equal:
                mismatches.append({"gold_row": gi + 1, "prediction_row": pi + 1,
                                   "field": field, "expected": expected[field], "actual": actual[field]})
    prediction_order = [pi for _, pi in pairs]
    duplicate_names = sorted(key for key, count in Counter(name_key(row["test_name"]) for row in predicted).items() if count > 1)
    return {"expected_rows": len(gold), "predicted_rows": len(predicted), "matched_rows": len(pairs),
            "correct_rows": complete, "coverage": rates(len(pairs), len(predicted), len(gold)),
            "complete_row": rates(complete, len(predicted), len(gold)),
            "field_accuracy": {field: {"correct": count, "matched_denominator": len(pairs),
                                      "expected_denominator": len(gold),
                                      "among_matched": count / len(pairs) if pairs else None,
                                      "over_expected": count / len(gold) if gold else None}
                               for field, count in correct_fields.items()},
            "missing_gold_rows": [{"row": i + 1, "data": gold[i]} for i in missing],
            "unmatched_predictions": [{"row": i + 1, "data": predicted[i]} for i in extra],
            "field_mismatches": mismatches, "matches": [{"gold_row": gi + 1, "prediction_row": pi + 1} for gi, pi in pairs],
            "exact_name_matches": exact_names, "duplicate_prediction_names": duplicate_names,
            "order_violation": prediction_order != sorted(prediction_order),
            "qualifier_expected": qualifier_expected, "qualifier_correct": qualifier_correct,
            "invented_missing_ranges": invented_ranges,
            "no_result_pass": not gold and not predicted}


def adjudicate(report, gold, cases):
    result = copy.deepcopy(gold)
    for correction in cases["adjudications"]:
        if correction["report"] != report:
            continue
        row = result[correction["row"] - 1]
        if row["test_name"] != correction["test_name"] or row[correction["field"]] != correction["original"]:
            raise ValueError(f"Adjudication source changed: {report}")
        row[correction["field"]] = correction["corrected"]
    return result


def load_prediction(directory, report, statuses):
    entry = statuses.get(report)
    if entry is not None:
        if not isinstance(entry, dict) or entry.get("status") not in ("success", "failed"):
            raise ValueError(f"Invalid run.json status for {report}")
        if entry["status"] == "failed":
            return "failed", [], str(entry.get("error", "Recorded extraction failure"))
    path = directory / f"{report}.json"
    if not path.exists():
        if entry:
            return "invalid", [], "Manifest claims success, but prediction file is absent"
        return "unavailable", [], "Saved prediction absent; baseline outputs are required"
    try:
        return "valid", validate(read_json(path)), None
    except (OSError, ValueError) as error:
        return "invalid", [], str(error)


def aggregate(reports):
    totals = {key: sum(row[key] for row in reports) for key in
              ("expected_rows", "predicted_rows", "matched_rows", "correct_rows", "qualifier_expected", "qualifier_correct", "invented_missing_ranges", "exact_name_matches")}
    totals["coverage"] = rates(totals["matched_rows"], totals["predicted_rows"], totals["expected_rows"])
    totals["complete_row"] = rates(totals["correct_rows"], totals["predicted_rows"], totals["expected_rows"])
    f1s = [row["complete_row"]["f1"] for row in reports if row["complete_row"]["f1"] is not None]
    totals["macro_complete_row_f1"] = sum(f1s) / len(f1s) if f1s else None
    totals["field_accuracy"] = {}
    for field in FIELDS:
        correct = sum(row["field_accuracy"][field]["correct"] for row in reports)
        totals["field_accuracy"][field] = {"correct": correct,
                                         "matched_denominator": totals["matched_rows"],
                                         "expected_denominator": totals["expected_rows"],
                                         "among_matched": correct / totals["matched_rows"] if totals["matched_rows"] else None,
                                         "over_expected": correct / totals["expected_rows"] if totals["expected_rows"] else None}
    totals["missing_rows"] = sum(len(row["missing_gold_rows"]) for row in reports)
    totals["unsupported_rows"] = sum(len(row["unmatched_predictions"]) for row in reports)
    return totals


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(predictions, gold_directory, cases_path):
    cases = read_json(cases_path)
    alias_map(cases)
    manifest = predictions / "run.json"
    manifest_data = read_json(manifest) if manifest.exists() else {}
    if not isinstance(manifest_data, dict):
        raise ValueError("run.json must be an object")
    if manifest.exists() and "reports" not in manifest_data:
        raise ValueError("run.json must contain reports")
    statuses = manifest_data.get("reports", {})
    if not isinstance(statuses, dict):
        raise ValueError("run.json reports must be an object keyed by report ID")
    for report, entry in statuses.items():
        if not isinstance(entry, dict) or entry.get("status") not in ("success", "failed"):
            raise ValueError(f"Invalid run.json status for {report}")
    gold_paths = sorted(gold_directory.glob("report_*.json"))
    if not gold_paths:
        raise ValueError("No gold report JSON files found")
    reports = []
    views = {"original": {}, "adjudicated": {}}
    for path in gold_paths:
        gold = validate(read_json(path))
        status, predicted, error = load_prediction(predictions, path.stem, statuses)
        reports.append({"report": path.stem, "status": status, "error": error})
        for view in views:
            expected = gold if view == "original" else adjudicate(path.stem, gold, cases)
            score = None if status == "unavailable" else score_rows(expected, predicted, cases)
            if score is not None and status != "valid":
                score["no_result_pass"] = False
            views[view][path.stem] = score
    counts = {status: sum(row["status"] == status for row in reports) for status in ("valid", "invalid", "failed", "unavailable")}
    availability = "unavailable" if counts["unavailable"] == len(reports) else "partial" if counts["unavailable"] else "complete"
    output_views = {}
    for view, scores in views.items():
        observed = [score for score in scores.values() if score is not None]
        output_views[view] = {"reports": scores,
                              "aggregate": aggregate(observed) if availability == "complete" else None,
                              "observed_subset_aggregate": aggregate(observed) if observed and availability == "partial" else None}
    files = [Path(__file__), cases_path, ROOT / "schema.json", *gold_paths]
    output = {"status": availability, "measurement": "Saved predictions only; evaluator does not run extraction",
              "message": "Scoring requires baseline outputs; missing predictions are not measured failures" if counts["unavailable"] else "All supplied report attempts accounted for",
              "report_status_counts": counts, "reports": reports, "views": output_views,
              "policy_version": cases["policy_version"], "adjudications": cases["adjudications"],
              "unlabelled_reports": {"reports": cases["unlabelled_reports"], "status": cases["unlabelled_status"]},
              "cost_and_extraction_latency": None,
              "fingerprints": {str(path.resolve()): sha256(path) for path in files},
              "prediction_fingerprints": {path.name: sha256(path) for path in sorted(predictions.glob("report_*.json"))},
              "manifest_sha256": sha256(manifest) if manifest.exists() else None}
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["score"], nargs="?", default="score")
    parser.add_argument("--predictions", type=Path, default=ROOT / "evidence" / "baseline")
    parser.add_argument("--gold", type=Path, default=ROOT / "gold")
    parser.add_argument("--cases", type=Path, default=ROOT / "evaluation_cases.json")
    args = parser.parse_args()
    try:
        output = evaluate(args.predictions, args.gold, args.cases)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        print(json.dumps({"status": "evaluation_error", "error": str(error)}), file=sys.stderr)
        return 3
    # ASCII JSON escapes are safe under Windows pipe encodings; decimals in
    # diagnostic source rows remain exact decimal strings rather than floats.
    print(json.dumps(output, indent=2, allow_nan=False, default=str))
    if output["report_status_counts"]["unavailable"]:
        return 2
    return 1 if output["report_status_counts"]["invalid"] or output["report_status_counts"]["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
