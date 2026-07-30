import asyncio
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from backend import db_migrations, main
from backend.server_data import (
    DataOperationError,
    backup_data_dir,
    database_snapshot,
    import_classic_data,
    restore_backup,
    verify_backup,
)


CLASSIC_SCHEMA = """
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE model_configs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    api_key TEXT,
    api_url TEXT NOT NULL,
    model_id TEXT NOT NULL,
    context_length INTEGER DEFAULT 8192,
    max_output INTEGER DEFAULT 4096,
    type TEXT NOT NULL,
    capability TEXT,
    created_at TEXT
);
CREATE TABLE chats (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT
);
CREATE TABLE chat_compactions (
    chat_id TEXT PRIMARY KEY,
    summary TEXT NOT NULL,
    boundary_message_id TEXT NOT NULL,
    boundary_created_at TEXT NOT NULL,
    original_token_estimate INTEGER DEFAULT 0,
    summary_token_estimate INTEGER DEFAULT 0,
    compressed_message_count INTEGER DEFAULT 0,
    updated_at TEXT
);
CREATE TABLE chat_skill_activations (
    id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    source_json TEXT,
    created_at TEXT
);
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    content TEXT,
    created_at TEXT
);
CREATE TABLE document_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding BLOB,
    created_at TEXT
);
"""


def sha256(path):
    digest = hashlib.sha256()
    digest.update(Path(path).read_bytes())
    return digest.hexdigest()


def create_classic_data_dir(root: Path) -> Path:
    data_dir = root / "classic-data"
    data_dir.mkdir()
    connection = sqlite3.connect(data_dir / "chatraw.db")
    connection.executescript(CLASSIC_SCHEMA)
    connection.execute(
        "INSERT INTO settings (key, value) VALUES ('global', '{}')"
    )
    connection.execute(
        """
        INSERT INTO model_configs
            (id, name, api_key, api_url, model_id, context_length,
             max_output, type, capability, created_at)
        VALUES
            ('model-1', 'Classic', 'secret', 'https://example.test/v1',
             'classic', 8192, 4096, 'chat', '{}',
             '2025-01-01T00:00:00')
        """
    )
    connection.execute(
        """
        INSERT INTO chats (id, title, created_at, updated_at)
        VALUES ('chat-1', 'Classic chat',
                '2025-01-01T00:00:00', '2025-01-01T00:00:02')
        """
    )
    connection.executemany(
        """
        INSERT INTO messages (id, chat_id, role, content, created_at)
        VALUES (?, 'chat-1', ?, ?, ?)
        """,
        [
            ("message-1", "user", "hello", "2025-01-01T00:00:01"),
            (
                "message-2",
                "assistant",
                "world",
                "2025-01-01T00:00:01",
            ),
        ],
    )
    connection.execute(
        """
        INSERT INTO chat_compactions
            (chat_id, summary, boundary_message_id, boundary_created_at,
             original_token_estimate, summary_token_estimate,
             compressed_message_count, updated_at)
        VALUES
            ('chat-1', 'summary', 'message-1',
             '2025-01-01T00:00:01', 100, 20, 1,
             '2025-01-01T00:00:02')
        """
    )
    connection.execute(
        """
        INSERT INTO chat_skill_activations
            (id, chat_id, message_id, skill_name, source_json, created_at)
        VALUES
            ('activation-1', 'chat-1', 'message-1', 'classic-skill',
             '{}', '2025-01-01T00:00:01')
        """
    )
    connection.execute(
        """
        INSERT INTO documents (id, filename, content, created_at)
        VALUES ('document-1', 'classic.txt', 'document content',
                '2025-01-01T00:00:00')
        """
    )
    connection.execute(
        """
        INSERT INTO document_chunks
            (id, document_id, content, embedding, created_at)
        VALUES ('chunk-1', 'document-1', 'document content',
                '[1.0, 2.0]', '2025-01-01T00:00:00')
        """
    )
    connection.commit()
    connection.close()

    plugins = data_dir / "plugins"
    skills = data_dir / "skills"
    plugins.mkdir()
    skills.mkdir()
    (plugins / "config.json").write_text(
        '{"plugins":{"classic":{"enabled":true}}}\n',
        encoding="utf-8",
    )
    (skills / "config.json").write_text(
        '{"classic-skill":{"enabled":true}}\n',
        encoding="utf-8",
    )
    return data_dir


class MigrationTests(unittest.TestCase):
    def test_classic_fixture_matches_v221_contract(self):
        with tempfile.TemporaryDirectory(prefix="chatraw-t1-contract-") as temp:
            root = Path(temp)
            source = create_classic_data_dir(root)
            snapshot = database_snapshot(source / "chatraw.db")
            contract = json.loads(
                (
                    Path(__file__).resolve().parent
                    / "contracts"
                    / "chatraw-v2.2.1.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(
                {
                    table: details["columns"]
                    for table, details in snapshot["tables"].items()
                },
                contract["database_tables"],
            )

    def test_fresh_database_has_versioned_server_columns(self):
        with tempfile.TemporaryDirectory(prefix="chatraw-t1-fresh-") as temp:
            database = main.Database(str(Path(temp) / "chatraw.db"))
            connection = database.get_conn()
            try:
                version = connection.execute(
                    "SELECT MAX(version) FROM schema_migrations"
                ).fetchone()[0]
                self.assertEqual(
                    version,
                    db_migrations.LATEST_SCHEMA_VERSION,
                )
                self.assertEqual(
                    connection.execute("PRAGMA foreign_keys").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute("PRAGMA busy_timeout").fetchone()[0],
                    5_000,
                )
                self.assertEqual(
                    connection.execute("PRAGMA journal_mode").fetchone()[0],
                    "wal",
                )
                self.assertEqual(
                    {
                        row["name"]
                        for row in connection.execute(
                            "PRAGMA table_info(chats)"
                        )
                    },
                    {
                        "id",
                        "title",
                        "created_at",
                        "updated_at",
                        "owner_user_id",
                    },
                )
            finally:
                connection.close()

    def test_server_schema_contract_matches_database(self):
        contract = json.loads(
            (
                Path(__file__).resolve().parent
                / "contracts"
                / "chatraw-server-schema-v1.json"
            ).read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory(prefix="chatraw-t1-schema-") as temp:
            database = main.Database(str(Path(temp) / "chatraw.db"))
            connection = database.get_conn()
            try:
                self.assertEqual(
                    db_migrations.current_schema_version(connection),
                    contract["latest_schema_version"],
                )
                migration_rows = [
                    {
                        "version": row["version"],
                        "name": row["name"],
                    }
                    for row in connection.execute(
                        """
                        SELECT version, name
                        FROM schema_migrations
                        ORDER BY version
                        """
                    )
                ]
                self.assertEqual(migration_rows, contract["migrations"])

                for table, columns in contract["new_tables"].items():
                    actual = {
                        row["name"]
                        for row in connection.execute(
                            f"PRAGMA table_info({table})"
                        )
                    }
                    self.assertEqual(actual, set(columns))
                for table, columns in contract["added_columns"].items():
                    actual = {
                        row["name"]
                        for row in connection.execute(
                            f"PRAGMA table_info({table})"
                        )
                    }
                    self.assertEqual(set(), set(columns) - actual)

                indexes = {
                    row["name"]
                    for row in connection.execute(
                        """
                        SELECT name
                        FROM sqlite_master
                        WHERE type = 'index'
                        """
                    )
                }
                self.assertEqual(
                    set(),
                    set(contract["new_indexes"]) - indexes,
                )
                input_resource_unique_columns = {
                    tuple(
                        column["name"]
                        for column in connection.execute(
                            f'PRAGMA index_info("{index["name"]}")'
                        )
                    )
                    for index in connection.execute(
                        "PRAGMA index_list(module_task_input_resources)"
                    )
                    if index["unique"]
                }
                self.assertIn(
                    ("storage_name",),
                    input_resource_unique_columns,
                )
                self.assertNotIn(
                    ("bound_task_id",),
                    input_resource_unique_columns,
                )
                self.assertEqual(
                    contract["module_task_input_resources"],
                    {
                        "one_task_per_resource": True,
                        "multiple_resources_per_task": True,
                    },
                )
            finally:
                connection.close()

    def test_v15_rule_tombstones_preserve_frozen_task_references(self):
        with tempfile.TemporaryDirectory(prefix="chatraw-t1-v14-") as temp:
            path = create_classic_data_dir(Path(temp)) / "chatraw.db"
            connection = sqlite3.connect(path)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """
                CREATE TABLE schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )
            connection.execute("BEGIN IMMEDIATE")
            try:
                for version, name, migrate in db_migrations.MIGRATIONS:
                    if version > 14:
                        break
                    migrate(connection)
                    connection.execute(
                        """
                        INSERT INTO schema_migrations (
                            version, name, applied_at
                        ) VALUES (?, ?, '2026-07-29T00:00:00Z')
                        """,
                        (version, name),
                    )
                connection.commit()
            except BaseException:
                connection.rollback()
                connection.close()
                raise

            try:
                now = "2026-07-29T00:00:00Z"
                connection.execute(
                    """
                    INSERT INTO users (
                        id, username, password_hash, role, enabled,
                        created_at, updated_at, password_changed_at
                    ) VALUES (
                        'rule-owner', 'rule-owner', 'hash', 'member', 1,
                        ?, ?, ?
                    )
                    """,
                    (now, now, now),
                )
                connection.execute(
                    """
                    INSERT INTO module_tasks (
                        id, registration_id, module_id, module_version,
                        action_id, action_version, action_contract_json,
                        config_revision, creator_user_id, idempotency_key,
                        request_digest, state, created_at, updated_at
                    ) VALUES (
                        'frozen-task', 'registration', 'chatraw.agent',
                        '1.0.0', 'chat', '1.0.0', '{}', '1',
                        'rule-owner', 'rule-task', 'digest', 'queued', ?, ?
                    )
                    """,
                    (now, now),
                )
                connection.execute(
                    """
                    INSERT INTO agent_rule_documents (
                        id, owner_user_id, target_module_id, name, scope,
                        current_source_version_id,
                        active_compiled_version_id, created_at, updated_at
                    ) VALUES (
                        'rule-document', 'rule-owner', 'chatraw.agent',
                        'Reusable name', 'personal', 'rule-source',
                        'rule-compiled', ?, ?
                    )
                    """,
                    (now, now),
                )
                connection.execute(
                    """
                    INSERT INTO agent_rule_source_versions (
                        id, document_id, version_number, source_document,
                        content_sha256, created_at
                    ) VALUES (
                        'rule-source', 'rule-document', 1, 'source',
                        'source-hash', ?
                    )
                    """,
                    (now,),
                )
                connection.execute(
                    """
                    INSERT INTO agent_compiled_rule_versions (
                        id, document_id, source_version_id,
                        specification_version, status, content_sha256,
                        compiled_json, model_output,
                        validation_errors_json, created_at
                    ) VALUES (
                        'rule-compiled', 'rule-document', 'rule-source',
                        'chatraw-agent-rule-1.1', 'valid', 'compiled-hash',
                        '{}', '{}', '[]', ?
                    )
                    """,
                    (now,),
                )
                connection.execute(
                    """
                    INSERT INTO module_task_rule_activations (
                        task_id, ordinal, document_id,
                        compiled_version_id, scope_snapshot, created_at
                    ) VALUES (
                        'frozen-task', 0, 'rule-document',
                        'rule-compiled', 'personal', ?
                    )
                    """,
                    (now,),
                )
                connection.commit()

                self.assertEqual(
                    db_migrations.apply_migrations(connection),
                    15,
                )
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT deleted_at FROM agent_rule_documents
                        WHERE id = 'rule-document'
                        """
                    ).fetchone()["deleted_at"],
                    None,
                )
                frozen = connection.execute(
                    """
                    SELECT activations.document_id,
                           activations.compiled_version_id,
                           activations.scope_snapshot,
                           versions.content_sha256
                    FROM module_task_rule_activations AS activations
                    JOIN agent_compiled_rule_versions AS versions
                      ON versions.id = activations.compiled_version_id
                    WHERE activations.task_id = 'frozen-task'
                    """
                ).fetchone()
                self.assertEqual(
                    tuple(frozen),
                    (
                        "rule-document",
                        "rule-compiled",
                        "personal",
                        "compiled-hash",
                    ),
                )
                connection.execute(
                    """
                    UPDATE agent_rule_documents
                    SET active_compiled_version_id = NULL,
                        deleted_at = '2026-07-29T01:00:00Z'
                    WHERE id = 'rule-document'
                    """
                )
                connection.execute(
                    """
                    INSERT INTO agent_rule_documents (
                        id, owner_user_id, target_module_id, name, scope,
                        current_source_version_id,
                        active_compiled_version_id, created_at, updated_at
                    ) VALUES (
                        'replacement-document', 'rule-owner',
                        'chatraw.agent', 'Reusable name', 'personal',
                        'replacement-source', NULL, ?, ?
                    )
                    """,
                    (now, now),
                )
                connection.execute(
                    """
                    INSERT INTO agent_rule_source_versions (
                        id, document_id, version_number, source_document,
                        content_sha256, created_at
                    ) VALUES (
                        'replacement-source', 'replacement-document', 1,
                        'replacement source', 'replacement-source-hash', ?
                    )
                    """,
                    (now,),
                )
                self.assertEqual(
                    connection.execute(
                        "PRAGMA foreign_key_check"
                    ).fetchall(),
                    [],
                )
            finally:
                connection.close()

    def test_v13_allows_multiple_input_resources_per_task(self):
        with tempfile.TemporaryDirectory(prefix="chatraw-t1-v12-") as temp:
            database = main.Database(str(Path(temp) / "chatraw.db"))
            connection = database.get_conn()
            try:
                connection.commit()
                connection.execute("PRAGMA foreign_keys = OFF")
                connection.execute(
                    "ALTER TABLE module_task_input_resources "
                    "RENAME TO module_task_input_resources_v13_test"
                )
                connection.execute(
                    """
                    CREATE TABLE module_task_input_resources (
                        resource_id TEXT PRIMARY KEY,
                        creator_user_id TEXT NOT NULL,
                        filename TEXT NOT NULL,
                        media_type TEXT NOT NULL,
                        size INTEGER NOT NULL CHECK (size >= 0),
                        sha256 TEXT NOT NULL,
                        storage_name TEXT NOT NULL UNIQUE,
                        created_at TEXT NOT NULL,
                        expires_at TEXT,
                        bound_task_id TEXT UNIQUE,
                        FOREIGN KEY (creator_user_id) REFERENCES users(id),
                        FOREIGN KEY (bound_task_id)
                            REFERENCES module_tasks(id) ON DELETE CASCADE
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO module_task_input_resources
                    SELECT * FROM module_task_input_resources_v13_test
                    """
                )
                connection.execute(
                    "DROP TABLE module_task_input_resources_v13_test"
                )
                connection.execute(
                    "CREATE INDEX idx_module_task_input_resources_expiry "
                    "ON module_task_input_resources(expires_at)"
                )
                connection.execute(
                    "DELETE FROM schema_migrations WHERE version >= 13"
                )
                connection.commit()
                connection.execute("PRAGMA foreign_keys = ON")

                connection.execute(
                    """
                    INSERT INTO users (
                        id, username, password_hash, role, enabled,
                        created_at, updated_at, password_changed_at
                    ) VALUES (
                        'resource-user', 'resource-user', 'hash', 'member', 1,
                        '2026-07-27T00:00:00Z',
                        '2026-07-27T00:00:00Z',
                        '2026-07-27T00:00:00Z'
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO module_tasks (
                        id, registration_id, module_id, module_version,
                        action_id, action_version, action_contract_json,
                        config_revision, creator_user_id, idempotency_key,
                        request_digest, state, created_at, updated_at
                    ) VALUES (
                        'resource-task', 'registration', 'example.module',
                        '1.0.0', 'example.run', '1.0.0', '{}', '1',
                        'resource-user', 'resource-idempotency', 'digest',
                        'queued', '2026-07-27T00:00:00Z',
                        '2026-07-27T00:00:00Z'
                    )
                    """
                )
                resource_rows = [
                    (
                        "resource-1",
                        "resource-user",
                        "first.txt",
                        "text/plain",
                        5,
                        "sha-1",
                        "storage-1",
                        "2026-07-27T00:00:00Z",
                        None,
                        "resource-task",
                    ),
                    (
                        "resource-2",
                        "resource-user",
                        "second.txt",
                        "text/plain",
                        6,
                        "sha-2",
                        "storage-2",
                        "2026-07-27T00:00:00Z",
                        None,
                        "resource-task",
                    ),
                ]
                connection.execute(
                    """
                    INSERT INTO module_task_input_resources (
                        resource_id, creator_user_id, filename, media_type,
                        size, sha256, storage_name, created_at, expires_at,
                        bound_task_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    resource_rows[0],
                )
                connection.commit()
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO module_task_input_resources (
                            resource_id, creator_user_id, filename, media_type,
                            size, sha256, storage_name, created_at, expires_at,
                            bound_task_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        resource_rows[1],
                    )
                connection.rollback()

                self.assertEqual(
                    db_migrations.apply_migrations(connection),
                    db_migrations.LATEST_SCHEMA_VERSION,
                )
                connection.execute(
                    """
                    INSERT INTO module_task_input_resources (
                        resource_id, creator_user_id, filename, media_type,
                        size, sha256, storage_name, created_at, expires_at,
                        bound_task_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    resource_rows[1],
                )
                connection.commit()

                resources = [
                    tuple(row)
                    for row in connection.execute(
                        """
                        SELECT resource_id, filename, bound_task_id
                        FROM module_task_input_resources
                        ORDER BY resource_id
                        """
                    )
                ]
                self.assertEqual(
                    resources,
                    [
                        ("resource-1", "first.txt", "resource-task"),
                        ("resource-2", "second.txt", "resource-task"),
                    ],
                )
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT name FROM schema_migrations
                        WHERE version = 13
                        """
                    ).fetchone()["name"],
                    "multiple_task_input_resources",
                )
                self.assertEqual(
                    connection.execute("PRAGMA foreign_key_check").fetchall(),
                    [],
                )
                self.assertEqual(
                    db_migrations.apply_migrations(connection),
                    db_migrations.LATEST_SCHEMA_VERSION,
                )
            finally:
                connection.close()

    def test_v7_plugin_dependency_migrates_without_data_loss(self):
        with tempfile.TemporaryDirectory(prefix="chatraw-t1-v7-") as temp:
            database = main.Database(str(Path(temp) / "chatraw.db"))
            connection = database.get_conn()
            try:
                connection.execute("PRAGMA foreign_keys = OFF")
                connection.execute("DROP TABLE module_feature_suites")
                connection.execute(
                    """
                    CREATE TABLE module_feature_suites (
                        registration_id TEXT PRIMARY KEY,
                        companion_plugin_id TEXT NOT NULL,
                        companion_plugin_version_range TEXT NOT NULL,
                        dependency_status TEXT NOT NULL,
                        checked_at TEXT
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO module_feature_suites (
                        registration_id, companion_plugin_id,
                        companion_plugin_version_range,
                        dependency_status, checked_at
                    )
                    VALUES ('legacy-registration', 'legacy-plugin',
                            '>=1.0.0,<2.0.0', 'plugin_disabled',
                            '2026-07-24T00:00:00Z')
                    """
                )
                connection.execute("DROP TABLE module_task_output_resources")
                connection.execute("DROP TABLE module_task_input_resources")
                connection.execute(
                    "DROP TABLE module_task_rule_activations"
                )
                connection.execute(
                    "DROP TABLE agent_compiled_rule_versions"
                )
                connection.execute(
                    "DROP TABLE agent_rule_source_versions"
                )
                connection.execute("DROP TABLE agent_rule_documents")
                connection.execute(
                    "DROP TABLE module_task_skill_activations"
                )
                connection.execute("DROP TABLE agent_skill_versions")
                connection.execute("DROP TABLE agent_skills")
                connection.execute(
                    "DELETE FROM schema_migrations "
                    "WHERE version >= 8"
                )
                connection.commit()

                self.assertEqual(
                    db_migrations.apply_migrations(connection),
                    db_migrations.LATEST_SCHEMA_VERSION,
                )
                row = connection.execute(
                    """
                    SELECT * FROM module_feature_suites
                    WHERE registration_id = 'legacy-registration'
                    """
                ).fetchone()
                self.assertEqual(row["integration_mode"], "plugin")
                self.assertEqual(row["integration_id"], "legacy-plugin")
                self.assertEqual(
                    row["integration_version_range"],
                    ">=1.0.0,<2.0.0",
                )
                self.assertEqual(
                    row["dependency_status"],
                    "plugin_disabled",
                )
            finally:
                connection.close()

    def test_v9_capability_rebuild_preserves_v8_tokens(self):
        with tempfile.TemporaryDirectory(prefix="chatraw-t1-v8-") as temp:
            database = main.Database(str(Path(temp) / "chatraw.db"))
            connection = database.get_conn()
            try:
                connection.execute("PRAGMA foreign_keys = OFF")
                connection.execute("DROP TABLE module_task_output_resources")
                connection.execute("DROP TABLE module_task_input_resources")
                connection.execute(
                    "DROP TABLE module_task_rule_activations"
                )
                connection.execute(
                    "DROP TABLE agent_compiled_rule_versions"
                )
                connection.execute(
                    "DROP TABLE agent_rule_source_versions"
                )
                connection.execute("DROP TABLE agent_rule_documents")
                connection.execute(
                    "DROP TABLE module_task_skill_activations"
                )
                connection.execute("DROP TABLE agent_skill_versions")
                connection.execute("DROP TABLE agent_skills")
                connection.execute(
                    "ALTER TABLE module_capability_tokens "
                    "RENAME TO module_capability_tokens_v9_test"
                )
                connection.execute(
                    """
                    CREATE TABLE module_capability_tokens (
                        token_digest TEXT PRIMARY KEY,
                        task_id TEXT NOT NULL,
                        registration_id TEXT NOT NULL,
                        capability TEXT NOT NULL
                            CHECK (
                                capability IN (
                                    'chat.read',
                                    'resource.read',
                                    'model.invoke'
                                )
                            ),
                        scope_json TEXT NOT NULL,
                        use_count INTEGER NOT NULL DEFAULT 0
                            CHECK (use_count >= 0),
                        max_uses INTEGER,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        revoked_at TEXT,
                        FOREIGN KEY (task_id)
                            REFERENCES module_tasks(id) ON DELETE CASCADE
                    )
                    """
                )
                connection.execute(
                    "DROP TABLE module_capability_tokens_v9_test"
                )
                token_rows = [
                    (
                        "digest-chat",
                        "legacy-task",
                        "legacy-registration",
                        "chat.read",
                        '{"chat_id":"chat-1"}',
                        1,
                        5,
                        "2026-07-24T00:00:00Z",
                        "2026-07-24T00:15:00Z",
                        None,
                    ),
                    (
                        "digest-model",
                        "legacy-task",
                        "legacy-registration",
                        "model.invoke",
                        '{"model_config_id":"model-1"}',
                        2,
                        None,
                        "2026-07-24T00:01:00Z",
                        "2026-07-24T00:16:00Z",
                        "2026-07-24T00:02:00Z",
                    ),
                ]
                connection.executemany(
                    """
                    INSERT INTO module_capability_tokens (
                        token_digest, task_id, registration_id, capability,
                        scope_json, use_count, max_uses, created_at,
                        expires_at, revoked_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    token_rows,
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO module_capability_tokens (
                            token_digest, task_id, registration_id,
                            capability, scope_json, created_at, expires_at
                        )
                        VALUES (
                            'digest-stream-before-v9', 'legacy-task',
                            'legacy-registration', 'resource.stream', '{}',
                            '2026-07-24T00:00:00Z',
                            '2026-07-24T00:15:00Z'
                        )
                        """
                    )
                connection.execute(
                    "DELETE FROM schema_migrations "
                    "WHERE version >= 9"
                )
                connection.commit()

                self.assertEqual(
                    db_migrations.apply_migrations(connection),
                    db_migrations.LATEST_SCHEMA_VERSION,
                )
                migrated_rows = [
                    tuple(row)
                    for row in connection.execute(
                        """
                        SELECT token_digest, task_id, registration_id,
                               capability, scope_json, use_count, max_uses,
                               created_at, expires_at, revoked_at
                        FROM module_capability_tokens
                        ORDER BY token_digest
                        """
                    )
                ]
                self.assertEqual(migrated_rows, sorted(token_rows))
                connection.execute(
                    """
                    INSERT INTO module_capability_tokens (
                        token_digest, task_id, registration_id, capability,
                        scope_json, created_at, expires_at
                    )
                    VALUES (
                        'digest-stream-after-v9', 'legacy-task',
                        'legacy-registration', 'resource.stream', '{}',
                        '2026-07-24T00:00:00Z',
                        '2026-07-24T00:15:00Z'
                    )
                    """
                )
            finally:
                connection.close()

    def test_classic_import_preserves_content_and_source(self):
        with tempfile.TemporaryDirectory(prefix="chatraw-t1-import-") as temp:
            root = Path(temp)
            source = create_classic_data_dir(root)
            destination = root / "server-data"
            source_db_hash = sha256(source / "chatraw.db")

            manifest = import_classic_data(
                source,
                destination,
                source_quiesced=True,
            )

            self.assertEqual(
                sha256(source / "chatraw.db"),
                source_db_hash,
            )
            self.assertTrue(manifest["validation"]["source_unchanged"])
            self.assertTrue(
                manifest["validation"]["table_counts_and_content_equal"]
            )
            self.assertTrue(
                manifest["validation"]["legacy_owners_null"]
            )
            self.assertEqual(
                manifest["target"]["legacy_owner_counts"],
                {
                    "chats_non_null": 0,
                    "messages_non_null": 0,
                    "documents_non_null": 0,
                },
            )
            self.assertEqual(
                (destination / "plugins" / "config.json").read_text(),
                (source / "plugins" / "config.json").read_text(),
            )
            self.assertEqual(
                (destination / "skills" / "config.json").read_text(),
                (source / "skills" / "config.json").read_text(),
            )

            connection = sqlite3.connect(destination / "chatraw.db")
            try:
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT sequence
                        FROM messages
                        WHERE chat_id = 'chat-1'
                        ORDER BY sequence
                        """
                    ).fetchall(),
                    [(1,), (2,)],
                )
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT typeof(embedding)
                        FROM document_chunks
                        WHERE id = 'chunk-1'
                        """
                    ).fetchone()[0],
                    "blob",
                )
            finally:
                connection.close()

            migrated_before = database_snapshot(
                destination / "chatraw.db"
            )
            migration_connection = main.open_database(
                str(destination / "chatraw.db")
            )
            try:
                self.assertEqual(
                    db_migrations.apply_migrations(migration_connection),
                    db_migrations.LATEST_SCHEMA_VERSION,
                )
            finally:
                migration_connection.close()
            self.assertEqual(
                database_snapshot(destination / "chatraw.db"),
                migrated_before,
            )

    def test_import_requires_new_destination_and_quiesced_source(self):
        with tempfile.TemporaryDirectory(prefix="chatraw-t1-safe-") as temp:
            root = Path(temp)
            source = create_classic_data_dir(root)
            destination = root / "server-data"

            with self.assertRaises(DataOperationError):
                import_classic_data(
                    source,
                    destination,
                    source_quiesced=False,
                )

            destination.mkdir()
            with self.assertRaises(DataOperationError):
                import_classic_data(
                    source,
                    destination,
                    source_quiesced=True,
                )

    def test_interrupted_migration_rolls_back_schema_and_version(self):
        with tempfile.TemporaryDirectory(prefix="chatraw-t1-rollback-") as temp:
            root = Path(temp)
            source = create_classic_data_dir(root)
            db_path = source / "chatraw.db"

            def failing_migration(connection):
                connection.execute(
                    "ALTER TABLE chats ADD COLUMN should_rollback TEXT"
                )
                raise RuntimeError("injected migration failure")

            connection = main.open_database(str(db_path))
            try:
                with patch.object(
                    db_migrations,
                    "MIGRATIONS",
                    ((1, "failing", failing_migration),),
                ):
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "injected migration failure",
                    ):
                        db_migrations.apply_migrations(connection)
            finally:
                connection.close()

            check = sqlite3.connect(db_path)
            try:
                columns = {
                    row[1]
                    for row in check.execute("PRAGMA table_info(chats)")
                }
                self.assertNotIn("should_rollback", columns)
                self.assertIsNone(
                    check.execute(
                        """
                        SELECT name
                        FROM sqlite_master
                        WHERE type = 'table'
                          AND name = 'schema_migrations'
                        """
                    ).fetchone()
                )
            finally:
                check.close()

    def test_newer_schema_is_rejected_without_modification(self):
        with tempfile.TemporaryDirectory(prefix="chatraw-t1-newer-") as temp:
            db_path = Path(temp) / "chatraw.db"
            connection = sqlite3.connect(db_path)
            connection.execute(
                """
                CREATE TABLE schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO schema_migrations
                VALUES (?, 'future', '2025-01-01T00:00:00Z')
                """,
                (db_migrations.LATEST_SCHEMA_VERSION + 1,),
            )
            connection.commit()
            connection.close()
            before = sha256(db_path)

            with self.assertRaises(
                db_migrations.UnsupportedSchemaVersion
            ):
                main.Database(str(db_path))

            self.assertEqual(sha256(db_path), before)
            check = sqlite3.connect(db_path)
            try:
                self.assertIsNone(
                    check.execute(
                        """
                        SELECT name
                        FROM sqlite_master
                        WHERE type = 'table' AND name = 'chats'
                        """
                    ).fetchone()
                )
            finally:
                check.close()


class DatabaseConcurrencyAndPaginationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            prefix="chatraw-t1-concurrency-"
        )
        self.database = main.Database(
            str(Path(self.temp.name) / "chatraw.db")
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_more_than_ten_chats_are_preserved(self):
        first = self.database.create_chat("first")
        for index in range(15):
            self.database.create_chat(f"chat-{index}")

        self.assertTrue(self.database.chat_exists(first.id))
        self.assertEqual(len(self.database.get_chats()), 16)

    def test_cursor_pagination_is_stable_and_complete(self):
        for index in range(12):
            chat = self.database.create_chat(f"chat-{index}")
            connection = self.database.get_conn()
            try:
                connection.execute(
                    "UPDATE chats SET updated_at = ? WHERE id = ?",
                    (f"2025-01-01T00:00:{index:02d}", chat.id),
                )
                connection.commit()
            finally:
                connection.close()

        collected = []
        cursor = None
        while True:
            page, cursor = self.database.get_chats_page(5, cursor)
            collected.extend(chat.id for chat in page)
            if cursor is None:
                break

        self.assertEqual(len(collected), 12)
        self.assertEqual(len(set(collected)), 12)

    def test_old_and_new_chat_endpoints_keep_separate_shapes(self):
        for index in range(12):
            self.database.create_chat(f"chat-{index}")

        original_database = main.db
        main.db = self.database
        try:
            legacy = asyncio.run(main.get_chats())
            first_page = asyncio.run(main.get_chats_page(limit=5))
            second_page = asyncio.run(
                main.get_chats_page(
                    limit=5,
                    cursor=first_page["next_cursor"],
                )
            )
        finally:
            main.db = original_database

        self.assertIsInstance(legacy, list)
        self.assertEqual(len(legacy), 12)
        self.assertEqual(
            set(legacy[0]),
            {"id", "title", "created_at", "updated_at"},
        )
        self.assertEqual(set(first_page), {"items", "next_cursor"})
        self.assertEqual(len(first_page["items"]), 5)
        self.assertEqual(len(second_page["items"]), 5)
        self.assertTrue(
            set(item["id"] for item in first_page["items"]).isdisjoint(
                item["id"] for item in second_page["items"]
            )
        )

    def test_paginated_route_and_invalid_inputs(self):
        route_methods = {
            (method, route.path)
            for route in main.app.routes
            for method in getattr(route, "methods", set())
        }
        self.assertIn(("GET", "/api/v1/chats"), route_methods)

        with self.assertRaises(main.HTTPException) as limit_error:
            asyncio.run(main.get_chats_page(limit=0))
        self.assertEqual(limit_error.exception.status_code, 400)

        with self.assertRaises(main.HTTPException) as cursor_error:
            asyncio.run(
                main.get_chats_page(limit=10, cursor="not-a-cursor")
            )
        self.assertEqual(cursor_error.exception.status_code, 400)

    def test_concurrent_messages_receive_unique_stable_sequences(self):
        chat = self.database.create_chat("concurrent")

        def add(index):
            return self.database.add_message(
                chat.id,
                "user",
                f"message-{index}",
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            messages = list(executor.map(add, range(40)))

        self.assertEqual(len(messages), 40)
        connection = self.database.get_conn()
        try:
            sequences = [
                row[0]
                for row in connection.execute(
                    """
                    SELECT sequence
                    FROM messages
                    WHERE chat_id = ?
                    ORDER BY sequence
                    """,
                    (chat.id,),
                )
            ]
        finally:
            connection.close()
        self.assertEqual(sequences, list(range(1, 41)))

    def test_concurrent_chat_creation_succeeds(self):
        with ThreadPoolExecutor(max_workers=8) as executor:
            chats = list(
                executor.map(
                    lambda index: self.database.create_chat(
                        f"chat-{index}"
                    ),
                    range(30),
                )
            )
        self.assertEqual(len({chat.id for chat in chats}), 30)
        self.assertEqual(len(self.database.get_chats()), 30)

    def test_busy_timeout_waits_for_writer_and_then_succeeds(self):
        blocker = self.database.get_conn()
        blocker.execute("BEGIN IMMEDIATE")
        started = threading.Event()
        result = {}

        def write_chat():
            started.set()
            begin = time.monotonic()
            result["chat"] = self.database.create_chat("after-lock")
            result["elapsed"] = time.monotonic() - begin

        thread = threading.Thread(target=write_chat)
        thread.start()
        self.assertTrue(started.wait(timeout=1))
        time.sleep(0.15)
        blocker.rollback()
        blocker.close()
        thread.join(timeout=5)

        self.assertFalse(thread.is_alive())
        self.assertTrue(self.database.chat_exists(result["chat"].id))
        self.assertGreaterEqual(result["elapsed"], 0.1)

    def test_failed_write_transaction_rolls_back(self):
        with self.assertRaisesRegex(RuntimeError, "injected failure"):
            with self.database.connection(write=True) as connection:
                connection.execute(
                    """
                    INSERT INTO chats
                        (id, title, created_at, updated_at, owner_user_id)
                    VALUES ('rollback-chat', 'rollback', '', '', NULL)
                    """
                )
                raise RuntimeError("injected failure")

        self.assertFalse(self.database.chat_exists("rollback-chat"))


class BackupRestoreTests(unittest.TestCase):
    def test_backup_verify_restore_round_trip(self):
        with tempfile.TemporaryDirectory(prefix="chatraw-t1-backup-") as temp:
            root = Path(temp)
            data_dir = root / "server-data"
            data_dir.mkdir()
            database = main.Database(str(data_dir / "chatraw.db"))
            chat = database.create_chat("backup")
            database.add_message(chat.id, "user", "content")
            (data_dir / "plugins").mkdir()
            (data_dir / "plugins" / "config.json").write_text(
                '{"plugins":{}}\n',
                encoding="utf-8",
            )
            (data_dir / "skills").mkdir()
            (data_dir / "skills" / "config.json").write_text(
                '{"skills":{}}\n',
                encoding="utf-8",
            )

            backup_dir = root / "backup"
            manifest = backup_data_dir(
                data_dir,
                backup_dir,
                source_quiesced=True,
            )
            self.assertTrue(manifest["source_unchanged"])
            self.assertEqual(
                manifest["schema_version"],
                db_migrations.LATEST_SCHEMA_VERSION,
            )
            self.assertEqual(
                {entry["path"] for entry in manifest["files"]},
                {
                    "chatraw.db",
                    "plugins/config.json",
                    "skills/config.json",
                },
            )
            verification = verify_backup(backup_dir)
            self.assertTrue(verification["valid"])

            restored = root / "restored-data"
            restore_backup(
                backup_dir,
                restored,
                destination_quiesced=True,
            )
            self.assertEqual(
                database_snapshot(restored / "chatraw.db"),
                database_snapshot(backup_dir / "data" / "chatraw.db"),
            )
            self.assertEqual(
                (restored / "plugins" / "config.json").read_text(),
                '{"plugins":{}}\n',
            )
            self.assertEqual(
                (restored / "skills" / "config.json").read_text(),
                '{"skills":{}}\n',
            )

            empty_volume = root / "empty-volume"
            empty_volume.mkdir()
            restore_backup(
                backup_dir,
                empty_volume,
                destination_quiesced=True,
                allow_empty_destination=True,
            )
            self.assertEqual(
                database_snapshot(empty_volume / "chatraw.db"),
                database_snapshot(backup_dir / "data" / "chatraw.db"),
            )

    def test_backup_tampering_and_overwrite_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix="chatraw-t1-tamper-") as temp:
            root = Path(temp)
            data_dir = root / "server-data"
            data_dir.mkdir()
            main.Database(str(data_dir / "chatraw.db"))
            backup_dir = root / "backup"

            with self.assertRaises(DataOperationError):
                backup_data_dir(
                    data_dir,
                    backup_dir,
                    source_quiesced=False,
                )

            backup_data_dir(
                data_dir,
                backup_dir,
                source_quiesced=True,
            )
            destination = root / "existing"
            destination.mkdir()
            with self.assertRaises(DataOperationError):
                restore_backup(
                    backup_dir,
                    destination,
                    destination_quiesced=True,
                )

            with (backup_dir / "data" / "chatraw.db").open("ab") as file:
                file.write(b"tamper")
            with self.assertRaises(DataOperationError):
                verify_backup(backup_dir)


class DataCommandLineTests(unittest.TestCase):
    def run_command(self, *arguments):
        result = subprocess.run(
            [sys.executable, "-m", "backend.server_data", *arguments],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, payload)
        self.assertTrue(payload["success"])
        return payload["result"]

    def test_import_backup_verify_and_restore_commands(self):
        with tempfile.TemporaryDirectory(prefix="chatraw-t1-cli-") as temp:
            root = Path(temp)
            source = create_classic_data_dir(root)
            server_data = root / "server-data"
            backup = root / "backup"
            restored = root / "restored"

            imported = self.run_command(
                "import-classic",
                "--source-data-dir",
                str(source),
                "--server-data-dir",
                str(server_data),
                "--confirm-source-quiesced",
            )
            self.assertTrue(imported["validation"]["source_unchanged"])

            self.run_command(
                "backup",
                "--data-dir",
                str(server_data),
                "--backup-dir",
                str(backup),
                "--confirm-source-quiesced",
            )
            verified = self.run_command(
                "verify",
                "--backup-dir",
                str(backup),
            )
            self.assertTrue(verified["valid"])

            self.run_command(
                "restore",
                "--backup-dir",
                str(backup),
                "--data-dir",
                str(restored),
                "--confirm-destination-quiesced",
            )
            self.assertEqual(
                database_snapshot(restored / "chatraw.db"),
                database_snapshot(server_data / "chatraw.db"),
            )


if __name__ == "__main__":
    unittest.main()
