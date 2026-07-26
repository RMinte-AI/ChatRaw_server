import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Mount

from backend import main
from backend.frontend_assets import (
    FrontendAssetIntegrityError,
    validate_frontend_assets,
)


def write_manifest(static_dir: Path, files: dict[str, bytes]) -> None:
    assets = {}
    for asset_path, content in files.items():
        (static_dir / asset_path).parent.mkdir(parents=True, exist_ok=True)
        (static_dir / asset_path).write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        assets[asset_path] = {"sha256": digest, "version": digest}
    (static_dir / "frontend-assets.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "entrypoint": "index.html",
                "assets": assets,
            }
        ),
        encoding="utf-8",
    )


class FrontendAssetIntegrityTests(unittest.TestCase):
    def test_release_manifest_covers_the_complete_static_directory(self):
        static_dir = Path(main.BACKEND_DIR, "static")
        manifest = json.loads(
            (static_dir / "frontend-assets.json").read_text(encoding="utf-8")
        )
        actual_assets = {
            path.relative_to(static_dir).as_posix()
            for path in static_dir.rglob("*")
            if path.is_file() and path.name != "frontend-assets.json"
        }
        self.assertEqual(set(manifest["assets"]), actual_assets)
        for html_name in ("login.html", "setup.html"):
            html = (static_dir / html_name).read_text(encoding="utf-8")
            for asset_name in ("auth.css", "auth.js"):
                version = manifest["assets"][asset_name]["version"]
                self.assertIn(f"/{asset_name}?v={version}", html)

    def test_valid_manifest_returns_cache_versions(self):
        with tempfile.TemporaryDirectory() as temporary:
            static_dir = Path(temporary)
            write_manifest(
                static_dir,
                {
                    "index.html": b"<html></html>",
                    "app.min.js": b"window.app = true;",
                },
            )
            versions = validate_frontend_assets(static_dir)
            self.assertEqual(
                versions["app.min.js"],
                hashlib.sha256(b"window.app = true;").hexdigest(),
            )

    def test_mixed_or_missing_assets_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            static_dir = Path(temporary)
            write_manifest(
                static_dir,
                {
                    "index.html": b"<html></html>",
                    "app.min.js": b"release-a",
                },
            )
            (static_dir / "app.min.js").write_bytes(b"release-b")
            with self.assertRaises(FrontendAssetIntegrityError):
                validate_frontend_assets(static_dir)

            (static_dir / "app.min.js").unlink()
            with self.assertRaises(FrontendAssetIntegrityError):
                validate_frontend_assets(static_dir)

    def test_manifest_rejects_paths_outside_static_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            static_dir = Path(temporary)
            content = b"outside"
            digest = hashlib.sha256(content).hexdigest()
            (static_dir / "index.html").write_bytes(b"<html></html>")
            index_digest = hashlib.sha256(b"<html></html>").hexdigest()
            (static_dir / "frontend-assets.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "entrypoint": "index.html",
                        "assets": {
                            "index.html": {
                                "sha256": index_digest,
                                "version": index_digest,
                            },
                            "../outside.js": {
                                "sha256": digest,
                                "version": digest,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(FrontendAssetIntegrityError):
                validate_frontend_assets(static_dir)


class FrontendAssetCacheTests(unittest.TestCase):
    def test_only_manifest_versioned_asset_is_immutable(self):
        static_dir = Path(main.BACKEND_DIR, "static")
        manifest = json.loads(
            (static_dir / "frontend-assets.json").read_text(encoding="utf-8")
        )
        version = manifest["assets"]["app.min.js"]["version"]
        main.FRONTEND_ASSET_VERSIONS = validate_frontend_assets(static_dir)
        static_app = main.CachedStaticFiles(
            directory=static_dir,
            html=True,
        )
        app = Starlette(routes=[Mount("/", app=static_app)])
        with TestClient(app) as client:
            versioned = client.get(f"/app.min.js?v={version}")
            unversioned = client.get("/app.min.js")
            wrong = client.get("/app.min.js?v=stale")
            html = client.get("/")

        self.assertEqual(versioned.status_code, 200)
        self.assertEqual(
            versioned.headers["cache-control"],
            "public, max-age=31536000, immutable",
        )
        self.assertEqual(
            unversioned.headers["cache-control"],
            "no-cache, must-revalidate",
        )
        self.assertEqual(
            wrong.headers["cache-control"],
            "no-cache, must-revalidate",
        )
        self.assertEqual(
            html.headers["cache-control"],
            "no-cache, must-revalidate",
        )


if __name__ == "__main__":
    unittest.main()
