"""Registration-only module registry for ChatRaw Module Protocol v1."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import os
import secrets
import socket
import ssl
import tempfile
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit

import aiohttp
import certifi
from aiohttp.abc import AbstractResolver, ResolveResult

try:
    from .db_runtime import database_connection
    from .module_protocol import (
        MAX_CONFIG_BYTES,
        MAX_MANIFEST_BYTES,
        ModuleProtocolError,
        canonical_json,
        integration_version_matches,
        digest_json,
        permission_digest,
        protocol_is_compatible,
        validate_config_update,
        validate_config_view,
        validate_manifest,
    )
except ImportError:
    from db_runtime import database_connection
    from module_protocol import (
        MAX_CONFIG_BYTES,
        MAX_MANIFEST_BYTES,
        ModuleProtocolError,
        canonical_json,
        integration_version_matches,
        digest_json,
        permission_digest,
        protocol_is_compatible,
        validate_config_update,
        validate_config_view,
        validate_manifest,
    )


MODULE_PATH_PREFIX = "/chatraw-module/v1"
PAIR_PATH = f"{MODULE_PATH_PREFIX}/pair"
MANIFEST_PATH = f"{MODULE_PATH_PREFIX}/manifest"
HEALTH_PATH = f"{MODULE_PATH_PREFIX}/health"
READY_PATH = f"{MODULE_PATH_PREFIX}/ready"
CONFIG_PATH = f"{MODULE_PATH_PREFIX}/config"
DISCONNECT_PATH = f"{MODULE_PATH_PREFIX}/disconnect"
PURGE_PATH = f"{MODULE_PATH_PREFIX}/purge-data"
MAX_PAIR_RESPONSE_BYTES = 32 * 1024
MAX_STATUS_RESPONSE_BYTES = 64 * 1024
MAX_PAIR_CODE_LENGTH = 512
MAX_TOKEN_LENGTH = 4096


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class ModuleRegistryError(RuntimeError):
    def __init__(
        self,
        code: str,
        public_message: str,
        *,
        status_code: int = 400,
    ):
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.status_code = status_code


class ModuleTransportError(ModuleRegistryError):
    pass


class ModuleAddressPolicy:
    def __init__(
        self,
        *,
        allowed_origins: set[str] | None = None,
        bridge_cidrs: list[str] | None = None,
        containerized: bool = False,
    ):
        self.containerized = containerized
        self.allowed_origins = {
            self._normalize_origin(origin)
            for origin in (allowed_origins or set())
            if origin
        }
        self.bridge_networks = []
        for raw_cidr in bridge_cidrs or []:
            try:
                self.bridge_networks.append(
                    ipaddress.ip_network(raw_cidr, strict=True)
                )
            except ValueError as error:
                raise ValueError(
                    f"Invalid module bridge CIDR: {raw_cidr}"
                ) from error

    @staticmethod
    def _normalize_origin(raw_url: str) -> str:
        parsed = urlsplit(raw_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("Module origin must be an HTTP(S) origin")
        hostname = parsed.hostname.lower()
        try:
            ip = ipaddress.ip_address(hostname)
            host = f"[{ip.compressed}]" if ip.version == 6 else ip.compressed
        except ValueError:
            host = hostname
        port = parsed.port
        if port is None:
            port = 443 if parsed.scheme == "https" else 80
        if not 1 <= port <= 65535:
            raise ValueError("Module origin port is invalid")
        default_port = (
            parsed.scheme == "https" and port == 443
        ) or (
            parsed.scheme == "http" and port == 80
        )
        netloc = host if default_port else f"{host}:{port}"
        return urlunsplit((parsed.scheme, netloc, "", "", ""))

    def normalize(self, raw_url: str) -> str:
        if not isinstance(raw_url, str) or len(raw_url) > 2048:
            raise ModuleAddressPolicy.denied()
        try:
            origin = self._normalize_origin(raw_url)
        except (ValueError, TypeError):
            raise ModuleAddressPolicy.denied() from None
        if self.containerized:
            hostname = (urlsplit(origin).hostname or "").lower()
            is_loopback = hostname == "localhost"
            if not is_loopback:
                try:
                    is_loopback = ipaddress.ip_address(hostname).is_loopback
                except ValueError:
                    is_loopback = False
            if is_loopback:
                raise ModuleRegistryError(
                    "module_loopback_unreachable_from_container",
                    (
                        "This ChatRaw Server runs in a container, so localhost "
                        "points back to ChatRaw. Use the module service name on "
                        "the configured shared module network."
                    ),
                    status_code=400,
                )
        return origin

    @staticmethod
    def denied() -> ModuleRegistryError:
        return ModuleRegistryError(
            "module_address_not_allowed",
            "Module address is not allowed",
            status_code=400,
        )

    def _ip_allowed(self, ip: Any) -> bool:
        if (
            ip.is_link_local
            or ip.is_multicast
            or ip.is_unspecified
            or ip.is_reserved
        ):
            return False
        if ip.is_loopback:
            return True
        return any(ip in network for network in self.bridge_networks)

    async def validate_and_resolve(self, raw_url: str) -> tuple[str, list[str]]:
        origin = self.normalize(raw_url)
        parsed = urlsplit(origin)
        hostname = parsed.hostname or ""
        if hostname.lower() in {
            "metadata",
            "metadata.google.internal",
            "instance-data",
            "instance-data.ec2.internal",
        }:
            raise self.denied()
        try:
            literal = ipaddress.ip_address(hostname)
            addresses = [literal]
        except ValueError:
            try:
                infos = await asyncio.get_running_loop().getaddrinfo(
                    hostname,
                    parsed.port,
                    family=socket.AF_UNSPEC,
                    type=socket.SOCK_STREAM,
                )
            except OSError:
                raise ModuleTransportError(
                    "module_unreachable",
                    "Module is unreachable",
                    status_code=502,
                ) from None
            addresses = []
            for info in infos:
                try:
                    address = ipaddress.ip_address(info[4][0])
                except ValueError:
                    continue
                if address not in addresses:
                    addresses.append(address)
        if not addresses:
            raise ModuleTransportError(
                "module_unreachable",
                "Module is unreachable",
                status_code=502,
            )
        if origin in self.allowed_origins:
            if any(
                address.is_link_local
                or address.is_multicast
                or address.is_unspecified
                or address.is_reserved
                for address in addresses
            ):
                raise self.denied()
            if parsed.scheme != "https" and not all(
                self._ip_allowed(address) for address in addresses
            ):
                raise self.denied()
            return origin, [address.compressed for address in addresses]
        if not all(self._ip_allowed(address) for address in addresses):
            raise self.denied()
        return origin, [address.compressed for address in addresses]


class _PinnedResolver(AbstractResolver):
    def __init__(self, hostname: str, addresses: list[str]):
        self.hostname = hostname.lower()
        self.addresses = tuple(addresses)

    async def resolve(
        self,
        host: str,
        port: int = 0,
        family: socket.AddressFamily = socket.AF_INET,
    ) -> list[ResolveResult]:
        if host.lower() != self.hostname:
            raise OSError("unexpected DNS hostname")
        results = []
        for raw_address in self.addresses:
            address = ipaddress.ip_address(raw_address)
            address_family = (
                socket.AF_INET6 if address.version == 6 else socket.AF_INET
            )
            if family not in {socket.AF_UNSPEC, address_family}:
                continue
            results.append(
                ResolveResult(
                    hostname=host,
                    host=address.compressed,
                    port=port,
                    family=address_family,
                    proto=socket.IPPROTO_TCP,
                    flags=socket.AI_NUMERICHOST,
                )
            )
        if not results:
            raise OSError("no approved address for hostname")
        return results

    async def close(self) -> None:
        return None


class ModuleHttpClient:
    def __init__(
        self,
        address_policy: ModuleAddressPolicy,
        *,
        timeout_seconds: float = 10.0,
    ):
        self.address_policy = address_policy
        self.timeout_seconds = timeout_seconds

    async def request_json(
        self,
        base_url: str,
        path: str,
        *,
        method: str = "GET",
        token: str | None = None,
        payload: dict[str, Any] | None = None,
        max_bytes: int = MAX_STATUS_RESPONSE_BYTES,
    ) -> tuple[int, dict[str, Any]]:
        origin, resolved_addresses = (
            await self.address_policy.validate_and_resolve(base_url)
        )
        parsed_origin = urlsplit(origin)
        headers = {
            "Accept": "application/json",
            "User-Agent": "ChatRaw-Module-Registry/1",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        timeout = aiohttp.ClientTimeout(
            total=self.timeout_seconds,
            connect=min(5.0, self.timeout_seconds),
        )
        connector = aiohttp.TCPConnector(
            ssl=ssl.create_default_context(cafile=certifi.where()),
            resolver=_PinnedResolver(
                parsed_origin.hostname or "",
                resolved_addresses,
            ),
            use_dns_cache=False,
        )
        try:
            async with aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
            ) as session:
                async with session.request(
                    method,
                    f"{origin}{path}",
                    json=payload,
                    headers=headers,
                    allow_redirects=False,
                ) as response:
                    if 300 <= response.status < 400:
                        raise ModuleTransportError(
                            "module_redirect_forbidden",
                            "Module redirects are not allowed",
                            status_code=502,
                        )
                    content_type = response.headers.get(
                        "Content-Type", ""
                    ).split(";", 1)[0].strip().lower()
                    if content_type != "application/json":
                        raise ModuleTransportError(
                            "invalid_module_response",
                            "Module returned an invalid response",
                            status_code=502,
                        )
                    chunks = bytearray()
                    async for chunk in response.content.iter_chunked(
                        min(64 * 1024, max_bytes + 1)
                    ):
                        chunks.extend(chunk)
                        if len(chunks) > max_bytes:
                            raise ModuleTransportError(
                                "module_response_too_large",
                                "Module response exceeds the size limit",
                                status_code=502,
                            )
                    body = bytes(chunks)
                    try:
                        decoded = json.loads(body.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        raise ModuleTransportError(
                            "invalid_module_response",
                            "Module returned invalid JSON",
                            status_code=502,
                        ) from None
                    if not isinstance(decoded, dict):
                        raise ModuleTransportError(
                            "invalid_module_response",
                            "Module response must be an object",
                            status_code=502,
                        )
                    return response.status, decoded
        except ModuleRegistryError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            raise ModuleTransportError(
                "module_unreachable",
                "Module is unreachable",
                status_code=502,
            ) from None

    async def request_bytes(
        self,
        base_url: str,
        path: str,
        *,
        token: str,
        max_bytes: int,
    ) -> tuple[int, dict[str, str], bytes]:
        origin, resolved_addresses = (
            await self.address_policy.validate_and_resolve(base_url)
        )
        parsed_origin = urlsplit(origin)
        connector = aiohttp.TCPConnector(
            ssl=ssl.create_default_context(cafile=certifi.where()),
            resolver=_PinnedResolver(
                parsed_origin.hostname or "",
                resolved_addresses,
            ),
            use_dns_cache=False,
        )
        timeout = aiohttp.ClientTimeout(
            total=self.timeout_seconds,
            connect=min(5.0, self.timeout_seconds),
        )
        try:
            async with aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
            ) as session:
                async with session.get(
                    f"{origin}{path}",
                    headers={
                        "Accept": "*/*",
                        "Authorization": f"Bearer {token}",
                        "User-Agent": "ChatRaw-Module-Registry/1",
                    },
                    allow_redirects=False,
                ) as response:
                    if 300 <= response.status < 400:
                        raise ModuleTransportError(
                            "module_redirect_forbidden",
                            "Module redirects are not allowed",
                            status_code=502,
                        )
                    body = bytearray()
                    async for chunk in response.content.iter_chunked(
                        min(64 * 1024, max_bytes + 1)
                    ):
                        body.extend(chunk)
                        if len(body) > max_bytes:
                            raise ModuleTransportError(
                                "module_response_too_large",
                                "Module response exceeds the size limit",
                                status_code=502,
                            )
                    headers = {
                        key.lower(): value
                        for key, value in response.headers.items()
                        if key.lower()
                        in {
                            "content-type",
                            "content-length",
                            "content-disposition",
                        }
                    }
                    return response.status, headers, bytes(body)
        except ModuleRegistryError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            raise ModuleTransportError(
                "module_unreachable",
                "Module is unreachable",
                status_code=502,
            ) from None

    @asynccontextmanager
    async def stream_bytes(
        self,
        base_url: str,
        path: str,
        *,
        method: str,
        token: str,
        range_header: str | None = None,
    ):
        if method not in {"GET", "HEAD"}:
            raise ValueError("resource stream method must be GET or HEAD")
        origin, resolved_addresses = (
            await self.address_policy.validate_and_resolve(base_url)
        )
        parsed_origin = urlsplit(origin)
        connector = aiohttp.TCPConnector(
            ssl=ssl.create_default_context(cafile=certifi.where()),
            resolver=_PinnedResolver(
                parsed_origin.hostname or "",
                resolved_addresses,
            ),
            use_dns_cache=False,
        )
        timeout = aiohttp.ClientTimeout(
            total=None,
            connect=min(5.0, self.timeout_seconds),
            sock_read=max(30.0, self.timeout_seconds),
        )
        session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            auto_decompress=False,
        )
        response = None
        try:
            headers = {
                "Accept": "*/*",
                "Authorization": f"Bearer {token}",
                "User-Agent": "ChatRaw-Module-Registry/1",
            }
            if range_header is not None:
                headers["Range"] = range_header
            response = await session.request(
                method,
                f"{origin}{path}",
                headers=headers,
                allow_redirects=False,
            )
            if 300 <= response.status < 400:
                raise ModuleTransportError(
                    "module_redirect_forbidden",
                    "Module redirects are not allowed",
                    status_code=502,
                )
            yield response
        except ModuleRegistryError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            raise ModuleTransportError(
                "module_unreachable",
                "Module is unreachable",
                status_code=502,
            ) from None
        finally:
            if response is not None:
                response.release()
            await session.close()

    async def iter_sse(
        self,
        base_url: str,
        path: str,
        *,
        token: str,
        last_event_id: int,
        max_event_bytes: int,
    ):
        origin, resolved_addresses = (
            await self.address_policy.validate_and_resolve(base_url)
        )
        parsed_origin = urlsplit(origin)
        connector = aiohttp.TCPConnector(
            ssl=ssl.create_default_context(cafile=certifi.where()),
            resolver=_PinnedResolver(
                parsed_origin.hostname or "",
                resolved_addresses,
            ),
            use_dns_cache=False,
        )
        timeout = aiohttp.ClientTimeout(
            total=None,
            connect=min(5.0, self.timeout_seconds),
            sock_read=max(30.0, self.timeout_seconds),
        )
        try:
            async with aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
            ) as session:
                async with session.get(
                    f"{origin}{path}",
                    headers={
                        "Accept": "text/event-stream",
                        "Authorization": f"Bearer {token}",
                        "Last-Event-ID": str(last_event_id),
                        "Cache-Control": "no-cache",
                        "User-Agent": "ChatRaw-Module-Registry/1",
                    },
                    allow_redirects=False,
                ) as response:
                    if 300 <= response.status < 400:
                        raise ModuleTransportError(
                            "module_redirect_forbidden",
                            "Module redirects are not allowed",
                            status_code=502,
                        )
                    if response.status != 200:
                        raise ModuleTransportError(
                            "module_task_stream_rejected",
                            "Module rejected the task event stream",
                            status_code=502,
                        )
                    content_type = response.headers.get(
                        "Content-Type", ""
                    ).split(";", 1)[0].strip().lower()
                    if content_type != "text/event-stream":
                        raise ModuleTransportError(
                            "invalid_module_response",
                            "Module returned an invalid event stream",
                            status_code=502,
                        )
                    fields: dict[str, str] = {}
                    event_size = 0
                    while True:
                        line_bytes = await response.content.readline()
                        if not line_bytes:
                            break
                        event_size += len(line_bytes)
                        if event_size > max_event_bytes:
                            raise ModuleTransportError(
                                "module_response_too_large",
                                "Module event exceeds the size limit",
                                status_code=502,
                            )
                        try:
                            line = line_bytes.decode("utf-8").rstrip("\r\n")
                        except UnicodeDecodeError:
                            raise ModuleTransportError(
                                "invalid_module_response",
                                "Module returned invalid event data",
                                status_code=502,
                            ) from None
                        if line.startswith(":"):
                            if not fields:
                                event_size = 0
                                yield None
                            continue
                        if line == "":
                            if not fields:
                                event_size = 0
                                continue
                            try:
                                event_id = int(fields["id"])
                                event_name = fields["event"]
                                data = json.loads(fields["data"])
                            except (
                                KeyError,
                                ValueError,
                                json.JSONDecodeError,
                            ):
                                raise ModuleTransportError(
                                    "invalid_module_response",
                                    "Module returned invalid event data",
                                    status_code=502,
                                ) from None
                            yield {
                                "id": event_id,
                                "event": event_name,
                                "data": data,
                            }
                            fields = {}
                            event_size = 0
                            continue
                        name, separator, value = line.partition(":")
                        if not separator or name not in {"id", "event", "data"}:
                            raise ModuleTransportError(
                                "invalid_module_response",
                                "Module returned invalid event data",
                                status_code=502,
                            )
                        if name in fields:
                            raise ModuleTransportError(
                                "invalid_module_response",
                                "Module returned duplicate event fields",
                                status_code=502,
                            )
                        fields[name] = value.lstrip(" ")
                    if fields:
                        raise ModuleTransportError(
                            "invalid_module_response",
                            "Module returned a truncated event",
                            status_code=502,
                        )
        except ModuleRegistryError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            raise ModuleTransportError(
                "module_unreachable",
                "Module is unreachable",
                status_code=502,
            ) from None


class ModuleRegistry:
    def __init__(
        self,
        db_path: str,
        credential_dir: Path,
        *,
        busy_timeout_ms: int,
        client: ModuleHttpClient,
        plugin_lookup: Callable[[str], dict[str, Any] | None],
        audit: Callable[..., None],
        resident_integration_lookup: (
            Callable[[str], dict[str, Any] | None] | None
        ) = None,
        capability_base_url: str = "http://127.0.0.1:51111",
    ):
        self.db_path = db_path
        self.credential_dir = Path(credential_dir).resolve()
        self.busy_timeout_ms = busy_timeout_ms
        self.client = client
        self.plugin_lookup = plugin_lookup
        self.resident_integration_lookup = (
            resident_integration_lookup or (lambda _integration_id: None)
        )
        self.audit = audit
        try:
            self.capability_base_url = (
                ModuleAddressPolicy._normalize_origin(capability_base_url)
            )
        except (TypeError, ValueError):
            raise ValueError(
                "Capability callback base URL must be an HTTP(S) origin"
            ) from None
        self.credential_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.credential_dir, 0o700)

    def _connection(self, *, write: bool = False, immediate: bool = False):
        return database_connection(
            self.db_path,
            busy_timeout_ms=self.busy_timeout_ms,
            write=write,
            immediate=immediate,
        )

    @staticmethod
    def _manifest_from_row(row: Any) -> dict[str, Any]:
        return validate_manifest(json.loads(row["manifest_json"]))

    def _credential_path(self, registration_id: str) -> Path:
        try:
            parsed = uuid.UUID(registration_id)
        except ValueError:
            raise ModuleRegistryError(
                "module_not_found",
                "Module registration was not found",
                status_code=404,
            ) from None
        return self.credential_dir / f"{parsed}.token"

    def _write_credential(self, registration_id: str, token: str) -> None:
        path = self._credential_path(registration_id)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{registration_id}.",
            dir=self.credential_dir,
        )
        temporary_path = Path(temporary_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as credential_file:
                credential_file.write(token)
                credential_file.flush()
                os.fsync(credential_file.fileno())
            os.replace(temporary_path, path)
            os.chmod(path, 0o600)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    def _read_credential(self, row: Any) -> str:
        path = self._credential_path(row["id"])
        try:
            mode = path.stat().st_mode & 0o777
            if mode != 0o600:
                raise OSError("credential permissions")
            token = path.read_text(encoding="utf-8")
        except OSError:
            raise ModuleRegistryError(
                "module_credential_unavailable",
                "Module connection credential is unavailable",
                status_code=503,
            ) from None
        if not secrets.compare_digest(
            _token_digest(token),
            row["credential_digest"],
        ):
            raise ModuleRegistryError(
                "module_credential_invalid",
                "Module connection credential is invalid",
                status_code=503,
            )
        return token

    def _row(self, registration_id: str):
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM module_registrations WHERE id = ?",
                (registration_id,),
            ).fetchone()
        if row is None:
            raise ModuleRegistryError(
                "module_not_found",
                "Module registration was not found",
                status_code=404,
            )
        return row

    def _grants(self, registration_id: str) -> list[str]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT capability
                FROM module_capability_grants
                WHERE registration_id = ?
                ORDER BY capability
                """,
                (registration_id,),
            ).fetchall()
        return [row["capability"] for row in rows]

    def _mark_refresh_failure(
        self,
        registration_id: str,
        *,
        health_status: str,
        requires_review: bool,
    ) -> None:
        now = _utc_now()
        with self._connection(
            write=True,
            immediate=True,
        ) as connection:
            connection.execute(
                """
                UPDATE module_registrations
                SET health_status = ?, ready_status = 'unknown',
                    config_status = 'unknown',
                    lifecycle_state = CASE
                        WHEN ? THEN 'pending_review'
                        ELSE lifecycle_state
                    END,
                    reviewed_manifest_digest = CASE
                        WHEN ? THEN NULL
                        ELSE reviewed_manifest_digest
                    END,
                    updated_at = ?, last_checked_at = ?
                WHERE id = ?
                """,
                (
                    health_status,
                    int(requires_review),
                    int(requires_review),
                    now,
                    now,
                    registration_id,
                ),
            )
            if requires_review:
                connection.execute(
                    """
                    DELETE FROM module_capability_grants
                    WHERE registration_id = ?
                    """,
                    (registration_id,),
                )

    def _feature_status(
        self,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        integration = manifest["frontend_integration"]
        mode = integration["mode"]
        if mode == "plugin":
            installed = self.plugin_lookup(integration["id"])
            if installed is None:
                status = "plugin_missing"
                version = None
                enabled = False
            else:
                version = installed.get("version")
                enabled = bool(installed.get("enabled"))
                if not enabled:
                    status = "plugin_disabled"
                elif (
                    not isinstance(version, str)
                    or not integration_version_matches(
                        version,
                        integration["version_range"],
                    )
                ):
                    status = "plugin_incompatible"
                else:
                    status = "ready"
            trust = (
                installed.get("trust")
                if installed is not None
                else None
            )
        else:
            installed = self.resident_integration_lookup(integration["id"])
            enabled = installed is not None
            trust = {"kind": "server_source", "label": "Built into Server"}
            if installed is None:
                status = "resident_missing"
                version = None
            else:
                version = installed.get("version")
                actions = {
                    action["action_id"]: action
                    for action in manifest["actions"]
                }
                role_rank = {"member": 0, "admin": 1}
                required_actions_compatible = True
                for required in installed.get("required_actions", []):
                    action = actions.get(required["action_id"])
                    if (
                        action is None
                        or not integration_version_matches(
                            action["action_version"],
                            required["version_range"],
                        )
                        or role_rank[installed["minimum_role"]]
                        < role_rank[action["minimum_role"]]
                    ):
                        required_actions_compatible = False
                        break
                if (
                    installed.get("module_id") != manifest["module_id"]
                    or not isinstance(version, str)
                    or not integration_version_matches(
                        version,
                        integration["version_range"],
                    )
                    or not required_actions_compatible
                ):
                    status = "resident_incompatible"
                else:
                    status = "ready"
        return {
            "mode": mode,
            "id": integration["id"],
            "plugin_id": (
                integration["id"] if mode == "plugin" else None
            ),
            "required_version": integration["version_range"],
            "installed_version": version,
            "enabled": enabled,
            "status": status,
            "trust": trust,
        }

    def _update_feature_status(
        self,
        registration_id: str,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        feature = self._feature_status(manifest)
        now = _utc_now()
        with self._connection(write=True) as connection:
            connection.execute(
                """
                UPDATE module_feature_suites
                SET dependency_status = ?, checked_at = ?
                WHERE registration_id = ?
                """,
                (feature["status"], now, registration_id),
            )
        return feature

    def _serialize(self, row: Any, *, detail: bool = False) -> dict[str, Any]:
        manifest = self._manifest_from_row(row)
        feature = self._feature_status(manifest)
        reviewed = (
            row["reviewed_manifest_digest"] == row["manifest_digest"]
            and row["reviewed_permission_digest"] == row["permission_digest"]
        )
        ready = (
            reviewed
            and row["health_status"] == "healthy"
            and row["ready_status"] == "ready"
            and row["config_status"] == "configured"
            and feature["status"] == "ready"
        )
        capability_reviews = []
        for capability in manifest["requested_host_capabilities"]:
            risk = {
                "chat.read": "medium",
                "resource.read": "medium",
                "resource.stream": "medium",
                "model.invoke": "high",
            }.get(capability, "unrecognized")
            capability_reviews.append(
                {
                    "capability": capability,
                    "risk": risk,
                    "effective_in_t3": False,
                    "effective_for_tasks": capability
                    in {
                        "chat.read",
                        "resource.read",
                        "resource.stream",
                        "model.invoke",
                    },
                }
            )
        actions = [
            {
                **{
                    key: action[key]
                    for key in (
                        "action_id",
                        "action_version",
                        "minimum_role",
                        "supports_stream",
                        "supports_cancel",
                        "supports_approval",
                        "supports_artifacts",
                        "supports_chat_projection",
                    )
                },
                "supports_resources": action.get(
                    "supports_resources",
                    False,
                ),
            }
            for action in manifest["actions"]
        ]
        payload = {
            "id": row["id"],
            "module_id": row["module_id"],
            "name": row["module_name"],
            "description": row["module_description"],
            "module_version": row["module_version"],
            "protocol_version": row["protocol_version"],
            "manifest_digest": row["manifest_digest"],
            "lifecycle_state": row["lifecycle_state"],
            "health_status": row["health_status"],
            "ready_status": row["ready_status"],
            "config_status": row["config_status"],
            "reviewed": reviewed,
            "can_enable": ready,
            "enabled_once": bool(row["enabled_once"]),
            "requested_host_capabilities": manifest[
                "requested_host_capabilities"
            ],
            "capability_reviews": capability_reviews,
            "granted_host_capabilities": self._grants(row["id"]),
            "actions": actions,
            "frontend_integration": feature,
            "feature_suite": feature,
            "supports_data_purge": manifest["administration"][
                "supports_data_purge"
            ],
            "network": {
                "status": row["health_status"],
                "last_checked_at": row["last_checked_at"],
            },
            "data_retention": {
                "managed_by": "module",
                "supports_purge": manifest["administration"][
                    "supports_data_purge"
                ],
            },
            "recent_fault": self._recent_fault(row, feature),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_checked_at": row["last_checked_at"],
        }
        if detail:
            payload["manifest"] = manifest
        return payload

    @staticmethod
    def _recent_fault(
        row: Any,
        feature: dict[str, Any],
    ) -> dict[str, str] | None:
        if row["health_status"] != "healthy":
            return {
                "code": f"module_{row['health_status']}",
                "message": "The backend module is not healthy.",
            }
        if row["ready_status"] != "ready":
            return {
                "code": "module_not_ready",
                "message": "The backend module is not ready.",
            }
        if row["config_status"] != "configured":
            return {
                "code": "module_not_configured",
                "message": "The backend module configuration is incomplete.",
            }
        if feature["status"] != "ready":
            return {
                "code": feature["status"],
                "message": "The frontend integration requirement is incomplete.",
            }
        return None

    def feature_status(self, module_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM module_registrations WHERE module_id = ?",
                (module_id,),
            ).fetchone()
        if row is None:
            raise ModuleRegistryError(
                "module_not_found",
                "Module feature was not found",
                status_code=404,
            )
        summary = self._serialize(row)
        available = (
            summary["lifecycle_state"] == "enabled"
            and summary["can_enable"]
        )
        integration = summary["frontend_integration"]
        visible = available or summary["enabled_once"]
        if available:
            state = "available"
            reason = None
        elif visible:
            state = "unavailable"
            reason = summary["recent_fault"] or {
                "code": "feature_disabled",
                "message": "This feature is currently unavailable.",
            }
        else:
            state = "hidden"
            reason = None
        public_integration = {
            key: integration[key]
            for key in ("mode", "id", "required_version", "status")
        }
        return {
            "sdk_version": "1.2.0",
            "module_id": summary["module_id"],
            "name": summary["name"],
            "module_version": summary["module_version"],
            "protocol_version": summary["protocol_version"],
            "visible": visible,
            "available": available,
            "state": state,
            "reason": reason,
            "frontend_integration": public_integration,
            "companion_plugin": (
                {"status": integration["status"]}
                if integration["mode"] == "plugin"
                else None
            ),
            "actions": summary["actions"],
        }

    def list(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM module_registrations
                ORDER BY module_name COLLATE NOCASE, module_id
                """
            ).fetchall()
        return [self._serialize(row) for row in rows]

    def get(self, registration_id: str) -> dict[str, Any]:
        return self._serialize(self._row(registration_id), detail=True)

    def task_target(
        self,
        *,
        module_id: str | None = None,
        registration_id: str | None = None,
        require_enabled: bool = True,
    ) -> dict[str, Any]:
        if (module_id is None) == (registration_id is None):
            raise ValueError("exactly one module identity is required")
        with self._connection() as connection:
            if module_id is not None:
                row = connection.execute(
                    "SELECT * FROM module_registrations WHERE module_id = ?",
                    (module_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT * FROM module_registrations WHERE id = ?",
                    (registration_id,),
                ).fetchone()
        if row is None:
            raise ModuleRegistryError(
                "module_not_found",
                "Module registration was not found",
                status_code=404,
            )
        if require_enabled and row["lifecycle_state"] != "enabled":
            raise ModuleRegistryError(
                "module_not_enabled",
                "Module is not accepting new tasks",
                status_code=409,
            )
        if require_enabled and (
            row["health_status"] != "healthy"
            or row["ready_status"] != "ready"
            or row["config_status"] != "configured"
        ):
            raise ModuleRegistryError(
                "module_not_ready",
                "Module is not ready",
                status_code=409,
            )
        manifest = self._manifest_from_row(row)
        reviewed = (
            row["reviewed_manifest_digest"] == row["manifest_digest"]
            and row["reviewed_permission_digest"] == row["permission_digest"]
        )
        if require_enabled and not reviewed:
            raise ModuleRegistryError(
                "module_review_required",
                "Module requires administrator review",
                status_code=409,
            )
        feature = self._feature_status(manifest)
        if require_enabled and feature["status"] != "ready":
            raise ModuleRegistryError(
                feature["status"],
                "The frontend integration requirement is incomplete",
                status_code=409,
            )
        return {
            "registration_id": row["id"],
            "module_id": row["module_id"],
            "module_version": row["module_version"],
            "protocol_version": row["protocol_version"],
            "base_url": row["base_url"],
            "credential": self._read_credential(row),
            "config_revision": row["config_revision"],
            "manifest": manifest,
            "granted_capabilities": self._grants(row["id"]),
            "lifecycle_state": row["lifecycle_state"],
        }

    async def _revoke_unstored_credential(
        self,
        base_url: str,
        access_token: str,
    ) -> None:
        try:
            await self.client.request_json(
                base_url,
                DISCONNECT_PATH,
                method="POST",
                token=access_token,
                payload={"preserve_data": True},
            )
        except ModuleRegistryError:
            pass

    async def pair(
        self,
        *,
        base_url: str,
        pairing_code: str,
        actor_user_id: str,
    ) -> dict[str, Any]:
        if (
            not isinstance(pairing_code, str)
            or not 16 <= len(pairing_code) <= MAX_PAIR_CODE_LENGTH
        ):
            raise ModuleRegistryError(
                "invalid_pairing_code",
                "Pairing code is invalid",
                status_code=400,
            )
        normalized_url = self.client.address_policy.normalize(base_url)
        status, identity = await self.client.request_json(
            normalized_url,
            PAIR_PATH,
            method="POST",
            payload={
                "pairing_code": pairing_code,
                "host": {
                    "product": "ChatRaw Server",
                    "module_protocol": "1.0.0",
                    "capability_base_url": self.capability_base_url,
                },
            },
            max_bytes=MAX_PAIR_RESPONSE_BYTES,
        )
        if status != 200:
            raise ModuleRegistryError(
                "pairing_rejected",
                "Module rejected the pairing request",
                status_code=400 if status < 500 else 502,
            )
        if set(identity) != {"module_id", "instance_id", "access_token"}:
            raise ModuleRegistryError(
                "invalid_pairing_response",
                "Module pairing response is invalid",
                status_code=502,
            )
        module_id = identity.get("module_id")
        instance_id = identity.get("instance_id")
        access_token = identity.get("access_token")
        if (
            not isinstance(module_id, str)
            or not isinstance(instance_id, str)
            or not isinstance(access_token, str)
            or not 32 <= len(access_token) <= MAX_TOKEN_LENGTH
        ):
            raise ModuleRegistryError(
                "invalid_pairing_response",
                "Module pairing response is invalid",
                status_code=502,
            )

        try:
            with self._connection() as connection:
                existing = connection.execute(
                    "SELECT 1 FROM module_registrations WHERE module_id = ?",
                    (module_id,),
                ).fetchone()
            if existing:
                raise ModuleRegistryError(
                    "module_already_registered",
                    "Module is already registered",
                    status_code=409,
                )
            manifest_status, raw_manifest = (
                await self.client.request_json(
                    normalized_url,
                    MANIFEST_PATH,
                    token=access_token,
                    max_bytes=MAX_MANIFEST_BYTES,
                )
            )
            if manifest_status != 200:
                raise ModuleRegistryError(
                    "manifest_unavailable",
                    "Module manifest is unavailable",
                    status_code=502,
                )
            try:
                manifest = validate_manifest(raw_manifest)
            except ModuleProtocolError as error:
                raise ModuleRegistryError(
                    error.code,
                    error.public_message,
                    status_code=error.status_code,
                ) from error
            if manifest["module_id"] != module_id:
                raise ModuleRegistryError(
                    "module_identity_mismatch",
                    "Module identity does not match its manifest",
                    status_code=400,
                )
        except BaseException:
            await self._revoke_unstored_credential(
                normalized_url,
                access_token,
            )
            raise

        registration_id = str(uuid.uuid4())
        now = _utc_now()
        manifest_digest = digest_json(manifest)
        permissions = permission_digest(manifest)
        health_status = (
            "healthy"
            if protocol_is_compatible(manifest["protocol_version"])
            else "incompatible"
        )
        self._write_credential(registration_id, access_token)
        try:
            with self._connection(
                write=True,
                immediate=True,
            ) as connection:
                existing = connection.execute(
                    "SELECT 1 FROM module_registrations WHERE module_id = ?",
                    (module_id,),
                ).fetchone()
                if existing:
                    raise ModuleRegistryError(
                        "module_already_registered",
                        "Module is already registered",
                        status_code=409,
                    )
                connection.execute(
                    """
                    INSERT INTO module_registrations (
                        id, module_id, instance_id, base_url,
                        module_name, module_description,
                        module_version, protocol_version,
                        manifest_json, manifest_digest, permission_digest,
                        credential_digest, lifecycle_state, health_status,
                        ready_status, config_status, created_by_user_id,
                        created_at, updated_at, last_checked_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        'pending_review', ?, 'unknown', 'unknown', ?,
                        ?, ?, ?
                    )
                    """,
                    (
                        registration_id,
                        module_id,
                        instance_id,
                        normalized_url,
                        manifest["name"],
                        manifest["description"],
                        manifest["module_version"],
                        manifest["protocol_version"],
                        canonical_json(manifest),
                        manifest_digest,
                        permissions,
                        _token_digest(access_token),
                        health_status,
                        actor_user_id,
                        now,
                        now,
                        now,
                    ),
                )
                integration = manifest["frontend_integration"]
                connection.execute(
                    """
                    INSERT INTO module_feature_suites (
                        registration_id, integration_mode,
                        integration_id, integration_version_range,
                        dependency_status, checked_at
                    )
                    VALUES (?, ?, ?, ?, 'unknown', NULL)
                    """,
                    (
                        registration_id,
                        integration["mode"],
                        integration["id"],
                        integration["version_range"],
                    ),
                )
        except BaseException:
            self._credential_path(registration_id).unlink(missing_ok=True)
            await self._revoke_unstored_credential(
                normalized_url,
                access_token,
            )
            raise
        self._update_feature_status(registration_id, manifest)
        self.audit(
            actor_user_id,
            "module.pair",
            "module",
            module_id,
            "success",
            {
                "registration_id": registration_id,
                "health_status": health_status,
            },
        )
        return self.get(registration_id)

    async def refresh(
        self,
        registration_id: str,
        *,
        actor_user_id: str,
    ) -> dict[str, Any]:
        row = self._row(registration_id)
        token = self._read_credential(row)
        try:
            status, raw_manifest = await self.client.request_json(
                row["base_url"],
                MANIFEST_PATH,
                token=token,
                max_bytes=MAX_MANIFEST_BYTES,
            )
        except ModuleRegistryError:
            self._mark_refresh_failure(
                registration_id,
                health_status="unreachable",
                requires_review=False,
            )
            raise
        if status != 200:
            self._mark_refresh_failure(
                registration_id,
                health_status="unreachable",
                requires_review=False,
            )
            raise ModuleRegistryError(
                "manifest_unavailable",
                "Module manifest is unavailable",
                status_code=502,
            )
        try:
            manifest = validate_manifest(raw_manifest)
        except ModuleProtocolError as error:
            self._mark_refresh_failure(
                registration_id,
                health_status="incompatible",
                requires_review=True,
            )
            raise ModuleRegistryError(
                error.code,
                error.public_message,
                status_code=error.status_code,
            ) from error
        if manifest["module_id"] != row["module_id"]:
            self._mark_refresh_failure(
                registration_id,
                health_status="incompatible",
                requires_review=True,
            )
            raise ModuleRegistryError(
                "module_identity_mismatch",
                "Module identity changed",
                status_code=409,
            )
        new_manifest_digest = digest_json(manifest)
        new_permission_digest = permission_digest(manifest)
        compatible = protocol_is_compatible(manifest["protocol_version"])
        permissions_unchanged = (
            row["reviewed_permission_digest"] is not None
            and row["reviewed_permission_digest"] == new_permission_digest
        )
        lifecycle = row["lifecycle_state"]
        reviewed_manifest_digest = row["reviewed_manifest_digest"]
        reviewed_module_version = row["reviewed_module_version"]
        if not compatible:
            health = "incompatible"
            lifecycle = "pending_review"
            reviewed_manifest_digest = None
        elif permissions_unchanged and row["reviewed_manifest_digest"]:
            health = "healthy"
            reviewed_manifest_digest = new_manifest_digest
            reviewed_module_version = manifest["module_version"]
        else:
            health = "healthy"
            if new_manifest_digest != row["reviewed_manifest_digest"]:
                lifecycle = "pending_review"
                reviewed_manifest_digest = None

        now = _utc_now()
        integration = manifest["frontend_integration"]
        with self._connection(
            write=True,
            immediate=True,
        ) as connection:
            connection.execute(
                """
                UPDATE module_registrations
                SET module_name = ?, module_description = ?,
                    module_version = ?, protocol_version = ?,
                    manifest_json = ?, manifest_digest = ?,
                    permission_digest = ?, reviewed_manifest_digest = ?,
                    reviewed_module_version = ?, lifecycle_state = ?,
                    health_status = ?, ready_status = 'unknown',
                    config_status = 'unknown', updated_at = ?,
                    last_checked_at = ?
                WHERE id = ?
                """,
                (
                    manifest["name"],
                    manifest["description"],
                    manifest["module_version"],
                    manifest["protocol_version"],
                    canonical_json(manifest),
                    new_manifest_digest,
                    new_permission_digest,
                    reviewed_manifest_digest,
                    reviewed_module_version,
                    lifecycle,
                    health,
                    now,
                    now,
                    registration_id,
                ),
            )
            connection.execute(
                """
                UPDATE module_feature_suites
                SET integration_mode = ?,
                    integration_id = ?,
                    integration_version_range = ?,
                    dependency_status = 'unknown',
                    checked_at = NULL
                WHERE registration_id = ?
                """,
                (
                    integration["mode"],
                    integration["id"],
                    integration["version_range"],
                    registration_id,
                ),
            )
            if reviewed_manifest_digest is None:
                connection.execute(
                    """
                    DELETE FROM module_capability_grants
                    WHERE registration_id = ?
                    """,
                    (registration_id,),
                )
        self._update_feature_status(registration_id, manifest)
        self.audit(
            actor_user_id,
            "module.refresh",
            "module",
            row["module_id"],
            "success",
            {
                "registration_id": registration_id,
                "requires_review": reviewed_manifest_digest is None,
                "health_status": health,
            },
        )
        return await self.check(
            registration_id,
            actor_user_id=actor_user_id,
        )

    def approve(
        self,
        registration_id: str,
        *,
        manifest_digest: str,
        approved_capabilities: list[str],
        actor_user_id: str,
    ) -> dict[str, Any]:
        row = self._row(registration_id)
        manifest = self._manifest_from_row(row)
        requested = sorted(manifest["requested_host_capabilities"])
        if manifest_digest != row["manifest_digest"]:
            raise ModuleRegistryError(
                "manifest_changed",
                "Module manifest changed; review the latest version",
                status_code=409,
            )
        if not protocol_is_compatible(row["protocol_version"]):
            raise ModuleRegistryError(
                "module_incompatible",
                "Module protocol is incompatible",
                status_code=409,
            )
        if sorted(set(approved_capabilities)) != requested:
            raise ModuleRegistryError(
                "capability_approval_mismatch",
                "All requested capabilities must be reviewed explicitly",
                status_code=400,
            )
        now = _utc_now()
        with self._connection(
            write=True,
            immediate=True,
        ) as connection:
            connection.execute(
                """
                DELETE FROM module_capability_grants
                WHERE registration_id = ?
                """,
                (registration_id,),
            )
            connection.executemany(
                """
                INSERT INTO module_capability_grants (
                    registration_id, capability,
                    granted_by_user_id, created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        registration_id,
                        capability,
                        actor_user_id,
                        now,
                    )
                    for capability in requested
                ],
            )
            connection.execute(
                """
                UPDATE module_registrations
                SET reviewed_manifest_digest = ?,
                    reviewed_permission_digest = ?,
                    reviewed_module_version = ?,
                    reviewed_by_user_id = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    row["manifest_digest"],
                    row["permission_digest"],
                    row["module_version"],
                    actor_user_id,
                    now,
                    registration_id,
                ),
            )
        self.audit(
            actor_user_id,
            "module.approve",
            "module",
            row["module_id"],
            "success",
            {
                "registration_id": registration_id,
                "capabilities": requested,
            },
        )
        return self.get(registration_id)

    @staticmethod
    def _validate_health_response(
        payload: dict[str, Any],
    ) -> None:
        if payload != {"status": "healthy"}:
            raise ModuleRegistryError(
                "invalid_health_response",
                "Module health response is invalid",
                status_code=502,
            )

    @staticmethod
    def _validate_ready_response(
        payload: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        if set(payload) != {"ready", "reasons"}:
            raise ModuleRegistryError(
                "invalid_ready_response",
                "Module readiness response is invalid",
                status_code=502,
            )
        ready = payload["ready"]
        reasons = payload["reasons"]
        if (
            not isinstance(ready, bool)
            or not isinstance(reasons, list)
            or len(reasons) > 32
            or not all(
                isinstance(reason, str)
                and 1 <= len(reason) <= 128
                and reason.replace("_", "").replace("-", "").isalnum()
                for reason in reasons
            )
        ):
            raise ModuleRegistryError(
                "invalid_ready_response",
                "Module readiness response is invalid",
                status_code=502,
            )
        return ready, reasons

    async def check(
        self,
        registration_id: str,
        *,
        actor_user_id: str,
    ) -> dict[str, Any]:
        row = self._row(registration_id)
        manifest = self._manifest_from_row(row)
        if not protocol_is_compatible(row["protocol_version"]):
            with self._connection(write=True) as connection:
                connection.execute(
                    """
                    UPDATE module_registrations
                    SET health_status = 'incompatible',
                        ready_status = 'unknown',
                        updated_at = ?, last_checked_at = ?
                    WHERE id = ?
                    """,
                    (_utc_now(), _utc_now(), registration_id),
                )
            return self.get(registration_id)
        token = self._read_credential(row)
        try:
            health_status, health = await self.client.request_json(
                row["base_url"],
                HEALTH_PATH,
                token=token,
            )
            if health_status != 200:
                raise ModuleRegistryError(
                    "module_unhealthy",
                    "Module health check failed",
                    status_code=502,
                )
            self._validate_health_response(health)
            ready_status_code, ready_payload = (
                await self.client.request_json(
                    row["base_url"],
                    READY_PATH,
                    token=token,
                )
            )
            if ready_status_code != 200:
                raise ModuleRegistryError(
                    "module_not_ready",
                    "Module readiness check failed",
                    status_code=502,
                )
            ready, _reasons = self._validate_ready_response(ready_payload)
            config_status_code, config_payload = (
                await self.client.request_json(
                    row["base_url"],
                    CONFIG_PATH,
                    token=token,
                    max_bytes=MAX_CONFIG_BYTES,
                )
            )
            if config_status_code != 200:
                raise ModuleRegistryError(
                    "module_config_unavailable",
                    "Module configuration is unavailable",
                    status_code=502,
                )
            config = validate_config_view(
                manifest["config_schema"],
                config_payload,
            )
        except (ModuleRegistryError, ModuleProtocolError) as error:
            error_code = getattr(
                error,
                "code",
                "module_check_failed",
            )
            health_status = (
                "incompatible"
                if isinstance(error, ModuleProtocolError)
                or error_code
                in {
                    "invalid_health_response",
                    "invalid_ready_response",
                    "invalid_config_response",
                }
                else "unreachable"
            )
            now = _utc_now()
            with self._connection(write=True) as connection:
                connection.execute(
                    """
                    UPDATE module_registrations
                    SET health_status = ?,
                        ready_status = 'unknown',
                        config_status = 'unknown',
                        updated_at = ?, last_checked_at = ?
                    WHERE id = ?
                    """,
                    (
                        health_status,
                        now,
                        now,
                        registration_id,
                    ),
                )
            self.audit(
                actor_user_id,
                "module.check",
                "module",
                row["module_id"],
                "failure",
                {
                    "registration_id": registration_id,
                    "error_code": error_code,
                },
            )
            return self.get(registration_id)

        now = _utc_now()
        with self._connection(write=True) as connection:
            connection.execute(
                """
                UPDATE module_registrations
                SET health_status = 'healthy',
                    ready_status = ?,
                    config_status = ?,
                    config_revision = ?,
                    updated_at = ?, last_checked_at = ?
                WHERE id = ?
                """,
                (
                    "ready" if ready else "not_ready",
                    "configured" if config["configured"] else "missing",
                    config["revision"],
                    now,
                    now,
                    registration_id,
                ),
            )
        self._update_feature_status(registration_id, manifest)
        self.audit(
            actor_user_id,
            "module.check",
            "module",
            row["module_id"],
            "success",
            {
                "registration_id": registration_id,
                "ready": ready,
                "configured": config["configured"],
            },
        )
        return self.get(registration_id)

    async def get_config(
        self,
        registration_id: str,
    ) -> dict[str, Any]:
        row = self._row(registration_id)
        token = self._read_credential(row)
        status, raw_config = await self.client.request_json(
            row["base_url"],
            CONFIG_PATH,
            token=token,
            max_bytes=MAX_CONFIG_BYTES,
        )
        if status != 200:
            raise ModuleRegistryError(
                "module_config_unavailable",
                "Module configuration is unavailable",
                status_code=502,
            )
        manifest = self._manifest_from_row(row)
        try:
            config = validate_config_view(
                manifest["config_schema"],
                raw_config,
            )
        except ModuleProtocolError as error:
            raise ModuleRegistryError(
                error.code,
                error.public_message,
                status_code=502,
            ) from error
        with self._connection(write=True) as connection:
            connection.execute(
                """
                UPDATE module_registrations
                SET config_status = ?, config_revision = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    "configured" if config["configured"] else "missing",
                    config["revision"],
                    _utc_now(),
                    registration_id,
                ),
            )
        return {
            "schema": manifest["config_schema"],
            "revision": config["revision"],
            "values": config["values"],
            "secret_configured": config["secret_configured"],
            "configured": config["configured"],
            "missing_required": config["missing_required"],
        }

    async def update_config(
        self,
        registration_id: str,
        payload: Any,
        *,
        actor_user_id: str,
    ) -> dict[str, Any]:
        row = self._row(registration_id)
        manifest = self._manifest_from_row(row)
        try:
            update = validate_config_update(
                manifest["config_schema"],
                payload,
            )
        except ModuleProtocolError as error:
            raise ModuleRegistryError(
                error.code,
                error.public_message,
                status_code=error.status_code,
            ) from error
        token = self._read_credential(row)
        status, raw_config = await self.client.request_json(
            row["base_url"],
            CONFIG_PATH,
            method="PUT",
            token=token,
            payload=update,
            max_bytes=MAX_CONFIG_BYTES,
        )
        if status == 409:
            raise ModuleRegistryError(
                "config_revision_conflict",
                "Module configuration changed; reload before saving",
                status_code=409,
            )
        if status != 200:
            raise ModuleRegistryError(
                "module_config_update_failed",
                "Module configuration update failed",
                status_code=502,
            )
        try:
            config = validate_config_view(
                manifest["config_schema"],
                raw_config,
            )
        except ModuleProtocolError as error:
            raise ModuleRegistryError(
                error.code,
                error.public_message,
                status_code=502,
            ) from error
        now = _utc_now()
        with self._connection(write=True) as connection:
            connection.execute(
                """
                UPDATE module_registrations
                SET config_status = ?, config_revision = ?,
                    ready_status = 'unknown', updated_at = ?
                WHERE id = ?
                """,
                (
                    "configured" if config["configured"] else "missing",
                    config["revision"],
                    now,
                    registration_id,
                ),
            )
        self.audit(
            actor_user_id,
            "module.config.update",
            "module",
            row["module_id"],
            "success",
            {
                "registration_id": registration_id,
                "secret_actions": {
                    name: action["action"]
                    for name, action in update["secrets"].items()
                },
            },
        )
        result = {
            "schema": manifest["config_schema"],
            "revision": config["revision"],
            "values": config["values"],
            "secret_configured": config["secret_configured"],
            "configured": config["configured"],
            "missing_required": config["missing_required"],
        }
        try:
            await self.check(
                registration_id,
                actor_user_id=actor_user_id,
            )
        except ModuleRegistryError:
            # The remote configuration was already committed. A concurrent
            # disconnect or other lifecycle change must not turn that success
            # into a misleading configuration-save failure.
            pass
        return result

    def _set_lifecycle(
        self,
        registration_id: str,
        *,
        expected: set[str],
        target: str,
        actor_user_id: str,
    ) -> dict[str, Any]:
        row = self._row(registration_id)
        if row["lifecycle_state"] not in expected:
            raise ModuleRegistryError(
                "invalid_module_transition",
                "Module lifecycle transition is not allowed",
                status_code=409,
            )
        if target == "enabled":
            summary = self._serialize(row)
            if not summary["can_enable"]:
                raise ModuleRegistryError(
                    "module_not_enableable",
                    "Module requirements are not ready",
                    status_code=409,
                )
        now = _utc_now()
        with self._connection(
            write=True,
            immediate=True,
        ) as connection:
            current = connection.execute(
                """
                SELECT lifecycle_state
                FROM module_registrations
                WHERE id = ?
                """,
                (registration_id,),
            ).fetchone()
            if current is None or current["lifecycle_state"] not in expected:
                raise ModuleRegistryError(
                    "invalid_module_transition",
                    "Module lifecycle changed; reload before retrying",
                    status_code=409,
                )
            connection.execute(
                """
                UPDATE module_registrations
                SET lifecycle_state = ?, updated_at = ?,
                    enabled_once = CASE
                        WHEN ? = 'enabled' THEN 1
                        ELSE enabled_once
                    END
                WHERE id = ?
                """,
                (target, now, target, registration_id),
            )
        self.audit(
            actor_user_id,
            f"module.{target}",
            "module",
            row["module_id"],
            "success",
            {"registration_id": registration_id},
        )
        return self.get(registration_id)

    async def enable(
        self,
        registration_id: str,
        *,
        actor_user_id: str,
    ) -> dict[str, Any]:
        await self.refresh(
            registration_id,
            actor_user_id=actor_user_id,
        )
        await self.check(
            registration_id,
            actor_user_id=actor_user_id,
        )
        return self._set_lifecycle(
            registration_id,
            expected={"pending_review", "disabled"},
            target="enabled",
            actor_user_id=actor_user_id,
        )

    def drain(
        self,
        registration_id: str,
        *,
        actor_user_id: str,
    ) -> dict[str, Any]:
        return self._set_lifecycle(
            registration_id,
            expected={"enabled"},
            target="draining",
            actor_user_id=actor_user_id,
        )

    def disable(
        self,
        registration_id: str,
        *,
        actor_user_id: str,
    ) -> dict[str, Any]:
        return self._set_lifecycle(
            registration_id,
            expected={"enabled", "draining"},
            target="disabled",
            actor_user_id=actor_user_id,
        )

    async def disconnect(
        self,
        registration_id: str,
        *,
        confirmation: str,
        actor_user_id: str,
    ) -> dict[str, Any]:
        row = self._row(registration_id)
        if confirmation != row["module_id"]:
            raise ModuleRegistryError(
                "disconnect_confirmation_required",
                "Type the module ID to confirm disconnect",
                status_code=400,
            )
        remote_notified = False
        try:
            token = self._read_credential(row)
            status, _response = await self.client.request_json(
                row["base_url"],
                DISCONNECT_PATH,
                method="POST",
                token=token,
                payload={"preserve_data": True},
            )
            remote_notified = status in {200, 204}
        except ModuleRegistryError:
            pass
        with self._connection(
            write=True,
            immediate=True,
        ) as connection:
            connection.execute(
                "DELETE FROM module_registrations WHERE id = ?",
                (registration_id,),
            )
        self._credential_path(registration_id).unlink(missing_ok=True)
        self.audit(
            actor_user_id,
            "module.disconnect",
            "module",
            row["module_id"],
            "success",
            {
                "registration_id": registration_id,
                "module_data_preserved": True,
                "remote_notified": remote_notified,
            },
        )
        return {
            "success": True,
            "module_data_preserved": True,
            "remote_notified": remote_notified,
        }

    async def purge_data(
        self,
        registration_id: str,
        *,
        confirmation: str,
        actor_user_id: str,
    ) -> dict[str, Any]:
        row = self._row(registration_id)
        manifest = self._manifest_from_row(row)
        if not manifest["administration"]["supports_data_purge"]:
            raise ModuleRegistryError(
                "module_purge_unsupported",
                "Module does not support data purge",
                status_code=409,
            )
        if confirmation != f"PURGE {row['module_id']}":
            raise ModuleRegistryError(
                "purge_confirmation_required",
                "Independent purge confirmation is required",
                status_code=400,
            )
        token = self._read_credential(row)
        status, response = await self.client.request_json(
            row["base_url"],
            PURGE_PATH,
            method="POST",
            token=token,
            payload={"confirmation": confirmation},
        )
        if status != 200 or response != {"purged": True}:
            raise ModuleRegistryError(
                "module_purge_failed",
                "Module data purge failed",
                status_code=502,
            )
        now = _utc_now()
        with self._connection(write=True) as connection:
            connection.execute(
                """
                UPDATE module_registrations
                SET lifecycle_state = 'disabled',
                    ready_status = 'not_ready',
                    config_status = 'missing',
                    config_revision = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (now, registration_id),
            )
        self.audit(
            actor_user_id,
            "module.data.purge",
            "module",
            row["module_id"],
            "success",
            {"registration_id": registration_id},
        )
        return {"purged": True}
