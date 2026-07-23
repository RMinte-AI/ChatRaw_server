#!/usr/bin/env python3
"""HTTP phases for the T8 Compose backup and restore acceptance."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class AcceptanceError(RuntimeError):
    pass


class Client:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
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
        headers = {"Accept": "application/json", "Origin": self.base_url}
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


def _login(base_url: str, username: str, password: str) -> Client:
    client = Client(base_url)
    client.request(
        "POST",
        "/api/auth/login",
        {"username": username, "password": password},
    )
    return client


def bootstrap(arguments: argparse.Namespace) -> None:
    admin = Client(arguments.base_url)
    admin.request(
        "POST",
        "/api/setup/admin",
        {
            "setup_token": arguments.setup_token,
            "username": "t8composeadmin",
            "password": "t8-compose-admin-password-2026",
        },
    )
    admin = _login(
        arguments.base_url,
        "t8composeadmin",
        "t8-compose-admin-password-2026",
    )
    admin.request(
        "POST",
        "/api/admin/users",
        {
            "username": "t8composemember",
            "password": "t8-compose-member-password-2026",
            "role": "member",
        },
    )
    chat = admin.request("POST", "/api/chats")
    admin.request(
        "PATCH",
        f"/api/chats/{chat['id']}",
        {"title": "T8 Compose recovery chat"},
    )
    arguments.state_file.write_text(
        json.dumps({"chat_id": chat["id"]}) + "\n",
        encoding="utf-8",
    )
    print("T8 Compose bootstrap passed")


def verify(arguments: argparse.Namespace) -> None:
    state = json.loads(arguments.state_file.read_text(encoding="utf-8"))
    for username, password, role in (
        (
            "t8composeadmin",
            "t8-compose-admin-password-2026",
            "admin",
        ),
        (
            "t8composemember",
            "t8-compose-member-password-2026",
            "member",
        ),
    ):
        client = _login(arguments.base_url, username, password)
        if client.request("GET", "/api/me")["role"] != role:
            raise AcceptanceError(f"{username} role was not restored")
        chats = client.request("GET", "/api/chats")
        if not any(
            chat["id"] == state["chat_id"]
            and chat["title"] == "T8 Compose recovery chat"
            for chat in chats
        ):
            raise AcceptanceError(f"{username} cannot see restored chat")
    print("T8 Compose restored admin/member data passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["bootstrap", "verify"])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--setup-token")
    arguments = parser.parse_args()
    if arguments.phase == "bootstrap":
        if not arguments.setup_token:
            parser.error("--setup-token is required for bootstrap")
        bootstrap(arguments)
    else:
        verify(arguments)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AcceptanceError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"success": False, "error": str(error)}))
        raise SystemExit(1)
