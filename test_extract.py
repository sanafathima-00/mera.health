"""Offline extractor regressions: provider calls are always mocked."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import extract
import evaluate


def row(value=None, **changes):
    result = {"test_name": "LDL-C (Direct)", "value": value,
              "unit": None, "reference_range": None}
    result.update(changes)
    return result


def response(text='{"tests": []}', **changes):
    result = {"candidates": [{"finishReason": "STOP",
                             "content": {"parts": [{"text": text}]}}]}
    result.update(changes)
    return io.BytesIO(json.dumps(result).encode())


class ValueTests(unittest.TestCase):
    def test_meaningful_values_preserved(self):
        for value in ["Negative", "Present (+)", "Dark Yellow", "< 0.5", "> 100",
                      "2-3", "2–3", "≤0.5", "2,29,000", "229,000", "13.50",
                      "2,29", "", "null", "NaN", None, 0, -2, 13.5]:
            with self.subTest(value=value):
                self.assertEqual(extract.clean([row(value)])[0]["value"], value)

    def test_grouped_numbers_keep_magnitude(self):
        for value in ["2,29,000", "229,000"]:
            kept = extract.clean([row(value)])[0]["value"]
            self.assertEqual(evaluate.scalar_key(kept), evaluate.scalar_key(229000))

    def test_units_ranges_names_and_nulls_unchanged(self):
        original = row("< 0.5", unit="lakh/cumm", reference_range="< 1.0")
        self.assertEqual(extract.clean([original]), [original])
        self.assertEqual(extract.clean([row()]), [row()])

    def test_non_finite_numeric_values_rejected(self):
        for value in [float('nan'), float('inf'), -float('inf')]:
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                extract.clean([row(value)])

    def test_invalid_value_types_rejected(self):
        for value in [True, [], {}]:
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                extract.clean([row(value)])

    def test_invalid_row_shapes_rejected(self):
        for rows in [None, {}, "tests", [None], [1], [[]], [{}],
                     [row(test_name=None)], [row(test_name=" ")], [row(unit=5)], [row(reference_range=[])]]:
            with self.subTest(rows=rows), self.assertRaises(RuntimeError):
                extract.clean(rows)

    def test_each_required_field_is_required(self):
        for field in row():
            incomplete = row(); del incomplete[field]
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                extract.clean([incomplete])

    def test_no_partial_success(self):
        with self.assertRaises(RuntimeError):
            extract.clean([row(1), {}])

    def test_extra_status_not_inferred_or_emitted(self):
        self.assertEqual(extract.clean([row(1, status="high")]), [row(1)])

    def test_saved_successful_baseline_fixtures_preserve_fields(self):
        for name in ['report_01', 'report_08']:
            payload = evaluate.read_json(Path('evidence/baseline_36') / (name + '.json'))
            # These fixtures use finite integral/fractional JSON numbers.
            payload = json.loads(json.dumps(payload, default=float))
            actual = extract.parse(json.dumps(payload))
            self.assertEqual(actual, [{f: r[f] for f in evaluate.FIELDS} for r in payload['tests']])
            evaluate.validate({'tests': actual})


class ParseTests(unittest.TestCase):
    def test_plain_and_fenced_json(self):
        text = json.dumps({'tests': [row('Present (+)')]})
        for wrapped in [text, '  ' + text + '\n', '```json\n' + text + '\n```',
                        '```\n' + text + '\n```']:
            with self.subTest(wrapped=wrapped):
                self.assertEqual(extract.parse(wrapped), [row('Present (+)')])

    def test_genuine_empty_document(self):
        self.assertEqual(extract.parse('{"tests": []}'), [])

    def test_malformed_or_wrapped_prose_rejected(self):
        for text in ['', '{', 'Here: {"tests": []}', '{"tests": []} trailing',
                     '{"tests": []}{"tests": []}', '```json\n{"tests": []}',
                     '{"tests": [],}', '[]', 'null', '{}', '{"tests": null}']:
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                extract.parse(text)

    def test_duplicate_keys_rejected(self):
        for text in ['{"tests": [], "tests": []}',
                     '{"tests": [{"test_name": "X", "test_name": "Y"}]}']:
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                extract.parse(text)

    def test_non_finite_json_rejected(self):
        for value in ['NaN', 'Infinity', '-Infinity', '1e999']:
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                extract.parse('{"tests": [' + json.dumps(row()).replace('"value": null', '"value": ' + value) + ']}')


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'GEMINI_API_KEY': 'offline-test-placeholder'})
        self.env.start(); self.addCleanup(self.env.stop)

    def test_request_and_thought_filter(self):
        parts = [{'text': 'private reasoning', 'thought': True}, {'text': '{"tests": []}'}]
        with patch('urllib.request.urlopen', return_value=response(candidates=[{
                'finishReason': 'STOP', 'content': {'parts': parts}}])) as opener:
            self.assertEqual(extract.call_model('image/png', 'synthetic'), '{"tests": []}')
        request = opener.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(body['generationConfig'], {'temperature': 0, 'maxOutputTokens': 16000})
        self.assertEqual(body['contents'][0]['parts'][1]['text'], extract.PROMPT)
        self.assertEqual(opener.call_count, 1)

    def test_missing_key_no_call(self):
        with patch.dict(os.environ, {}, clear=True), patch('urllib.request.urlopen') as opener:
            with self.assertRaises(RuntimeError): extract.call_model('image/png', 'synthetic')
            opener.assert_not_called()

    def test_http_connection_and_timeout_failures(self):
        for error in [urllib.error.HTTPError('https://example.invalid', 503, 'unavailable', {}, None),
                      urllib.error.URLError('offline'), TimeoutError()]:
            with self.subTest(error=type(error).__name__), patch('urllib.request.urlopen', side_effect=error):
                with self.assertRaises(RuntimeError): extract.call_model('image/png', 'synthetic')

    def test_provider_invalid_json(self):
        with patch('urllib.request.urlopen', return_value=io.BytesIO(b'not json')):
            with self.assertRaises(RuntimeError): extract.call_model('image/png', 'synthetic')

    def test_missing_or_invalid_candidate(self):
        for candidates in [None, [], {}, [None], [{}],
                           [{'finishReason': 'MAX_TOKENS'}], [{'finishReason': 'SAFETY'}],
                           [{'finishReason': 'STOP', 'content': None}],
                           [{'finishReason': 'STOP', 'content': {'parts': [None]}}],
                           [{'finishReason': 'STOP', 'content': {'parts': [{'text': None}]}}],
                           [{'finishReason': 'STOP', 'content': {'parts': []}}]]:
            with self.subTest(candidates=candidates), patch('urllib.request.urlopen', return_value=response(candidates=candidates)):
                with self.assertRaises(RuntimeError): extract.call_model('image/png', 'synthetic')


class CliTests(unittest.TestCase):
    def test_real_cli_missing_key_has_stderr_and_no_success_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.png'; path.write_bytes(b'synthetic')
            env = os.environ.copy(); env.pop('GEMINI_API_KEY', None)
            result = subprocess.run([sys.executable, '-B', 'extract.py', str(path)],
                                    env=env, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertIn('No API call made', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def run_cli(self, provider):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.png'; path.write_bytes(b'synthetic')
            out, err = io.StringIO(), io.StringIO()
            with patch.object(sys, 'argv', ['extract.py', str(path)]), \
                 patch.dict(os.environ, {'GEMINI_API_KEY': 'offline-test-placeholder'}), \
                 patch('urllib.request.urlopen', return_value=provider), \
                 contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try: runpy.run_path('extract.py', run_name='__main__'); code = 0
                except SystemExit as failure: code = failure.code
            return code, out.getvalue(), err.getvalue()

    def test_cli_success_schema_valid(self):
        code, stdout, _ = self.run_cli(response(json.dumps({'tests': [row('Dark Yellow')]})))
        self.assertEqual(code, 0)
        self.assertEqual(evaluate.validate(json.loads(stdout)), [row('Dark Yellow')])

    def test_cli_empty_is_success(self):
        code, stdout, _ = self.run_cli(response())
        self.assertEqual(code, 0); self.assertEqual(json.loads(stdout), {'tests': []})

    def test_cli_invalid_output_is_nonzero_without_success_json(self):
        for text in ['not JSON', '{"tests": [{}]}']:
            with self.subTest(text=text):
                code, stdout, _ = self.run_cli(response(text))
                self.assertNotEqual(code, 0); self.assertEqual(stdout, '')

    def test_cli_provider_failure_is_not_empty_success(self):
        code, stdout, _ = self.run_cli(response(candidates=[]))
        self.assertNotEqual(code, 0); self.assertEqual(stdout, '')

    def test_pdf_command_still_first_page_60_dpi(self):
        with patch('subprocess.run') as convert, patch.object(Path, 'read_bytes', return_value=b'png'):
            extract.load_image(Path('synthetic.pdf'))
        command = convert.call_args.args[0]
        self.assertEqual(command[1:9], ['-f', '1', '-l', '1', '-singlefile', '-r', '60', '-png'])


if __name__ == '__main__':
    unittest.main()
