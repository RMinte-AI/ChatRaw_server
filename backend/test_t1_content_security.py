import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend import main


ROOT = Path(__file__).resolve().parents[1]


class ContentSecurityContractTests(unittest.TestCase):
    def test_core_frontend_dependencies_are_local(self):
        markup = (ROOT / "backend/static/index.html").read_text(
            encoding="utf-8"
        )
        source = (ROOT / "backend/static/app.js").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("unpkg.com", markup)
        self.assertNotIn("unpkg.com", source)
        self.assertNotIn("cdn.jsdelivr.net", markup)
        self.assertIn("vendor/purify.min.js", markup)
        self.assertIn("ChatRawContentSecurity.renderMarkdown", source)

    def test_csv_parser_dependency_is_local(self):
        manifest = (
            ROOT / "Plugins/Plugin_market/csv-parser/manifest.json"
        ).read_text(encoding="utf-8")
        self.assertIn("/api/plugins/csv-parser/lib/papaparse.min.js", manifest)
        self.assertNotIn("cdn.jsdelivr.net", manifest)

    def test_static_and_api_responses_define_csp(self):
        with TestClient(main.app) as client:
            for path in ("/", "/health"):
                with self.subTest(path=path):
                    response = client.get(path)
                    policy = response.headers.get(
                        "content-security-policy",
                        "",
                    )
                    self.assertIn("object-src 'none'", policy)
                    self.assertIn(
                        "script-src 'self' 'unsafe-eval'",
                        policy,
                    )


if __name__ == "__main__":
    unittest.main()
