import json
import sqlite3
import struct
from datetime import datetime, timezone


LATEST_SCHEMA_VERSION = 12


class UnsupportedSchemaVersion(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(connection, table):
        return set()
    return {
        row["name"]
        for row in connection.execute(f'PRAGMA table_info("{table}")')
    }


def current_schema_version(connection: sqlite3.Connection) -> int:
    if not _table_exists(connection, "schema_migrations"):
        return 0
    row = connection.execute(
        "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
    ).fetchone()
    return int(row["version"])


def assert_supported_schema(connection: sqlite3.Connection) -> int:
    version = current_schema_version(connection)
    if version > LATEST_SCHEMA_VERSION:
        raise UnsupportedSchemaVersion(
            "database schema version "
            f"{version} is newer than supported version {LATEST_SCHEMA_VERSION}"
        )
    return version


def _add_column_if_missing(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    declaration: str,
) -> None:
    if column not in _columns(connection, table):
        connection.execute(
            f'ALTER TABLE "{table}" ADD COLUMN "{column}" {declaration}'
        )


def _backfill_message_sequences(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        """
        SELECT rowid, chat_id
        FROM messages
        ORDER BY chat_id ASC, COALESCE(created_at, '') ASC, rowid ASC
        """
    ).fetchall()
    next_sequence: dict[str, int] = {}
    updates = []
    for row in rows:
        sequence = next_sequence.get(row["chat_id"], 0) + 1
        next_sequence[row["chat_id"]] = sequence
        updates.append((sequence, row["rowid"]))
    connection.executemany(
        "UPDATE messages SET sequence = ? WHERE rowid = ?",
        updates,
    )


def _migrate_embeddings(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        """
        SELECT id, embedding
        FROM document_chunks
        WHERE embedding IS NOT NULL AND typeof(embedding) = 'text'
        """
    ).fetchall()
    updates = []
    for row in rows:
        try:
            values = json.loads(row["embedding"])
            if not isinstance(values, list):
                continue
            encoded = struct.pack(f"{len(values)}f", *values)
        except (TypeError, ValueError, json.JSONDecodeError, struct.error):
            continue
        updates.append((encoded, row["id"]))
    connection.executemany(
        "UPDATE document_chunks SET embedding = ? WHERE id = ?",
        updates,
    )


def _migration_1_server_shared_data(connection: sqlite3.Connection) -> None:
    _add_column_if_missing(connection, "chats", "owner_user_id", "TEXT")
    _add_column_if_missing(connection, "messages", "author_user_id", "TEXT")
    _add_column_if_missing(connection, "messages", "sequence", "INTEGER")
    _add_column_if_missing(connection, "documents", "uploader_user_id", "TEXT")

    _backfill_message_sequences(connection)
    _migrate_embeddings(connection)

    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_chats_owner_user_id "
        "ON chats(owner_user_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_author_user_id "
        "ON messages(author_user_id)"
    )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_chat_sequence "
        "ON messages(chat_id, sequence) WHERE sequence IS NOT NULL"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_documents_uploader_user_id "
        "ON documents(uploader_user_id)"
    )


def _migration_2_auth_and_audit(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'member')),
            enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            password_changed_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE sessions (
            token_digest TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE setup_state (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            token_digest TEXT NOT NULL,
            created_at TEXT NOT NULL,
            consumed_at TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE audit_log (
            id TEXT PRIMARY KEY,
            actor_user_id TEXT,
            action TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT,
            outcome TEXT NOT NULL,
            details_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (actor_user_id) REFERENCES users(id)
        )
        """
    )
    connection.execute(
        "CREATE INDEX idx_sessions_user_id ON sessions(user_id)"
    )
    connection.execute(
        "CREATE INDEX idx_sessions_expires_at ON sessions(expires_at)"
    )
    connection.execute(
        "CREATE INDEX idx_users_role_enabled ON users(role, enabled)"
    )
    connection.execute(
        "CREATE INDEX idx_audit_created_at ON audit_log(created_at DESC)"
    )


def _migration_3_module_registry(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE module_registrations (
            id TEXT PRIMARY KEY,
            module_id TEXT NOT NULL UNIQUE,
            instance_id TEXT NOT NULL,
            base_url TEXT NOT NULL,
            module_name TEXT NOT NULL,
            module_description TEXT NOT NULL,
            module_version TEXT NOT NULL,
            protocol_version TEXT NOT NULL,
            manifest_json TEXT NOT NULL,
            manifest_digest TEXT NOT NULL,
            permission_digest TEXT NOT NULL,
            reviewed_manifest_digest TEXT,
            reviewed_permission_digest TEXT,
            reviewed_module_version TEXT,
            credential_digest TEXT NOT NULL,
            lifecycle_state TEXT NOT NULL
                CHECK (
                    lifecycle_state IN (
                        'pending_review',
                        'enabled',
                        'draining',
                        'disabled'
                    )
                ),
            health_status TEXT NOT NULL
                CHECK (
                    health_status IN (
                        'healthy',
                        'unreachable',
                        'incompatible'
                    )
                ),
            ready_status TEXT NOT NULL
                CHECK (
                    ready_status IN (
                        'unknown',
                        'ready',
                        'not_ready'
                    )
                ),
            config_status TEXT NOT NULL
                CHECK (
                    config_status IN (
                        'unknown',
                        'configured',
                        'missing'
                    )
                ),
            config_revision TEXT,
            created_by_user_id TEXT NOT NULL,
            reviewed_by_user_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_checked_at TEXT,
            FOREIGN KEY (created_by_user_id) REFERENCES users(id),
            FOREIGN KEY (reviewed_by_user_id) REFERENCES users(id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE module_capability_grants (
            registration_id TEXT NOT NULL,
            capability TEXT NOT NULL,
            granted_by_user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (registration_id, capability),
            FOREIGN KEY (registration_id)
                REFERENCES module_registrations(id) ON DELETE CASCADE,
            FOREIGN KEY (granted_by_user_id) REFERENCES users(id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE module_feature_suites (
            registration_id TEXT PRIMARY KEY,
            companion_plugin_id TEXT NOT NULL,
            companion_plugin_version_range TEXT NOT NULL,
            dependency_status TEXT NOT NULL
                CHECK (
                    dependency_status IN (
                        'unknown',
                        'plugin_missing',
                        'plugin_disabled',
                        'plugin_incompatible',
                        'ready'
                    )
                ),
            checked_at TEXT,
            FOREIGN KEY (registration_id)
                REFERENCES module_registrations(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        "CREATE INDEX idx_modules_lifecycle "
        "ON module_registrations(lifecycle_state)"
    )
    connection.execute(
        "CREATE INDEX idx_modules_health "
        "ON module_registrations(health_status)"
    )
    connection.execute(
        "CREATE INDEX idx_module_capability_grants_registration "
        "ON module_capability_grants(registration_id)"
    )


def _migration_4_module_tasks(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE module_tasks (
            id TEXT PRIMARY KEY,
            registration_id TEXT NOT NULL,
            module_id TEXT NOT NULL,
            module_version TEXT NOT NULL,
            action_id TEXT NOT NULL,
            action_version TEXT NOT NULL,
            action_contract_json TEXT NOT NULL,
            config_revision TEXT NOT NULL,
            creator_user_id TEXT NOT NULL,
            chat_id TEXT,
            idempotency_key TEXT NOT NULL,
            request_digest TEXT NOT NULL,
            state TEXT NOT NULL
                CHECK (
                    state IN (
                        'submitting',
                        'queued',
                        'running',
                        'waiting_approval',
                        'cancel_requested',
                        'succeeded',
                        'failed',
                        'cancelled',
                        'abandoned'
                    )
                ),
            visible INTEGER NOT NULL DEFAULT 0
                CHECK (visible IN (0, 1)),
            status_sync TEXT NOT NULL DEFAULT 'current'
                CHECK (status_sync IN ('current', 'unreachable')),
            outcome_code TEXT,
            last_cursor INTEGER NOT NULL DEFAULT 0
                CHECK (last_cursor >= 0),
            user_message_id TEXT,
            assistant_message_id TEXT,
            projection_state TEXT NOT NULL DEFAULT 'pending'
                CHECK (
                    projection_state IN (
                        'pending',
                        'projected',
                        'suppressed'
                    )
                ),
            created_at TEXT NOT NULL,
            accepted_at TEXT,
            updated_at TEXT NOT NULL,
            terminal_at TEXT,
            FOREIGN KEY (creator_user_id) REFERENCES users(id),
            UNIQUE (creator_user_id, idempotency_key)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE module_task_resource_refs (
            task_id TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            PRIMARY KEY (task_id, resource_id),
            FOREIGN KEY (task_id)
                REFERENCES module_tasks(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE module_task_artifacts (
            artifact_ref TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            artifact_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            media_type TEXT NOT NULL,
            size INTEGER NOT NULL CHECK (size >= 0),
            expires_at TEXT,
            created_at TEXT NOT NULL,
            UNIQUE (task_id, artifact_id),
            FOREIGN KEY (task_id)
                REFERENCES module_tasks(id) ON DELETE CASCADE
        )
        """
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
            use_count INTEGER NOT NULL DEFAULT 0 CHECK (use_count >= 0),
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
        "CREATE INDEX idx_module_tasks_visible_updated "
        "ON module_tasks(visible, updated_at DESC)"
    )
    connection.execute(
        "CREATE INDEX idx_module_tasks_chat_active "
        "ON module_tasks(chat_id, state) WHERE visible = 1"
    )
    connection.execute(
        "CREATE INDEX idx_module_tasks_creator "
        "ON module_tasks(creator_user_id, updated_at DESC)"
    )
    connection.execute(
        "CREATE INDEX idx_module_task_resources_resource "
        "ON module_task_resource_refs(resource_id)"
    )
    connection.execute(
        "CREATE INDEX idx_module_capability_task "
        "ON module_capability_tokens(task_id, capability)"
    )


def _migration_5_frozen_task_action_contract(
    connection: sqlite3.Connection,
) -> None:
    if "action_contract_json" not in _columns(connection, "module_tasks"):
        connection.execute(
            "ALTER TABLE module_tasks "
            "ADD COLUMN action_contract_json TEXT NOT NULL DEFAULT '{}'"
        )
    rows = connection.execute(
        """
        SELECT tasks.id, tasks.action_id, tasks.action_version,
               registrations.manifest_json
        FROM module_tasks AS tasks
        LEFT JOIN module_registrations AS registrations
          ON registrations.id = tasks.registration_id
        WHERE tasks.action_contract_json = '{}'
        """
    ).fetchall()
    for row in rows:
        if not row["manifest_json"]:
            continue
        try:
            manifest = json.loads(row["manifest_json"])
        except json.JSONDecodeError:
            continue
        action = next(
            (
                candidate
                for candidate in manifest.get("actions", [])
                if candidate.get("action_id") == row["action_id"]
                and candidate.get("action_version") == row["action_version"]
            ),
            None,
        )
        if action is not None:
            connection.execute(
                """
                UPDATE module_tasks SET action_contract_json = ?
                WHERE id = ?
                """,
                (
                    json.dumps(
                        action,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    row["id"],
                ),
            )


def _migration_6_task_approval_audit(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE module_task_approval_audit (
            task_id TEXT NOT NULL,
            approval_id TEXT NOT NULL,
            decision TEXT NOT NULL
                CHECK (decision IN ('approve', 'deny')),
            actor_user_id TEXT NOT NULL,
            resolved_at TEXT NOT NULL,
            PRIMARY KEY (task_id, approval_id),
            FOREIGN KEY (task_id)
                REFERENCES module_tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (actor_user_id) REFERENCES users(id)
        )
        """
    )
    connection.execute(
        "CREATE INDEX idx_module_task_approvals_actor "
        "ON module_task_approval_audit(actor_user_id, resolved_at DESC)"
    )


def _migration_7_module_feature_visibility(
    connection: sqlite3.Connection,
) -> None:
    _add_column_if_missing(
        connection,
        "module_registrations",
        "enabled_once",
        "INTEGER NOT NULL DEFAULT 0 CHECK (enabled_once IN (0, 1))",
    )
    connection.execute(
        """
        UPDATE module_registrations
        SET enabled_once = 1
        WHERE lifecycle_state IN ('enabled', 'draining', 'disabled')
        """
    )


def _migration_8_frontend_integrations(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        "ALTER TABLE module_feature_suites "
        "RENAME TO module_feature_suites_plugin_legacy"
    )
    connection.execute(
        """
        CREATE TABLE module_feature_suites (
            registration_id TEXT PRIMARY KEY,
            integration_mode TEXT NOT NULL
                CHECK (integration_mode IN ('plugin', 'resident')),
            integration_id TEXT NOT NULL,
            integration_version_range TEXT NOT NULL,
            dependency_status TEXT NOT NULL
                CHECK (
                    dependency_status IN (
                        'unknown',
                        'plugin_missing',
                        'plugin_disabled',
                        'plugin_incompatible',
                        'resident_missing',
                        'resident_incompatible',
                        'ready'
                    )
                ),
            checked_at TEXT,
            FOREIGN KEY (registration_id)
                REFERENCES module_registrations(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        INSERT INTO module_feature_suites (
            registration_id, integration_mode, integration_id,
            integration_version_range, dependency_status, checked_at
        )
        SELECT registration_id, 'plugin', companion_plugin_id,
               companion_plugin_version_range, dependency_status, checked_at
        FROM module_feature_suites_plugin_legacy
        """
    )
    connection.execute("DROP TABLE module_feature_suites_plugin_legacy")


def _migration_9_module_task_resources(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        "ALTER TABLE module_capability_tokens "
        "RENAME TO module_capability_tokens_v8"
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
                        'resource.stream',
                        'model.invoke'
                    )
                ),
            scope_json TEXT NOT NULL,
            use_count INTEGER NOT NULL DEFAULT 0 CHECK (use_count >= 0),
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
        """
        INSERT INTO module_capability_tokens (
            token_digest, task_id, registration_id, capability,
            scope_json, use_count, max_uses, created_at, expires_at,
            revoked_at
        )
        SELECT token_digest, task_id, registration_id, capability,
               scope_json, use_count, max_uses, created_at, expires_at,
               revoked_at
        FROM module_capability_tokens_v8
        """
    )
    connection.execute("DROP TABLE module_capability_tokens_v8")
    connection.execute(
        "CREATE INDEX idx_module_capability_task "
        "ON module_capability_tokens(task_id, capability)"
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
            bound_task_id TEXT,
            FOREIGN KEY (creator_user_id) REFERENCES users(id),
            FOREIGN KEY (bound_task_id)
                REFERENCES module_tasks(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE module_task_output_resources (
            resource_ref TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            media_type TEXT NOT NULL,
            size INTEGER NOT NULL CHECK (size >= 0),
            expires_at TEXT,
            created_at TEXT NOT NULL,
            UNIQUE (task_id, resource_id),
            FOREIGN KEY (task_id)
                REFERENCES module_tasks(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        "CREATE INDEX idx_module_task_input_resources_expiry "
        "ON module_task_input_resources(expires_at)"
    )
    connection.execute(
        "CREATE INDEX idx_module_task_output_resources_task "
        "ON module_task_output_resources(task_id, created_at)"
    )


def _migration_10_agent_host_capabilities(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        "ALTER TABLE module_capability_tokens "
        "RENAME TO module_capability_tokens_v9"
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
                        'principal.read',
                        'resource.read',
                        'resource.stream',
                        'model.invoke',
                        'model.chat.completions',
                        'skill.read'
                    )
                ),
            scope_json TEXT NOT NULL,
            use_count INTEGER NOT NULL DEFAULT 0 CHECK (use_count >= 0),
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
        """
        INSERT INTO module_capability_tokens (
            token_digest, task_id, registration_id, capability,
            scope_json, use_count, max_uses, created_at, expires_at,
            revoked_at
        )
        SELECT token_digest, task_id, registration_id, capability,
               scope_json, use_count, max_uses, created_at, expires_at,
               revoked_at
        FROM module_capability_tokens_v9
        """
    )
    connection.execute("DROP TABLE module_capability_tokens_v9")
    connection.execute(
        "CREATE INDEX idx_module_capability_task "
        "ON module_capability_tokens(task_id, capability)"
    )


def _migration_11_personal_agent_skills(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        """
        CREATE TABLE agent_skills (
            id TEXT PRIMARY KEY,
            owner_user_id TEXT NOT NULL,
            target_module_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            license TEXT NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1
                CHECK (enabled IN (0, 1)),
            active_version_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (owner_user_id, target_module_id, name),
            FOREIGN KEY (owner_user_id) REFERENCES users(id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE agent_skill_versions (
            id TEXT PRIMARY KEY,
            skill_id TEXT NOT NULL,
            commit_sha TEXT NOT NULL,
            content_sha256 TEXT NOT NULL,
            source_json TEXT NOT NULL,
            skill_markdown TEXT NOT NULL,
            resources_json TEXT NOT NULL,
            package_path TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            UNIQUE (skill_id, content_sha256),
            FOREIGN KEY (skill_id)
                REFERENCES agent_skills(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE module_task_skill_activations (
            task_id TEXT NOT NULL,
            ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
            skill_id TEXT NOT NULL,
            version_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (task_id, skill_id),
            UNIQUE (task_id, ordinal),
            FOREIGN KEY (task_id)
                REFERENCES module_tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (skill_id) REFERENCES agent_skills(id),
            FOREIGN KEY (version_id) REFERENCES agent_skill_versions(id)
        )
        """
    )
    connection.execute(
        "CREATE INDEX idx_agent_skills_owner_target "
        "ON agent_skills(owner_user_id, target_module_id, updated_at)"
    )
    connection.execute(
        "CREATE INDEX idx_agent_skill_versions_skill "
        "ON agent_skill_versions(skill_id, created_at)"
    )
    connection.execute(
        "CREATE INDEX idx_module_task_skill_activations_task "
        "ON module_task_skill_activations(task_id, ordinal)"
    )


def _migration_12_agent_compiled_rules(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        """
        CREATE TABLE agent_rule_documents (
            id TEXT PRIMARY KEY,
            owner_user_id TEXT NOT NULL,
            target_module_id TEXT NOT NULL,
            name TEXT NOT NULL,
            current_source_version_id TEXT NOT NULL,
            active_compiled_version_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (owner_user_id, target_module_id, name),
            FOREIGN KEY (owner_user_id) REFERENCES users(id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE agent_rule_source_versions (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            version_number INTEGER NOT NULL CHECK (version_number >= 1),
            source_document TEXT NOT NULL,
            content_sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (document_id, version_number),
            FOREIGN KEY (document_id)
                REFERENCES agent_rule_documents(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE agent_compiled_rule_versions (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            source_version_id TEXT NOT NULL,
            specification_version TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('valid', 'invalid')),
            content_sha256 TEXT NOT NULL,
            compiled_json TEXT,
            model_output TEXT NOT NULL,
            validation_errors_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (document_id)
                REFERENCES agent_rule_documents(id) ON DELETE CASCADE,
            FOREIGN KEY (source_version_id)
                REFERENCES agent_rule_source_versions(id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE module_task_rule_activations (
            task_id TEXT NOT NULL,
            ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
            document_id TEXT NOT NULL,
            compiled_version_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (task_id, document_id),
            UNIQUE (task_id, ordinal),
            FOREIGN KEY (task_id)
                REFERENCES module_tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (document_id) REFERENCES agent_rule_documents(id),
            FOREIGN KEY (compiled_version_id)
                REFERENCES agent_compiled_rule_versions(id)
        )
        """
    )
    connection.execute(
        "ALTER TABLE module_capability_tokens "
        "RENAME TO module_capability_tokens_v11"
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
                        'principal.read',
                        'resource.read',
                        'resource.stream',
                        'model.invoke',
                        'model.chat.completions',
                        'skill.read',
                        'rule.read'
                    )
                ),
            scope_json TEXT NOT NULL,
            use_count INTEGER NOT NULL DEFAULT 0 CHECK (use_count >= 0),
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
        """
        INSERT INTO module_capability_tokens (
            token_digest, task_id, registration_id, capability,
            scope_json, use_count, max_uses, created_at, expires_at,
            revoked_at
        )
        SELECT token_digest, task_id, registration_id, capability,
               scope_json, use_count, max_uses, created_at, expires_at,
               revoked_at
        FROM module_capability_tokens_v11
        """
    )
    connection.execute("DROP TABLE module_capability_tokens_v11")
    connection.execute(
        "CREATE INDEX idx_module_capability_task "
        "ON module_capability_tokens(task_id, capability)"
    )
    connection.execute(
        "CREATE INDEX idx_agent_rule_documents_owner "
        "ON agent_rule_documents(owner_user_id, target_module_id, updated_at)"
    )
    connection.execute(
        "CREATE INDEX idx_agent_rule_sources_document "
        "ON agent_rule_source_versions(document_id, version_number)"
    )
    connection.execute(
        "CREATE INDEX idx_agent_compiled_rules_document "
        "ON agent_compiled_rule_versions(document_id, created_at)"
    )
    connection.execute(
        "CREATE INDEX idx_module_task_rule_activations_task "
        "ON module_task_rule_activations(task_id, ordinal)"
    )


MIGRATIONS = (
    (1, "server_shared_data", _migration_1_server_shared_data),
    (2, "auth_and_audit", _migration_2_auth_and_audit),
    (3, "module_registry", _migration_3_module_registry),
    (4, "module_tasks", _migration_4_module_tasks),
    (
        5,
        "frozen_task_action_contract",
        _migration_5_frozen_task_action_contract,
    ),
    (6, "task_approval_audit", _migration_6_task_approval_audit),
    (
        7,
        "module_feature_visibility",
        _migration_7_module_feature_visibility,
    ),
    (
        8,
        "frontend_integrations",
        _migration_8_frontend_integrations,
    ),
    (
        9,
        "module_task_resources",
        _migration_9_module_task_resources,
    ),
    (
        10,
        "agent_host_capabilities",
        _migration_10_agent_host_capabilities,
    ),
    (
        11,
        "personal_agent_skills",
        _migration_11_personal_agent_skills,
    ),
    (
        12,
        "agent_compiled_rules",
        _migration_12_agent_compiled_rules,
    ),
)


def apply_migrations(connection: sqlite3.Connection) -> int:
    version = assert_supported_schema(connection)
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        for migration_version, name, migrate in MIGRATIONS:
            if migration_version <= version:
                continue
            migrate(connection)
            connection.execute(
                """
                INSERT INTO schema_migrations (version, name, applied_at)
                VALUES (?, ?, ?)
                """,
                (migration_version, name, _utc_now()),
            )
            version = migration_version
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    return version
