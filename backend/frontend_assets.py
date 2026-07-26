from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath


ASSET_MANIFEST_FILENAME = "frontend-assets.json"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class FrontendAssetIntegrityError(RuntimeError):
    pass


def _safe_asset_path(static_dir: Path, asset_path: str) -> Path:
    relative = PurePosixPath(asset_path)
    if (
        not asset_path
        or relative.is_absolute()
        or ".." in relative.parts
        or str(relative) != asset_path
    ):
        raise FrontendAssetIntegrityError(
            "frontend asset manifest contains an invalid path"
        )
    resolved = static_dir.joinpath(*relative.parts).resolve()
    try:
        resolved.relative_to(static_dir.resolve())
    except ValueError as error:
        raise FrontendAssetIntegrityError(
            "frontend asset manifest path escapes the static directory"
        ) from error
    return resolved


def validate_frontend_assets(static_dir: Path) -> dict[str, str]:
    manifest_path = static_dir / ASSET_MANIFEST_FILENAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FrontendAssetIntegrityError(
            "frontend asset manifest is missing or invalid"
        ) from error

    if (
        not isinstance(manifest, dict)
        or set(manifest) != {"schema_version", "entrypoint", "assets"}
        or manifest["schema_version"] != "1"
        or manifest["entrypoint"] != "index.html"
        or not isinstance(manifest["assets"], dict)
        or "index.html" not in manifest["assets"]
    ):
        raise FrontendAssetIntegrityError(
            "frontend asset manifest has an unsupported shape"
        )

    versions: dict[str, str] = {}
    for asset_path, metadata in manifest["assets"].items():
        if (
            not isinstance(asset_path, str)
            or not isinstance(metadata, dict)
            or set(metadata) != {"sha256", "version"}
            or not isinstance(metadata["sha256"], str)
            or not SHA256_PATTERN.fullmatch(metadata["sha256"])
            or not isinstance(metadata["version"], str)
            or not SHA256_PATTERN.fullmatch(metadata["version"])
        ):
            raise FrontendAssetIntegrityError(
                "frontend asset manifest contains invalid metadata"
            )
        file_path = _safe_asset_path(static_dir, asset_path)
        try:
            actual_sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()
        except OSError as error:
            raise FrontendAssetIntegrityError(
                "frontend asset file is missing"
            ) from error
        if actual_sha256 != metadata["sha256"]:
            raise FrontendAssetIntegrityError(
                "frontend asset file does not match its manifest"
            )
        versions[asset_path] = metadata["version"]

    return versions
