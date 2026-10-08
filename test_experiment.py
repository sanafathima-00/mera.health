"""Offline harness tests: synthetic provider responses, no real key/network."""
import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import experiment as e

KEY = "synthetic-key-for-tests"
ROW = {"test_name": "Synthetic", "value": "Negative", "unit": None, "reference_range": None}


class Response(io.BytesIO):
    status = 200
    headers = {"Date": "synthetic", "Content-Type": "application/json"}


def success(request, timeout):
    return Response(json.dumps({"candidates": [{"finishReason": "STOP", "content": {
        "parts": [{"text": json.dumps({"tests": [ROW]})}]}}],
        "usageMetadata": {"promptTokenCount": 10, "totalTokenCount": 20}}).encode())


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fake_load(self, version, dpi):
        module, digest = self.real_load(version, dpi)
        if version == "original":
            module.load_image = lambda path: ("image/png", "cGFnZTE=")
        else:
            module.load_images = lambda path: [("image/png", "cGFnZTE="), ("image/png", "cGFnZTI=")]
        return module, digest

    def run_mock(self, transport=success):
        self.real_load = e.load_revision
        with patch.object(e, "load_revision", self.fake_load):
            return e.run_matrix(self.root / "evidence", KEY, transport)

    def test_historical_modules_and_dpi(self):
        original, a = e.load_revision("original", 60)
        improved, b = e.load_revision("improved", 150)
        self.assertNotEqual(a, b)
        self.assertNotEqual(original.PROMPT, improved.PROMPT)
        self.assertEqual(original.MODEL, improved.MODEL)
        self.assertEqual(improved.DPI, 150)
        self.assertTrue(hasattr(original, "load_image"))
        self.assertTrue(hasattr(improved, "load_images"))

    def test_saved_baseline_decimal_diagnostics_serialize_without_score_change(self):
        from decimal import Decimal
        metrics = e.evaluate.evaluate(e.ROOT / "evidence/baseline_36", e.ROOT / "gold", e.ROOT / "evaluation_cases.json")
        actual = metrics["views"]["original"]["reports"]["report_01"]["field_mismatches"][0]["actual"]
        self.assertIsInstance(actual, Decimal)
        output = self.root / "metrics.json"
        e.write_json(output, metrics)
        saved = json.loads((e.ROOT / "evidence/baseline_36/metrics.json").read_text())
        serialized = json.loads(output.read_text())
        self.assertEqual(serialized["views"], saved["views"])
        self.assertEqual(serialized["report_status_counts"], saved["report_status_counts"])
        e.write_json(output, {"precise": Decimal("0.123456789012345678901234567890")})
        self.assertEqual(json.loads(output.read_text())["precise"], "0.123456789012345678901234567890")
        with self.assertRaises(TypeError):
            e.write_json(output, {"invalid": Decimal("NaN")})

    def test_matrix_order_settings_evidence_and_budget(self):
        requests = []
        def transport(request, timeout):
            requests.append((request.full_url, json.loads(request.data)["generationConfig"], timeout))
            return success(request, timeout)
        result = self.run_mock(transport)
        self.assertEqual(result["generation_calls"], 10)
        self.assertEqual(result["valid_paired_reports"], ["06", "11", "03", "08"])
        self.assertEqual(len(set((url, json.dumps(config, sort_keys=True), timeout) for url, config, timeout in requests)), 1)
        self.assertEqual([(r["report"][-2:], "original" if r["revision"] == e.REVISIONS["original"] else "improved", r["dpi"]) for r in result["attempts"]], e.MATRIX)
        original, improved = result["attempts"][:2]
        self.assertEqual(original["image_count"], 1)
        self.assertEqual(improved["image_count"], 2)
        self.assertTrue(improved["request_prompt"].startswith("Images are consecutive"))
        self.assertEqual(improved["usage"]["promptTokenCount"], 10)
        self.assertGreaterEqual(improved["latency_seconds"], 0)
        paths = list((self.root / "evidence").rglob("*"))
        self.assertTrue(any(p.name == "metrics.json" for p in paths))
        self.assertFalse(any(KEY in p.read_text() for p in paths if p.is_file()))
        # Original cleanup defect survives; the runner does not repair its output.
        saved = json.loads((self.root / "evidence/original-60/report_06.json").read_text())
        self.assertIsNone(saved["tests"][0]["value"])

    def error_transport(self, code, message="synthetic"):
        def transport(request, timeout):
            raise urllib.error.HTTPError(request.full_url, code, "synthetic", {"Retry-After": "7"},
                                         io.BytesIO(json.dumps({"error": {"message": message}}).encode()))
        return transport

    def test_two_503_stop_and_sanitized_headers(self):
        result = self.run_mock(self.error_transport(503, "high demand " + KEY))
        self.assertEqual(result["generation_calls"], 2)
        self.assertEqual(result["stop_reason"], "two_consecutive_503")
        self.assertEqual(result["attempts"][0]["category"], "overload")
        self.assertEqual(result["attempts"][0]["retry_headers"], {"Retry-After": "7"})
        self.assertEqual(result["valid_paired_reports"], [])

    def test_fatal_categories_stop_immediately(self):
        for code, message, category in [(401, "invalid", "authentication"), (400, "API_KEY_INVALID", "authentication"),
                                         (403, "billing disabled", "billing"), (429, "quota", "quota"), (403, "denied", "permission")]:
            with self.subTest(category=category):
                self.real_load = e.load_revision
                with patch.object(e, "load_revision", self.fake_load):
                    result = e.run_matrix(self.root / (category + str(code)), KEY, self.error_transport(code, message))
                self.assertEqual(result["generation_calls"], 1)
                self.assertEqual(result["stop_reason"], category)

    def test_first_pair_gate_after_transport_failure(self):
        count = 0
        def transport(request, timeout):
            nonlocal count
            count += 1
            if count == 1:
                raise TimeoutError("sensitive text")
            return success(request, timeout)
        result = self.run_mock(transport)
        self.assertEqual(result["stop_reason"], "first_pair_invalid")
        self.assertEqual(count, 2)
        self.assertEqual(result["attempts"][0]["category"], "transport")

    def test_invalid_output_rejected_and_original_silent_parse_preserved(self):
        def transport(request, timeout):
            return Response(b'{"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":"bad JSON"}]}}]}')
        result = self.run_mock(transport)
        self.assertTrue(result["attempts"][0]["schema_valid"])  # historical silent-empty behavior
        self.assertFalse(result["attempts"][1]["schema_valid"])
        self.assertEqual(result["stop_reason"], "first_pair_invalid")

    def test_dpi_requires_valid_improved_11(self):
        count = 0
        def transport(request, timeout):
            nonlocal count
            count += 1
            if count == 3:  # improved report 11
                raise TimeoutError()
            return success(request, timeout)
        result = self.run_mock(transport)
        self.assertEqual(result["generation_calls"], 8)
        self.assertNotIn("11", result["valid_paired_reports"])

    def test_existing_evidence_never_overwritten(self):
        destination = self.root / "existing"
        destination.mkdir()
        with self.assertRaises(FileExistsError):
            e.run_matrix(destination, KEY, success)

    def test_configuration_drift_prevents_call(self):
        real_load = e.load_revision
        def altered(version, dpi):
            module, sha = real_load(version, dpi)
            module.MODEL = "unapproved-model"
            module.load_images = lambda path: [("image/png", "cGFnZQ==")]
            return module, sha
        with patch.object(e, "load_revision", altered), patch("urllib.request.urlopen") as network:
            result = e.attempt("06", "improved", 60, self.root, KEY, network)
            network.assert_not_called()
        self.assertEqual(result["generation_calls"], 0)

    def test_pdf_dpi_treatments_change_only_render_resolution(self):
        for dpi in (60, 150, 300):
            module, sha = e.load_revision("improved", dpi)
            rendered_paths = []
            def render(command, **kwargs):
                self.assertEqual(command[:4], ["pdftoppm", "-r", str(dpi), "-png"])
                prefix = Path(command[-1])
                rendered_paths.append(prefix.parent)
                prefix.with_name(prefix.name + "-1.png").write_bytes(b"page one")
                prefix.with_name(prefix.name + "-2.png").write_bytes(b"page two")
            with patch.object(module.subprocess, "run", render):
                images = module.load_images(e.ROOT / "reports/report_11.pdf")
            self.assertEqual(len(images), 2)
            self.assertTrue(all(not path.exists() for path in rendered_paths))

    def test_key_loading_overrides_stale_without_exposure(self):
        env = self.root / ".env"
        env.write_text(' GEMINI_API_KEY = " synthetic-key-for-tests "\n')
        with patch.dict(os.environ, {"GEMINI_API_KEY": "stale"}):
            self.assertEqual(e.local_key(env), KEY)
        env.write_text("GEMINI_API_KEY=PASTE_YOUR_API_KEY_HERE\n")
        with self.assertRaises(ValueError):
            e.local_key(env)

    def test_cli_default_and_blocked_generation_no_network(self):
        with patch("sys.argv", ["experiment.py"]), patch("urllib.request.urlopen") as network, context_output():
            e.main()
            network.assert_not_called()
        preflight = self.root / "preflight.json"
        preflight.write_text('{}')
        with patch("sys.argv", ["experiment.py", "--generate", "--preflight", str(preflight), "--output", str(self.root / "out")]), patch.object(e, "local_key", return_value=KEY), patch("urllib.request.urlopen") as network, context_output():
            with self.assertRaises(SystemExit):
                e.main()
            network.assert_not_called()


def context_output():
    import contextlib
    stack = contextlib.ExitStack()
    stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
    stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
    return stack


if __name__ == "__main__":
    unittest.main()
