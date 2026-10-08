"""Synthetic evaluator invariants. Temporary predictions are not a baseline."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evaluate as ev

CASES = ev.read_json(ev.ROOT / "evaluation_cases.json")


def row(name="Haemoglobin", value="13.5", unit="g/dL", reference="13.0 - 17.0"):
    return {"test_name": name, "value": value, "unit": unit, "reference_range": reference}


class ScoringTests(unittest.TestCase):
    def score(self, gold, predicted):
        return ev.score_rows(gold, predicted, CASES)

    def test_exact_match(self):
        score = self.score([row()], [row()])
        self.assertEqual(score["complete_row"], {"precision": 1, "recall": 1, "f1": 1})
        self.assertTrue(all(field["over_expected"] == 1 for field in score["field_accuracy"].values()))

    def test_missing_row(self):
        score = self.score([row(), row("MCV", "80", "fL")], [row()])
        self.assertEqual(score["complete_row"]["recall"], 0.5)
        self.assertAlmostEqual(score["complete_row"]["f1"], 2 / 3)
        self.assertEqual(score["missing_gold_rows"][0]["row"], 2)
        self.assertEqual(score["field_accuracy"]["value"]["among_matched"], 1)
        self.assertEqual(score["field_accuracy"]["value"]["over_expected"], 0.5)

    def test_extra_row(self):
        score = self.score([row()], [row(), row("Invented test")])
        self.assertEqual(score["complete_row"]["precision"], 0.5)
        self.assertEqual(score["unmatched_predictions"][0]["row"], 2)

    def test_duplicate_extra_not_deduplicated(self):
        score = self.score([row()], [row(), row()])
        self.assertEqual(score["matched_rows"], 1)
        self.assertEqual(score["correct_rows"], 1)
        self.assertEqual(score["duplicate_prediction_names"], ["haemoglobin"])
        self.assertEqual(len(score["unmatched_predictions"]), 1)

    def test_duplicate_pairing_never_optimizes_values(self):
        gold = [row(value="10"), row(value="20")]
        score = self.score(gold, list(reversed(gold)))
        self.assertEqual(score["matched_rows"], 2)
        self.assertEqual(score["correct_rows"], 0)
        self.assertEqual(score["matches"], [{"gold_row": 1, "prediction_row": 1}, {"gold_row": 2, "prediction_row": 2}])

    def test_exact_name_pass_before_alias(self):
        score = self.score([row("Hb", "10"), row("Haemoglobin", "20")],
                           [row("Haemoglobin", "20"), row("Hb", "10")])
        self.assertEqual(score["correct_rows"], 2)
        self.assertTrue(score["order_violation"])

    def test_numeric_string_normalization(self):
        for value in (13.5, "13.50", " 13.500 ", "1.35e1"):
            with self.subTest(value=value):
                self.assertEqual(self.score([row()], [row(value=value)])["correct_rows"], 1)
        self.assertEqual(self.score([row()], [row(value="13.51")])["correct_rows"], 0)

    def test_indian_and_western_commas(self):
        for value in ("2,29,000", "229,000", 229000):
            with self.subTest(value=value):
                self.assertEqual(ev.scalar_key(value), ev.scalar_key("229000"))
        self.assertNotEqual(ev.scalar_key("2,29"), ev.scalar_key("229"))

    def test_qualitative_results(self):
        expected = row("Albumin", "Negative", None, "Negative")
        self.assertEqual(self.score([expected], [row("Albumin", " negative ", None, "negative")])["correct_rows"], 1)
        for value in ("Nil", "Present", "Present (+)", None):
            with self.subTest(value=value):
                self.assertEqual(self.score([expected], [row("Albumin", value, None, "Negative")])["correct_rows"], 0)
        self.assertNotEqual(ev.scalar_key("Present (+)"), ev.scalar_key("Present"))

    def test_inequality_comparator_preservation(self):
        self.assertEqual(ev.scalar_key("< 0.5"), ev.scalar_key("<0.50"))
        self.assertEqual(ev.scalar_key("≤0.5"), ev.scalar_key("<=0.5"))
        for value in ("0.5", "<=0.5", ">0.5"):
            self.assertNotEqual(ev.scalar_key("<0.5"), ev.scalar_key(value))

    def test_interval_preservation_and_grouped_bounds(self):
        self.assertEqual(ev.scalar_key("2–3"), ev.scalar_key("2 - 3.0"))
        self.assertEqual(ev.scalar_key("1,50,000 - 4,10,000"), ev.scalar_key("150000-410000"))
        self.assertEqual(ev.scalar_key("-2 - -1"), ev.scalar_key("-2.0–-1.0"))
        for value in (2, 3, "2.5", "3-2"):
            self.assertNotEqual(ev.scalar_key("2-3"), ev.scalar_key(value))

    def test_qualifier_omission_counts_wrong(self):
        score = self.score([row("CRP", "<0.5"), row("Leucocytes", "2-3")], [row("CRP", "0.5")])
        self.assertEqual(score["qualifier_expected"], 2)
        self.assertEqual(score["qualifier_correct"], 0)

    def test_null_range_and_invention(self):
        expected = row(reference=None)
        self.assertEqual(self.score([expected], [expected])["correct_rows"], 1)
        for value in ("", "null", "13-17"):
            score = self.score([expected], [row(reference=value)])
            self.assertEqual(score["correct_rows"], 0)
            self.assertEqual(score["invented_missing_ranges"], 1)

    def test_wrong_unit_not_silently_converted(self):
        score = self.score([row("Platelets", "3.03", "lakh/cumm")], [row("Platelets", "303000", "/cumm")])
        self.assertEqual(score["coverage"]["f1"], 1)
        self.assertEqual(score["complete_row"]["f1"], 0)
        self.assertEqual({error["field"] for error in score["field_mismatches"]}, {"value", "unit"})
        self.assertNotEqual(ev.unit_key("mg/dL", CASES["unit_aliases"]), ev.unit_key("mmol/L", CASES["unit_aliases"]))
        self.assertNotEqual(ev.unit_key("mM", CASES["unit_aliases"]), ev.unit_key("mm", CASES["unit_aliases"]))

    def test_unit_typography_aliases(self):
        self.assertEqual(ev.unit_key("µg/dL", {}), ev.unit_key("μg/dL", {}))
        self.assertEqual(ev.unit_key("g/dl", CASES["unit_aliases"]), "g/dL")

    def test_range_semantics(self):
        for wrong in ("<= 200", "> 200", "200", None):
            self.assertEqual(self.score([row(reference="< 200")], [row(reference=wrong)])["correct_rows"], 0)
        self.assertEqual(self.score([row(reference="13.0–17.0")], [row(reference="13 - 17")])["correct_rows"], 1)

    def test_conservative_aliases_and_specimen_qualifiers(self):
        self.assertEqual(self.score([row("MCV")], [row("Mean Corpuscular Volume")])["correct_rows"], 1)
        for expected, predicted in (("RBC", "RBC Count"), ("Albumin", "Serum Albumin"),
                                    ("T3", "Free T3"), ("FBS", "PPBS"), ("LDL-C (Direct)", "LDL-C")):
            with self.subTest(expected=expected):
                self.assertEqual(self.score([row(expected)], [row(predicted)])["matched_rows"], 0)

    def test_overlapping_aliases_rejected(self):
        cases = copy.deepcopy(CASES)
        cases["aliases"].append({"names": ["Hb"]})
        with self.assertRaises(ValueError):
            ev.alias_map(cases)

    def test_empty_extraction_is_valid_and_scored(self):
        self.assertEqual(ev.validate({"tests": []}), [])
        score = self.score([row()], [])
        self.assertIsNone(score["complete_row"]["precision"])
        self.assertEqual(score["complete_row"]["recall"], 0)
        self.assertEqual(score["complete_row"]["f1"], 0)
        empty = self.score([], [])
        self.assertTrue(empty["no_result_pass"])
        self.assertIsNone(empty["complete_row"]["f1"])

    def test_schema_types_required_fields_and_nonfinite_values(self):
        invalid = ({}, {"tests": None}, {"tests": ["row"]}, {"tests": [{}]},
                   {"tests": [row(value=True)]}, {"tests": [row(value=float("nan"))]},
                   {"tests": [row(value=float("inf"))]}, {"tests": [row(unit=3)]},
                   {"tests": [row(reference=[])]}, {"tests": [row(name=None)]})
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                ev.validate(payload)
        payload = {"tests": [{**row(), "status": "high"}], "extra": True}
        self.assertEqual(len(ev.validate(payload)), 1)

    def test_micro_macro_and_failure_penalty(self):
        good = self.score([row(), row("MCV")], [row(), row("MCV")])
        failed = self.score([row()], [])
        result = ev.aggregate([good, failed])
        self.assertAlmostEqual(result["complete_row"]["f1"], 4 / 5)
        self.assertEqual(result["macro_complete_row_f1"], 0.5)
        self.assertEqual(result["missing_rows"], 1)


class FileAndCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.predictions = Path(self.temp.name)

    def write(self, name, payload):
        (self.predictions / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def evaluate(self):
        return ev.evaluate(self.predictions, ev.ROOT / "gold", ev.ROOT / "evaluation_cases.json")

    def test_malformed_json_and_duplicate_keys(self):
        for content in ('{', '{"tests":[],"tests":[]}', '{"tests":[NaN]}', '{"tests":[1e400]}'):
            with self.subTest(content=content):
                (self.predictions / "report_01.json").write_text(content, encoding="utf-8")
                status, _, error = ev.load_prediction(self.predictions, "report_01", {})
                self.assertEqual(status, "invalid")
                self.assertTrue(error)

    def test_missing_outputs_are_unavailable_not_zero_baseline(self):
        with patch("socket.socket", side_effect=AssertionError("Offline test must not use network")):
            result = self.evaluate()
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["report_status_counts"]["unavailable"], 8)
        for view in result["views"].values():
            self.assertIsNone(view["aggregate"])
            self.assertTrue(all(score is None for score in view["reports"].values()))
        self.assertIsNone(result["cost_and_extraction_latency"])

    def test_partial_corpus_explicit_subset_only(self):
        self.write("report_01.json", {"tests": []})
        result = self.evaluate()
        self.assertEqual(result["status"], "partial")
        view = result["views"]["original"]
        self.assertIsNone(view["aggregate"])
        self.assertEqual(view["observed_subset_aggregate"]["expected_rows"], 14)
        self.assertEqual(view["observed_subset_aggregate"]["complete_row"]["f1"], 0)

    def test_failed_manifest_overrides_stale_output(self):
        self.write("report_01.json", {"tests": [row()]})
        status, predicted, _ = ev.load_prediction(self.predictions, "report_01", {"report_01": {"status": "failed", "error": "timeout"}})
        self.assertEqual((status, predicted), ("failed", []))
        self.write("run.json", {"reports": {path.stem: {"status": "failed"} for path in (ev.ROOT / "gold").glob("*.json")}})
        result = self.evaluate()
        self.assertEqual(result["report_status_counts"]["failed"], 8)
        self.assertEqual(result["views"]["original"]["aggregate"]["missing_rows"], 138)
        self.assertEqual(result["views"]["original"]["aggregate"]["complete_row"]["f1"], 0)

    def test_claimed_success_without_file_invalid(self):
        status, _, _ = ev.load_prediction(self.predictions, "report_01", {"report_01": {"status": "success"}})
        self.assertEqual(status, "invalid")

    def test_invalid_json_counts_expected_rows_as_missing(self):
        (self.predictions / "report_01.json").write_text("{", encoding="utf-8")
        result = self.evaluate()
        self.assertEqual(result["report_status_counts"]["invalid"], 1)
        score = result["views"]["original"]["reports"]["report_01"]
        self.assertEqual(len(score["missing_gold_rows"]), 14)
        self.assertEqual(score["correct_rows"], 0)

    def test_known_label_discrepancy_original_and_adjudicated_views(self):
        source_hash = ev.sha256(ev.ROOT / "gold" / "report_01.json")
        for path in (ev.ROOT / "gold").glob("*.json"):
            self.write(path.name, ev.read_json(path))  # Synthetic perfect-label fixture only.
        result = self.evaluate()
        self.assertEqual(result["views"]["original"]["aggregate"]["correct_rows"], 138)
        self.assertEqual(result["views"]["adjudicated"]["aggregate"]["correct_rows"], 137)
        corrected = ev.read_json(self.predictions / "report_01.json")
        corrected["tests"][13]["value"] = "340000"
        self.write("report_01.json", corrected)
        result = self.evaluate()
        self.assertEqual(result["views"]["original"]["aggregate"]["correct_rows"], 137)
        self.assertEqual(result["views"]["adjudicated"]["aggregate"]["correct_rows"], 138)
        self.assertEqual(ev.sha256(ev.ROOT / "gold" / "report_01.json"), source_hash)

    def test_changed_gold_invalidates_overlay(self):
        gold = ev.read_json(ev.ROOT / "gold" / "report_01.json")["tests"]
        gold[13]["value"] = "something else"
        with self.assertRaises(ValueError):
            ev.adjudicate("report_01", gold, CASES)

    def test_cli_unavailable_exit_and_valid_json(self):
        result = subprocess.run([sys.executable, "-B", str(ev.ROOT / "evaluate.py"), "score", "--predictions", str(self.predictions)], capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "unavailable")
        self.assertEqual(result.stderr, "")

    def test_cli_invalid_manifest_is_configuration_error(self):
        self.write("run.json", {"reports": {"report_01": {"status": "made_up"}}})
        result = subprocess.run([sys.executable, "-B", str(ev.ROOT / "evaluate.py"), "--predictions", str(self.predictions)], capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, "")
        self.assertEqual(json.loads(result.stderr)["status"], "evaluation_error")

    def test_manifest_root_must_be_object(self):
        self.write("run.json", [])
        with self.assertRaisesRegex(ValueError, "must be an object"):
            self.evaluate()

    def test_manifest_missing_reports_is_error(self):
        self.write("run.json", {"unrelated": []})
        with self.assertRaisesRegex(ValueError, "must contain reports"):
            self.evaluate()

    def test_invalid_unlabelled_manifest_status_is_not_ignored(self):
        self.write("run.json", {"reports": {"report_12": {"status": "unknown"}}})
        with self.assertRaisesRegex(ValueError, "Invalid run.json status"):
            self.evaluate()

    def test_cli_complete_synthetic_and_failed_exit_codes(self):
        command = [sys.executable, "-B", str(ev.ROOT / "evaluate.py"), "--predictions", str(self.predictions)]
        for path in (ev.ROOT / "gold").glob("*.json"):
            self.write(path.name, ev.read_json(path))
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["status"], "complete")
        self.write("run.json", {"reports": {"report_01": {"status": "failed", "error": "timeout"}}})
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["report_status_counts"]["failed"], 1)

    def test_json_numeric_precision_is_not_rounded_into_match(self):
        path = self.predictions / "report_01.json"
        path.write_text('{"tests":[{"test_name":"Hb","value":1.0000000000000001,"unit":null,"reference_range":null}]}', encoding="utf-8")
        loaded = ev.validate(ev.read_json(path))
        score = ev.score_rows([row("Hb", "1", None, None)], loaded, CASES)
        self.assertEqual(score["correct_rows"], 0)
        self.assertEqual(str(loaded[0]["value"]), "1.0000000000000001")

    def test_failed_empty_document_is_not_no_result_pass(self):
        gold_directory = self.predictions / "gold"
        gold_directory.mkdir()
        (gold_directory / "report_12.json").write_text('{"tests": []}', encoding="utf-8")
        self.write("run.json", {"reports": {"report_12": {"status": "failed"}}})
        result = ev.evaluate(self.predictions, gold_directory, ev.ROOT / "evaluation_cases.json")
        self.assertFalse(result["views"]["original"]["reports"]["report_12"]["no_result_pass"])

    def test_schema_validator_matches_supplied_contract(self):
        schema = ev.read_json(ev.ROOT / "schema.json")
        definition = schema["properties"]["tests"]["items"]
        self.assertEqual(set(definition["required"]), set(ev.FIELDS))
        self.assertEqual(definition["properties"]["value"]["type"], ["string", "number", "null"])
        self.assertTrue(definition["additionalProperties"])
        for path in (ev.ROOT / "gold").glob("*.json"):
            self.assertTrue(ev.validate(ev.read_json(path)))


if __name__ == "__main__":
    unittest.main()
