#!/usr/bin/env python3
"""Validate the T7 Agent and private LinkDB Compose boundary."""

from __future__ import annotations

import argparse
import json
import sys


def fail(message: str) -> None:
    raise SystemExit(message)


def forbid_privileged_runtime(service: dict, name: str) -> None:
    if service.get("network_mode") == "host":
        fail(f"{name} must not use host networking")
    if service.get("privileged"):
        fail(f"{name} must not be privileged")
    if service.get("ports"):
        fail(f"{name} must not publish a host port")
    for volume in service.get("volumes", []):
        source = (
            volume.get("source", "")
            if isinstance(volume, dict)
            else str(volume)
        )
        target = (
            volume.get("target", "")
            if isinstance(volume, dict)
            else str(volume)
        )
        if "docker.sock" in source or "docker.sock" in target:
            fail(f"{name} must not mount the Docker socket")


def validate_agent(config: dict) -> None:
    services = config.get("services", {})
    if set(services) != {"chatraw-agent"}:
        fail("Agent Compose may manage only ChatRaw Agent")
    agent = services["chatraw-agent"]
    forbid_privileged_runtime(agent, "chatraw-agent")
    if set(agent.get("networks", {})) != {
        "chatraw_modules",
        "agent_linkdb",
    }:
        fail("Agent must join exactly northbound and private networks")
    if not agent.get("healthcheck"):
        fail("Agent requires a healthcheck")
    if not agent.get("volumes"):
        fail("Agent requires persistent data")
    networks = config.get("networks", {})
    for name in ("chatraw_modules", "agent_linkdb"):
        if not networks.get(name, {}).get("external"):
            fail(f"{name} must be externally managed")


def validate_linkdb_fixture(config: dict) -> None:
    services = config.get("services", {})
    if set(services) != {"t7-linkdb"}:
        fail("T7 LinkDB fixture service set is unexpected")
    linkdb = services["t7-linkdb"]
    forbid_privileged_runtime(linkdb, "t7-linkdb")
    if set(linkdb.get("networks", {})) != {"agent_linkdb"}:
        fail("LinkDB must join only the Agent private network")
    if not linkdb.get("healthcheck"):
        fail("LinkDB fixture requires a healthcheck")
    if not linkdb.get("volumes"):
        fail("LinkDB fixture requires persistent data")
    if not config.get("networks", {}).get(
        "agent_linkdb",
        {},
    ).get("external"):
        fail("Agent-LinkDB private network must be externally managed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("agent", "linkdb-fixture"))
    arguments = parser.parse_args()
    config = json.load(sys.stdin)
    if arguments.kind == "agent":
        validate_agent(config)
    else:
        validate_linkdb_fixture(config)
    print(f"T7 {arguments.kind} Compose contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
