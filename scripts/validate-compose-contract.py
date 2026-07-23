#!/usr/bin/env python3
"""Validate the frozen T6 Compose security and network contract."""

from __future__ import annotations

import argparse
import json
import sys


def fail(message: str) -> None:
    raise SystemExit(message)


def _forbidden_runtime(service: dict, name: str) -> None:
    if service.get("network_mode") == "host":
        fail(f"{name} must not use host networking")
    if service.get("privileged"):
        fail(f"{name} must not be privileged")
    for volume in service.get("volumes", []):
        source = volume.get("source", "") if isinstance(volume, dict) else str(volume)
        target = volume.get("target", "") if isinstance(volume, dict) else str(volume)
        if "docker.sock" in source or "docker.sock" in target:
            fail(f"{name} must not mount the Docker socket")


def validate_server(config: dict) -> None:
    services = config.get("services", {})
    if set(services) != {"chatraw"}:
        fail("Server Compose may manage only the ChatRaw service")
    chatraw = services["chatraw"]
    _forbidden_runtime(chatraw, "chatraw")
    if not chatraw.get("ports"):
        fail("ChatRaw must publish its WebUI port")
    if set(chatraw.get("networks", {})) != {"module_bridge"}:
        fail("ChatRaw must join only the shared module bridge")
    if chatraw.get("extra_hosts") != [
        "host.docker.internal=host-gateway"
    ]:
        fail("Linux host access must use the explicit host-gateway mapping")
    bridge = config.get("networks", {}).get("module_bridge", {})
    if not bridge.get("external"):
        fail("The module bridge must be external")


def validate_module(config: dict) -> None:
    services = config.get("services", {})
    if set(services) != {"reference-module", "reference-private"}:
        fail("Reference Compose service set is unexpected")
    module = services["reference-module"]
    private = services["reference-private"]
    _forbidden_runtime(module, "reference-module")
    _forbidden_runtime(private, "reference-private")
    if module.get("ports") or private.get("ports"):
        fail("Module services must not publish host ports")
    if set(module.get("networks", {})) != {
        "module_bridge",
        "module_private",
    }:
        fail("Reference module must join northbound and private networks")
    if set(private.get("networks", {})) != {"module_private"}:
        fail("Private dependency must join only the private network")
    networks = config.get("networks", {})
    if not networks.get("module_bridge", {}).get("external"):
        fail("Northbound module bridge must be external")
    if not networks.get("module_private", {}).get("internal"):
        fail("Downstream dependency network must be internal")
    if not config.get("volumes", {}).get("reference_module_data"):
        fail("Reference module must own a persistent volume")
    if not module.get("healthcheck") or not private.get("healthcheck"):
        fail("Both reference services require healthchecks")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("server", "module"))
    arguments = parser.parse_args()
    config = json.load(sys.stdin)
    if arguments.kind == "server":
        validate_server(config)
    else:
        validate_module(config)
    print(f"T6 {arguments.kind} Compose contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
