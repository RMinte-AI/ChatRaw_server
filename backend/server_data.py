import argparse
import base64
import hashlib
import json
import os
import shutil
import sqlite3
import struct
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from .db_migrations import (
        LATEST_SCHEMA_VERSION,
        apply_migrations,
        current_schema_version,
    )
    from .db_runtime import open_database
except ImportError:
    from db_migrations import (
        LATEST_SCHEMA_VERSION,
        apply_migrations,
        current_schema_version,
    )
    from db_runtime import open_database


MANIFEST_VERSION = 1
DATABASE_NAME = "chatraw.db"
EPHEMERAL_DATABASE_SUFFIXES = ("-wal", "-shm")


class DataOperationError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_file_manifest(root: Path) -> list[dict[str, Any]]:
    files = []
    if not root.exists():
        return files
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise DataOperationError(f"symbolic links are not supported: {path}")
        if not path.is_file():
            continue
        if path.name.endswith(EPHEMERAL_DATABASE_SUFFIXES):
            continue
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return files


def _json_value(
    value: Any,
    *,
    table: str,
    column: str,
    normalize_legacy_embeddings: bool,
) -> Any:
    if (
        normalize_legacy_embeddings
        and table == "document_chunks"
        and column == "embedding"
        and value is not None
    ):
        if isinstance(value, str):
            try:
                values = json.loads(value)
            except json.JSONDecodeError:
                values = value
        elif isinstance(value, bytes) and len(value) % 4 == 0:
            count = len(value) // 4
            values = list(struct.unpack(f"{count}f", value))
        else:
            values = value
        return {"type": "embedding", "values": values}
    if isinstance(value, bytes):
        return {
            "type": "blob",
            "base64": base64.b64encode(value).decode("ascii"),
        }
    return value


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def database_snapshot(
    db_path: Path,
    *,
    columns_by_table: Optional[dict[str, list[str]]] = None,
    normalize_legacy_embeddings: bool = False,
) -> dict[str, Any]:
    connection = open_database(str(db_path), read_only=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise DataOperationError(
                f"database integrity check failed: {integrity}"
            )

        if columns_by_table is None:
            tables = [
                row["name"]
                for row in connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                      AND name NOT LIKE 'sqlite_%'
                    ORDER BY name
                    """
                )
            ]
        else:
            tables = sorted(columns_by_table)

        table_snapshots = {}
        for table in tables:
            if columns_by_table is None:
                columns = [
                    row["name"]
                    for row in connection.execute(
                        f"PRAGMA table_info({_quote_identifier(table)})"
                    )
                ]
            else:
                columns = columns_by_table[table]

            column_sql = ", ".join(
                _quote_identifier(column) for column in columns
            )
            rows = connection.execute(
                f"SELECT {column_sql} "
                f"FROM {_quote_identifier(table)} ORDER BY rowid"
            ).fetchall()
            digest = hashlib.sha256()
            for row in rows:
                encoded = json.dumps(
                    [
                        _json_value(
                            row[column],
                            table=table,
                            column=column,
                            normalize_legacy_embeddings=(
                                normalize_legacy_embeddings
                            ),
                        )
                        for column in columns
                    ],
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                digest.update(encoded)
                digest.update(b"\n")
            table_snapshots[table] = {
                "columns": columns,
                "count": len(rows),
                "sha256": digest.hexdigest(),
            }

        return {
            "integrity": integrity,
            "schema_version": current_schema_version(connection),
            "tables": table_snapshots,
        }
    finally:
        connection.close()


def _validate_distinct_paths(source: Path, destination: Path) -> None:
    source = source.resolve()
    destination = destination.resolve()
    if source == destination:
        raise DataOperationError("source and destination must be different")
    if destination.is_relative_to(source):
        raise DataOperationError("destination must not be inside source")


def _require_new_destination(destination: Path) -> None:
    if destination.exists():
        raise DataOperationError(
            f"destination already exists; refusing to overwrite: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)


def _require_quiesced(confirmed: bool) -> None:
    if not confirmed:
        raise DataOperationError(
            "the source or destination service must be stopped; "
            "repeat with explicit quiesced confirmation"
        )


def _copy_sqlite_snapshot(source_db: Path, destination_db: Path) -> None:
    source = open_database(str(source_db), read_only=True)
    destination = sqlite3.connect(str(destination_db))
    try:
        source.backup(destination)
        destination.commit()
    finally:
        destination.close()
        source.close()


def _copy_non_database_data(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for child in sorted(source.iterdir()):
        if child.name == DATABASE_NAME:
            continue
        if child.name.startswith(f"{DATABASE_NAME}-"):
            continue
        if child.is_symlink():
            raise DataOperationError(
                f"symbolic links are not supported: {child}"
            )
        target = destination / child.name
        if child.is_dir():
            shutil.copytree(child, target)
        elif child.is_file():
            shutil.copy2(child, target)


def _atomic_directory(operation: str, destination: Path):
    _require_new_destination(destination)
    return Path(
        tempfile.mkdtemp(
            prefix=f".chatraw-{operation}-",
            dir=destination.parent,
        )
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _finalize_sqlite(db_path: Path) -> None:
    connection = open_database(str(db_path))
    try:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        connection.close()
    for suffix in ("-wal", "-shm"):
        supporting_file = Path(str(db_path) + suffix)
        if supporting_file.exists():
            supporting_file.unlink()


def _legacy_owner_counts(db_path: Path) -> dict[str, int]:
    connection = open_database(str(db_path), read_only=True)
    try:
        return {
            "chats_non_null": connection.execute(
                "SELECT COUNT(*) FROM chats WHERE owner_user_id IS NOT NULL"
            ).fetchone()[0],
            "messages_non_null": connection.execute(
                "SELECT COUNT(*) FROM messages WHERE author_user_id IS NOT NULL"
            ).fetchone()[0],
            "documents_non_null": connection.execute(
                """
                SELECT COUNT(*)
                FROM documents
                WHERE uploader_user_id IS NOT NULL
                """
            ).fetchone()[0],
        }
    finally:
        connection.close()


def import_classic_data(
    source_data_dir: Path,
    server_data_dir: Path,
    *,
    source_quiesced: bool,
) -> dict[str, Any]:
    _require_quiesced(source_quiesced)
    source_data_dir = source_data_dir.resolve()
    server_data_dir = server_data_dir.resolve()
    _validate_distinct_paths(source_data_dir, server_data_dir)
    source_db = source_data_dir / DATABASE_NAME
    if not source_db.is_file():
        raise DataOperationError(f"classic database not found: {source_db}")

    source_files_before = _relative_file_manifest(source_data_dir)
    source_database = database_snapshot(
        source_db,
        normalize_legacy_embeddings=True,
    )
    source_columns = {
        table: snapshot["columns"]
        for table, snapshot in source_database["tables"].items()
    }

    staging = _atomic_directory("import", server_data_dir)
    try:
        target_db = staging / DATABASE_NAME
        _copy_sqlite_snapshot(source_db, target_db)
        _copy_non_database_data(source_data_dir, staging)

        migration_connection = open_database(str(target_db))
        try:
            apply_migrations(migration_connection)
        finally:
            migration_connection.close()
        _finalize_sqlite(target_db)

        migrated_database = database_snapshot(
            target_db,
            columns_by_table=source_columns,
            normalize_legacy_embeddings=True,
        )
        if source_database["tables"] != migrated_database["tables"]:
            raise DataOperationError(
                "classic database content changed during migration"
            )

        owner_counts = _legacy_owner_counts(target_db)
        if any(owner_counts.values()):
            raise DataOperationError(
                "legacy ownership fields must remain NULL"
            )

        source_files_after = _relative_file_manifest(source_data_dir)
        if source_files_before != source_files_after:
            raise DataOperationError(
                "classic source data changed during import"
            )

        manifest = {
            "manifest_version": MANIFEST_VERSION,
            "kind": "classic_import",
            "created_at": _utc_now(),
            "source": {
                "data_dir": str(source_data_dir),
                "files_before": source_files_before,
                "files_after": source_files_after,
                "database": source_database,
            },
            "target": {
                "schema_version": LATEST_SCHEMA_VERSION,
                "files": _relative_file_manifest(staging),
                "database_on_classic_columns": migrated_database,
                "legacy_owner_counts": owner_counts,
            },
            "validation": {
                "source_unchanged": True,
                "table_counts_and_content_equal": True,
                "legacy_owners_null": True,
            },
        }
        _write_json(staging / "import-manifest.json", manifest)
        os.replace(staging, server_data_dir)
        return manifest
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def backup_data_dir(
    data_dir: Path,
    backup_dir: Path,
    *,
    source_quiesced: bool,
) -> dict[str, Any]:
    _require_quiesced(source_quiesced)
    data_dir = data_dir.resolve()
    backup_dir = backup_dir.resolve()
    _validate_distinct_paths(data_dir, backup_dir)
    source_db = data_dir / DATABASE_NAME
    if not source_db.is_file():
        raise DataOperationError(f"database not found: {source_db}")

    source_files_before = _relative_file_manifest(data_dir)
    staging = _atomic_directory("backup", backup_dir)
    try:
        staged_data = staging / "data"
        staged_data.mkdir()
        _copy_sqlite_snapshot(source_db, staged_data / DATABASE_NAME)
        _copy_non_database_data(data_dir, staged_data)
        _finalize_sqlite(staged_data / DATABASE_NAME)

        manifest = {
            "manifest_version": MANIFEST_VERSION,
            "kind": "server_backup",
            "created_at": _utc_now(),
            "schema_version": database_snapshot(
                staged_data / DATABASE_NAME
            )["schema_version"],
            "files": _relative_file_manifest(staged_data),
            "database": database_snapshot(staged_data / DATABASE_NAME),
            "source_files_before": source_files_before,
        }
        source_files_after = _relative_file_manifest(data_dir)
        manifest["source_files_after"] = source_files_after
        manifest["source_unchanged"] = (
            source_files_before == source_files_after
        )
        if not manifest["source_unchanged"]:
            raise DataOperationError("source data changed during backup")

        _write_json(staging / "manifest.json", manifest)
        os.replace(staging, backup_dir)
        return manifest
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def verify_backup(backup_dir: Path) -> dict[str, Any]:
    backup_dir = backup_dir.resolve()
    manifest_path = backup_dir / "manifest.json"
    data_dir = backup_dir / "data"
    if not manifest_path.is_file() or not data_dir.is_dir():
        raise DataOperationError("invalid ChatRaw backup layout")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise DataOperationError("unsupported backup manifest version")
    if manifest.get("kind") != "server_backup":
        raise DataOperationError("manifest is not a Server backup")

    actual_files = _relative_file_manifest(data_dir)
    if actual_files != manifest.get("files"):
        raise DataOperationError("backup file checksum validation failed")
    actual_database = database_snapshot(data_dir / DATABASE_NAME)
    if actual_database != manifest.get("database"):
        raise DataOperationError("backup database validation failed")
    return {
        "valid": True,
        "schema_version": actual_database["schema_version"],
        "file_count": len(actual_files),
    }


def restore_backup(
    backup_dir: Path,
    data_dir: Path,
    *,
    destination_quiesced: bool,
    allow_empty_destination: bool = False,
) -> dict[str, Any]:
    _require_quiesced(destination_quiesced)
    verification = verify_backup(backup_dir)
    backup_dir = backup_dir.resolve()
    data_dir = data_dir.resolve()
    _validate_distinct_paths(backup_dir, data_dir)

    destination_exists = data_dir.exists()
    if destination_exists:
        if (
            not allow_empty_destination
            or not data_dir.is_dir()
            or any(data_dir.iterdir())
        ):
            raise DataOperationError(
                f"destination already exists; refusing to overwrite: {data_dir}"
            )
        staging = Path(
            tempfile.mkdtemp(
                prefix=".chatraw-restore-",
                dir=data_dir,
            )
        )
    else:
        staging = _atomic_directory("restore", data_dir)
    try:
        shutil.copytree(
            backup_dir / "data",
            staging,
            dirs_exist_ok=True,
        )
        if _relative_file_manifest(staging) != _relative_file_manifest(
            backup_dir / "data"
        ):
            raise DataOperationError("restored file validation failed")
        if database_snapshot(staging / DATABASE_NAME) != database_snapshot(
            backup_dir / "data" / DATABASE_NAME
        ):
            raise DataOperationError("restored database validation failed")
        if destination_exists:
            for child in staging.iterdir():
                os.replace(child, data_dir / child.name)
            staging.rmdir()
        else:
            os.replace(staging, data_dir)
        return verification
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ChatRaw Server data import, backup, verification, and restore"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    import_command = commands.add_parser("import-classic")
    import_command.add_argument("--source-data-dir", type=Path, required=True)
    import_command.add_argument("--server-data-dir", type=Path, required=True)
    import_command.add_argument(
        "--confirm-source-quiesced",
        action="store_true",
    )

    backup_command = commands.add_parser("backup")
    backup_command.add_argument("--data-dir", type=Path, required=True)
    backup_command.add_argument("--backup-dir", type=Path, required=True)
    backup_command.add_argument(
        "--confirm-source-quiesced",
        action="store_true",
    )

    verify_command = commands.add_parser("verify")
    verify_command.add_argument("--backup-dir", type=Path, required=True)

    restore_command = commands.add_parser("restore")
    restore_command.add_argument("--backup-dir", type=Path, required=True)
    restore_command.add_argument("--data-dir", type=Path, required=True)
    restore_command.add_argument(
        "--confirm-destination-quiesced",
        action="store_true",
    )
    restore_command.add_argument(
        "--allow-empty-destination",
        action="store_true",
        help="restore into an existing empty directory such as a new volume",
    )
    return parser


def main() -> int:
    arguments = _build_parser().parse_args()
    try:
        if arguments.command == "import-classic":
            result = import_classic_data(
                arguments.source_data_dir,
                arguments.server_data_dir,
                source_quiesced=arguments.confirm_source_quiesced,
            )
        elif arguments.command == "backup":
            result = backup_data_dir(
                arguments.data_dir,
                arguments.backup_dir,
                source_quiesced=arguments.confirm_source_quiesced,
            )
        elif arguments.command == "verify":
            result = verify_backup(arguments.backup_dir)
        else:
            result = restore_backup(
                arguments.backup_dir,
                arguments.data_dir,
                destination_quiesced=(
                    arguments.confirm_destination_quiesced
                ),
                allow_empty_destination=arguments.allow_empty_destination,
            )
    except (DataOperationError, OSError, sqlite3.Error, ValueError) as error:
        print(json.dumps({"success": False, "error": str(error)}))
        return 1

    print(json.dumps({"success": True, "result": result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
