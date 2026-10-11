"""Local HTTP integration tests; extraction mocked and external network blocked."""
import http.client
import json
import os
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import ui_server as ui


class UITests(unittest.TestCase):
    def setUp(self):
        self.server = ui.ThreadingHTTPServer(("127.0.0.1", 0), ui.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.env = patch.dict(os.environ, {"GEMINI_API_KEY": "synthetic-test-key"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.network = patch("urllib.request.urlopen", side_effect=AssertionError("External calls forbidden"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method="POST", body=b"%PDF-1.4 synthetic", **headers):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        self.addCleanup(connection.close)
        default = {"Host": f"127.0.0.1:{self.server.server_port}", "X-Upload-Token": ui.TOKEN,
                   "X-Filename": "report.pdf", "Content-Length": str(len(body))}
        default.update(headers)
        connection.request(method, "/api/extract" if method == "POST" else "/api/config", body if method=="POST" else None, headers=default)
        response = connection.getresponse()
        return response.status, json.loads(response.read())

    def test_arbitrary_upload_uses_safe_temporary_path_and_preserves_values(self):
        paths = []
        expected = {"tests": [{"test_name":"Synthetic result", "value":"< 0.5", "unit":None,"reference_range":None}]}
        def extraction(path):
            paths.append(path)
            self.assertEqual(path.name, "report.pdf")
            self.assertEqual(path.read_bytes(), b"%PDF-1.4 synthetic")
            return expected
        with patch.object(ui.extract, "extract", extraction):
            status, data = self.request(**{"X-Filename":"../../anything.pdf"})
        self.assertEqual(status, 200)
        self.assertEqual(data, expected)
        self.assertFalse(paths[0].exists())

    def test_provider_failure_is_visible_and_upload_cleaned(self):
        paths = []
        def extraction(path):
            paths.append(path)
            raise RuntimeError("Gemini HTTP 503; unavailable")
        with patch.object(ui.extract, "extract", extraction):
            status, data = self.request()
        self.assertEqual(status, 502)
        self.assertNotIn("tests", data)
        self.assertFalse(paths[0].exists())

    def test_reject_invalid_uploads_before_extraction(self):
        for headers, body, expected in [({"X-Filename":"report.docx"},b"abc",415),
            ({},b"not a PDF",400), ({},b"",413), ({"Content-Length":str(ui.LIMIT+1)},b"x",413),
            ({"Content-Length":"invalid"},b"x",400)]:
            with self.subTest(expected=expected), patch.object(ui.extract,"extract") as extraction:
                status, data = self.request(body=body,**headers)
                self.assertEqual(status, expected)
                extraction.assert_not_called()

    def test_cross_origin_and_missing_token_rejected(self):
        for headers in [{"X-Upload-Token":"wrong"},{"Origin":"https://example.test"},{"Host":"example.test"}]:
            with patch.object(ui.extract,"extract") as extraction:
                status, data=self.request(**headers)
                self.assertEqual(status,403)
                extraction.assert_not_called()

    def test_config_never_returns_api_key(self):
        status, data=self.request(method="GET")
        self.assertEqual(status,200)
        self.assertTrue(data["configured"])
        self.assertNotIn("synthetic-test-key",json.dumps(data))

    def test_no_key_and_busy_fail_before_extraction(self):
        with patch.dict(os.environ,{"GEMINI_API_KEY":""}):
            self.assertEqual(self.request()[0],503)
        ui.BUSY.acquire()
        try:
            self.assertEqual(self.request()[0],409)
        finally:
            ui.BUSY.release()

    def test_images_and_empty_result_supported(self):
        for name,body in [("photo.jpg",b"\xff\xd8\xffsynthetic"),("photo.PNG",b"\x89PNG\r\n\x1a\nsynthetic")]:
            with patch.object(ui.extract,"extract",return_value={"tests":[]}):
                status,data=self.request(body=body,**{"X-Filename":name})
                self.assertEqual((status,data),(200,{"tests":[]}))


if __name__=="__main__":
    unittest.main()
