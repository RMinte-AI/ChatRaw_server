#!/usr/bin/env python3
"""Real source-runtime acceptance for classic import and backup recovery."""

from __future__ import annotations

import hashlib
import http.cookiejar
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

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


class AcceptanceError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _create_classic_data(root: Path) -> Path:
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
            ('model-1', 'Classic', 'fixture-secret',
             'https://example.test/v1', 'classic', 8192, 4096,
             'chat', '{}', '2025-01-01T00:00:00')
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
        VALUES ('chat-1', 'summary', 'message-1',
                '2025-01-01T00:00:01', 100, 20, 1,
                '2025-01-01T00:00:02')
        """
    )
    connection.execute(
        """
        INSERT INTO chat_skill_activations
            (id, chat_id, message_id, skill_name, source_json, created_at)
        VALUES ('activation-1', 'chat-1', 'message-1', 'classic-skill',
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
    (data_dir / "plugins").mkdir()
    (data_dir / "skills").mkdir()
    (data_dir / "plugins" / "config.json").write_text(
        '{"plugins":{"classic":{"enabled":true}}}\n',
        encoding="utf-8",
    )
    (data_dir / "skills" / "config.json").write_text(
        '{"classic-skill":{"enabled":true}}\n',
        encoding="utf-8",
    )
    return data_dir


def _run_data_command(*arguments: str) -> dict[str, Any]:
    process = subprocess.run(
        [
            sys.executable,
            str(REPOSITORY_ROOT / "backend" / "server_data.py"),
            *arguments,
        ],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise AcceptanceError(
            f"data command failed: {process.stdout}\n{process.stderr}"
        )
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise AcceptanceError(
            f"data command returned invalid JSON: {process.stdout}"
        ) from error
    if payload.get("success") is not True:
        raise AcceptanceError(f"data command rejected: {payload}")
    return payload["result"]


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


class Client:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        data = None
        headers = {
            "Accept": "application/json",
            "Origin": self.base_url,
        }
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with self.opener.open(request, timeout=10) as response:
                body = response.read()
        except urllib.error.HTTPError as error:
            raise AcceptanceError(
                f"{method} {path} returned {error.code}: "
                f"{error.read().decode('utf-8', errors='replace')}"
            ) from error
        return json.loads(body) if body else None


def _start_server(data_dir: Path) -> tuple[subprocess.Popen, str, Any]:
    port = _free_port()
    log = (data_dir / "t8-server.log").open("w", encoding="utf-8")
    environment = os.environ.copy()
    environment.update(
        {
            "DATA_DIR": str(data_dir),
            "PORT": str(port),
            "CHATRAW_LOOPBACK_DEV": "1",
        }
    )
    process = subprocess.Popen(
        [sys.executable, str(REPOSITORY_ROOT / "backend" / "main.py")],
        cwd=REPOSITORY_ROOT,
        env=environment,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    base_url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        if process.poll() is not None:
            log.close()
            raise AcceptanceError(
                f"Server exited during startup; see {data_dir / 't8-server.log'}"
            )
        try:
            with urllib.request.urlopen(base_url + "/ready", timeout=1) as response:
                if json.load(response).get("status") == "ready":
                    return process, base_url, log
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            pass
        time.sleep(0.1)
    process.terminate()
    process.wait(timeout=10)
    log.close()
    raise AcceptanceError("Server did not become ready")


def _stop_server(process: subprocess.Popen, log: Any) -> None:
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    log.close()


def _assert_chat_titles(client: Client, expected: set[str]) -> None:
    chats = client.request("GET", "/api/chats")
    titles = {chat["title"] for chat in chats}
    missing = expected - titles
    if missing:
        raise AcceptanceError(f"restored chat titles are missing: {sorted(missing)}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="chatraw-t8-recovery-") as temp:
        root = Path(temp)
        classic = _create_classic_data(root)
        classic_files = {
            path.relative_to(classic).as_posix(): _sha256(path)
            for path in sorted(classic.rglob("*"))
            if path.is_file()
        }
        server_data = root / "server-data"
        imported = _run_data_command(
            "import-classic",
            "--source-data-dir",
            str(classic),
            "--server-data-dir",
            str(server_data),
            "--confirm-source-quiesced",
        )
        if imported["validation"] != {
            "source_unchanged": True,
            "table_counts_and_content_equal": True,
            "legacy_owners_null": True,
        }:
            raise AcceptanceError("classic import validation was incomplete")

        subprocess.run(
            [
                sys.executable,
                str(REPOSITORY_ROOT / "scripts" / "prepare-server-secrets.py"),
                "--data-dir",
                str(server_data),
                "--quiet",
            ],
            cwd=REPOSITORY_ROOT,
            check=True,
        )
        setup_token = (
            server_data / "secrets" / "setup-token"
        ).read_text(encoding="utf-8").strip()
        process, base_url, log = _start_server(server_data)
        try:
            admin = Client(base_url)
            admin.request(
                "POST",
                "/api/setup/admin",
                {
                    "setup_token": setup_token,
                    "username": "t8admin",
                    "password": "t8-admin-password-strong-2026",
                },
            )
            admin.request(
                "POST",
                "/api/auth/login",
                {
                    "username": "t8admin",
                    "password": "t8-admin-password-strong-2026",
                },
            )
            _assert_chat_titles(admin, {"Classic chat"})
            messages = admin.request("GET", "/api/chats/chat-1/messages")
            if [message["content"] for message in messages] != ["hello", "world"]:
                raise AcceptanceError("classic messages changed during import")
            admin.request(
                "POST",
                "/api/admin/users",
                {
                    "username": "t8member",
                    "password": "t8-member-password-strong-2026",
                    "role": "member",
                },
            )
            created = admin.request("POST", "/api/chats")
            admin.request(
                "PATCH",
                f"/api/chats/{created['id']}",
                {"title": "Post-import chat"},
            )
        finally:
            _stop_server(process, log)

        backup = root / "backup"
        backed_up = _run_data_command(
            "backup",
            "--data-dir",
            str(server_data),
            "--backup-dir",
            str(backup),
            "--confirm-source-quiesced",
        )
        if backed_up.get("source_unchanged") is not True:
            raise AcceptanceError("backup changed its source")
        verified = _run_data_command(
            "verify",
            "--backup-dir",
            str(backup),
        )
        if verified.get("valid") is not True:
            raise AcceptanceError("backup verification failed")

        restored = root / "restored-data"
        _run_data_command(
            "restore",
            "--backup-dir",
            str(backup),
            "--data-dir",
            str(restored),
            "--confirm-destination-quiesced",
        )
        process, base_url, log = _start_server(restored)
        try:
            admin = Client(base_url)
            admin.request(
                "POST",
                "/api/auth/login",
                {
                    "username": "t8admin",
                    "password": "t8-admin-password-strong-2026",
                },
            )
            _assert_chat_titles(admin, {"Classic chat", "Post-import chat"})
            member = Client(base_url)
            member.request(
                "POST",
                "/api/auth/login",
                {
                    "username": "t8member",
                    "password": "t8-member-password-strong-2026",
                },
            )
            _assert_chat_titles(member, {"Classic chat", "Post-import chat"})
        finally:
            _stop_server(process, log)

        classic_after = {
            path.relative_to(classic).as_posix(): _sha256(path)
            for path in sorted(classic.rglob("*"))
            if path.is_file()
        }
        if classic_after != classic_files:
            raise AcceptanceError("classic source data was modified")

        print(
            json.dumps(
                {
                    "success": True,
                    "fresh_server_setup": True,
                    "classic_import": imported["validation"],
                    "admin_login_after_restore": True,
                    "member_login_after_restore": True,
                    "backup_verified": verified,
                    "classic_source_unchanged": True,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AcceptanceError, OSError, sqlite3.Error, subprocess.SubprocessError) as error:
        print(json.dumps({"success": False, "error": str(error)}))
        raise SystemExit(1)
