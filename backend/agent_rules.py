"""Versioned user rule documents and deterministic compiled-rule validation."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


TARGET_MODULE_ID = "chatraw.agent"
SPECIFICATION_VERSION = "chatraw-agent-rule-1.0"
MAX_SOURCE_DOCUMENT_BYTES = 128 * 1024
MAX_COMPILED_RULE_BYTES = 64 * 1024
MAX_ACTIVE_RULES_PER_TASK = 10
_RULE_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class AgentRuleError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class RuleTrigger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    all: list[str] = Field(default_factory=list, max_length=20)
    any: list[str] = Field(default_factory=list, max_length=20)
    none: list[str] = Field(default_factory=list, max_length=20)


class RuleIteration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cursor_argument: str = Field(min_length=1, max_length=128)
    start: int
    step: int = Field(ge=1, le=1000000)
    page_size_argument: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
    )
    page_size: int | None = Field(default=None, ge=1, le=1000000)
    stop_when: Literal["empty_result", "short_page", "described_condition"]
    stop_description: str = Field(default="", max_length=1000)
    max_calls: int = Field(default=100, ge=1, le=256)

    @model_validator(mode="after")
    def validate_pairing(self):
        if (self.page_size_argument is None) != (self.page_size is None):
            raise ValueError(
                "page_size_argument and page_size must appear together"
            )
        if (
            self.stop_when == "described_condition"
            and not self.stop_description.strip()
        ):
            raise ValueError(
                "described_condition requires stop_description"
            )
        return self


class RuleToolPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selector: str = Field(min_length=1, max_length=1000)
    names: list[str] = Field(default_factory=list, max_length=20)
    argument_defaults: dict[str, Any] = Field(default_factory=dict)
    argument_constants: dict[str, Any] = Field(default_factory=dict)
    iteration: RuleIteration | None = None

    @model_validator(mode="after")
    def validate_arguments(self):
        overlap = set(self.argument_defaults) & set(
            self.argument_constants
        )
        if overlap:
            raise ValueError(
                "arguments cannot be both defaults and constants"
            )
        return self


class ExecutionRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    priority: int = Field(default=50, ge=1, le=100)
    when: RuleTrigger = Field(default_factory=RuleTrigger)
    instructions: list[str] = Field(min_length=1, max_length=20)
    tools: list[RuleToolPolicy] = Field(default_factory=list, max_length=20)
    response_requirements: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_id(self):
        if not _RULE_ID.fullmatch(self.id):
            raise ValueError("rule id format is invalid")
        return self


class CompiledRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=2000)
    execution_rules: list[ExecutionRule] = Field(
        min_length=1,
        max_length=50,
    )
    clarification_rules: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_unique_ids(self):
        identifiers = [rule.id for rule in self.execution_rules]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("execution rule ids must be unique")
        return self


COMPILED_RULE_JSON_SCHEMA = CompiledRule.model_json_schema()

COMPILER_SPECIFICATION = f"""
You compile a user's Source Document into a ChatRaw Compiled Rule.

Return exactly one JSON object. Do not return Markdown or commentary.
The JSON must conform exactly to this schema:
{json.dumps(COMPILED_RULE_JSON_SCHEMA, ensure_ascii=False, separators=(",", ":"))}

Compilation rules:
1. Preserve only requirements stated by the Source Document. Do not invent
   business facts, tool names, field names, dates, permissions, or defaults.
2. Convert operational instructions into ordered execution_rules. A rule's
   when fields describe when it applies; instructions describe required work.
3. Use tools[].selector for a semantic tool description. Add tools[].names
   only when the Source Document states exact tool names.
4. Put fixed arguments in argument_constants and fallback values in
   argument_defaults.
5. Represent pagination or repeated calls with iteration. For page=1,
   size=20, incrementing page until an empty result, use cursor_argument
   "page", start 1, step 1, page_size_argument "size", page_size 20,
   stop_when "empty_result".
6. If the Source Document is ambiguous or missing required runtime input,
   preserve that uncertainty in clarification_rules. Never guess.
7. Never create rules that grant tool permissions, bypass confirmations,
   change security policy, expose secrets, or override execution budgets.
8. The compiled rule is guidance for a general Agent. It must not contain
   executable code, shell commands, templates, or model-control instructions.
""".strip()


class AgentRuleService:
    def __init__(
        self,
        connection: Callable[..., Any],
        *,
        compile_model: Callable[
            [dict[str, Any]], Awaitable[dict[str, Any]]
        ],
        audit: Callable[..., None],
    ):
        self.connection = connection
        self.compile_model = compile_model
        self.audit = audit

    @staticmethod
    def _validate_source(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise AgentRuleError(
                "invalid_source_document",
                "Source Document is required",
            )
        if len(value.encode("utf-8")) > MAX_SOURCE_DOCUMENT_BYTES:
            raise AgentRuleError(
                "source_document_too_large",
                "Source Document is too large",
                413,
            )
        return value

    @staticmethod
    def _document_summary(row: Any) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "target_module_id": row["target_module_id"],
            "current_source_version_id": row[
                "current_source_version_id"
            ],
            "active_compiled_version_id": row[
                "active_compiled_version_id"
            ],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _owned_document(self, owner_user_id: str, document_id: str):
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM agent_rule_documents
                WHERE id = ? AND owner_user_id = ?
                  AND target_module_id = ?
                """,
                (document_id, owner_user_id, TARGET_MODULE_ID),
            ).fetchone()
        if row is None:
            raise AgentRuleError(
                "rule_document_not_found",
                "Rule document was not found",
                404,
            )
        return row

    def list_documents(self, owner_user_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM agent_rule_documents
                WHERE owner_user_id = ? AND target_module_id = ?
                ORDER BY updated_at DESC, name
                """,
                (owner_user_id, TARGET_MODULE_ID),
            ).fetchall()
        return [self._document_summary(row) for row in rows]

    def get_document(
        self,
        owner_user_id: str,
        document_id: str,
    ) -> dict[str, Any]:
        document = self._owned_document(owner_user_id, document_id)
        with self.connection() as connection:
            sources = connection.execute(
                """
                SELECT id, version_number, source_document,
                       content_sha256, created_at
                FROM agent_rule_source_versions
                WHERE document_id = ?
                ORDER BY version_number DESC
                """,
                (document_id,),
            ).fetchall()
            candidates = connection.execute(
                """
                SELECT id, source_version_id, specification_version,
                       status, content_sha256, compiled_json,
                       model_output, validation_errors_json, created_at
                FROM agent_compiled_rule_versions
                WHERE document_id = ?
                ORDER BY created_at DESC
                """,
                (document_id,),
            ).fetchall()
        result = self._document_summary(document)
        result["source_versions"] = [dict(row) for row in sources]
        result["compiled_candidates"] = [
            {
                **dict(row),
                "compiled_rule": (
                    json.loads(row["compiled_json"])
                    if row["compiled_json"]
                    else None
                ),
                "validation_errors": json.loads(
                    row["validation_errors_json"]
                ),
            }
            for row in candidates
        ]
        for candidate in result["compiled_candidates"]:
            candidate.pop("compiled_json")
            candidate.pop("validation_errors_json")
        return result

    def create_document(
        self,
        owner_user_id: str,
        *,
        name: str,
        source_document: str,
    ) -> dict[str, Any]:
        name = name.strip() if isinstance(name, str) else ""
        if not name or len(name) > 200:
            raise AgentRuleError(
                "invalid_rule_name",
                "Rule document name is invalid",
            )
        source_document = self._validate_source(source_document)
        document_id = str(uuid.uuid4())
        source_version_id = str(uuid.uuid4())
        now = _utc_now()
        try:
            with self.connection(write=True, immediate=True) as connection:
                connection.execute(
                    """
                    INSERT INTO agent_rule_documents (
                        id, owner_user_id, target_module_id, name,
                        current_source_version_id,
                        active_compiled_version_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?)
                    """,
                    (
                        document_id,
                        owner_user_id,
                        TARGET_MODULE_ID,
                        name,
                        source_version_id,
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO agent_rule_source_versions (
                        id, document_id, version_number, source_document,
                        content_sha256, created_at
                    ) VALUES (?, ?, 1, ?, ?, ?)
                    """,
                    (
                        source_version_id,
                        document_id,
                        source_document,
                        _sha256(source_document),
                        now,
                    ),
                )
        except Exception as error:
            if "UNIQUE constraint failed" in str(error):
                raise AgentRuleError(
                    "rule_name_conflict",
                    "A rule document with this name already exists",
                    409,
                ) from None
            raise
        self.audit(
            owner_user_id,
            "agent_rule.create",
            "agent_rule_document",
            document_id,
            "success",
            {"source_version_id": source_version_id},
        )
        return self.get_document(owner_user_id, document_id)

    def update_source(
        self,
        owner_user_id: str,
        document_id: str,
        *,
        expected_source_version_id: str,
        source_document: str,
    ) -> dict[str, Any]:
        source_document = self._validate_source(source_document)
        source_version_id = str(uuid.uuid4())
        now = _utc_now()
        with self.connection(write=True, immediate=True) as connection:
            document = connection.execute(
                """
                SELECT * FROM agent_rule_documents
                WHERE id = ? AND owner_user_id = ?
                  AND target_module_id = ?
                """,
                (document_id, owner_user_id, TARGET_MODULE_ID),
            ).fetchone()
            if document is None:
                raise AgentRuleError(
                    "rule_document_not_found",
                    "Rule document was not found",
                    404,
                )
            if (
                document["current_source_version_id"]
                != expected_source_version_id
            ):
                raise AgentRuleError(
                    "source_version_conflict",
                    "Source Document has changed; reload before saving",
                    409,
                )
            next_version = connection.execute(
                """
                SELECT COALESCE(MAX(version_number), 0) + 1
                FROM agent_rule_source_versions
                WHERE document_id = ?
                """,
                (document_id,),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO agent_rule_source_versions (
                    id, document_id, version_number, source_document,
                    content_sha256, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    source_version_id,
                    document_id,
                    next_version,
                    source_document,
                    _sha256(source_document),
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE agent_rule_documents
                SET current_source_version_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (source_version_id, now, document_id),
            )
        self.audit(
            owner_user_id,
            "agent_rule.source.update",
            "agent_rule_document",
            document_id,
            "success",
            {"source_version_id": source_version_id},
        )
        return self.get_document(owner_user_id, document_id)

    @staticmethod
    def _validated_candidate(
        model_output: str,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        try:
            raw = json.loads(model_output)
        except json.JSONDecodeError as error:
            return None, [
                {
                    "type": "invalid_json",
                    "message": str(error),
                }
            ]
        try:
            compiled = CompiledRule.model_validate(raw)
        except Exception as error:
            details = (
                error.errors(include_context=False)
                if hasattr(error, "errors")
                else [{"type": "validation_error", "message": str(error)}]
            )
            return None, details
        normalized = compiled.model_dump(mode="json")
        encoded = json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if len(encoded.encode("utf-8")) > MAX_COMPILED_RULE_BYTES:
            return None, [
                {
                    "type": "compiled_rule_too_large",
                    "message": "Compiled Rule is too large",
                }
            ]
        return normalized, []

    async def compile_document(
        self,
        owner_user_id: str,
        document_id: str,
        *,
        source_version_id: str,
    ) -> dict[str, Any]:
        document = self._owned_document(owner_user_id, document_id)
        with self.connection() as connection:
            source = connection.execute(
                """
                SELECT * FROM agent_rule_source_versions
                WHERE id = ? AND document_id = ?
                """,
                (source_version_id, document_id),
            ).fetchone()
        if source is None:
            raise AgentRuleError(
                "source_version_not_found",
                "Source Document version was not found",
                404,
            )
        request = {
            "profile": "agent-compiler",
            "messages": [
                {"role": "system", "content": COMPILER_SPECIFICATION},
                {
                    "role": "user",
                    "content": (
                        "Source Document:\n"
                        f"{source['source_document']}"
                    ),
                },
            ],
            "temperature": 0,
            "max_tokens": 8192,
            "timeout_seconds": 600,
        }
        completion = await self.compile_model(request)
        model_output = completion.get("content")
        if not isinstance(model_output, str):
            raise AgentRuleError(
                "invalid_compiler_response",
                "Compiler model returned invalid content",
                502,
            )
        if len(model_output.encode("utf-8")) > MAX_COMPILED_RULE_BYTES:
            compiled = None
            validation_errors = [
                {
                    "type": "compiler_output_too_large",
                    "message": "Compiler model output is too large",
                }
            ]
            model_output = model_output.encode("utf-8")[
                :MAX_COMPILED_RULE_BYTES
            ].decode("utf-8", errors="ignore")
        else:
            compiled, validation_errors = self._validated_candidate(
                model_output
            )
        candidate_id = str(uuid.uuid4())
        now = _utc_now()
        normalized_json = (
            json.dumps(
                compiled,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            if compiled is not None
            else None
        )
        content_digest = _sha256(normalized_json or model_output)
        with self.connection(write=True) as connection:
            connection.execute(
                """
                INSERT INTO agent_compiled_rule_versions (
                    id, document_id, source_version_id,
                    specification_version, status, content_sha256,
                    compiled_json, model_output, validation_errors_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    document_id,
                    source_version_id,
                    SPECIFICATION_VERSION,
                    "valid" if compiled is not None else "invalid",
                    content_digest,
                    normalized_json,
                    model_output,
                    json.dumps(
                        validation_errors,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    now,
                ),
            )
        self.audit(
            owner_user_id,
            "agent_rule.compile",
            "agent_rule_document",
            document_id,
            "success" if compiled is not None else "invalid",
            {
                "source_version_id": source_version_id,
                "candidate_id": candidate_id,
                "specification_version": SPECIFICATION_VERSION,
            },
        )
        return self.get_document(owner_user_id, document["id"])

    def activate(
        self,
        owner_user_id: str,
        document_id: str,
        *,
        compiled_version_id: str | None,
    ) -> dict[str, Any]:
        with self.connection(write=True, immediate=True) as connection:
            document = connection.execute(
                """
                SELECT * FROM agent_rule_documents
                WHERE id = ? AND owner_user_id = ?
                  AND target_module_id = ?
                """,
                (document_id, owner_user_id, TARGET_MODULE_ID),
            ).fetchone()
            if document is None:
                raise AgentRuleError(
                    "rule_document_not_found",
                    "Rule document was not found",
                    404,
                )
            if compiled_version_id is not None:
                candidate = connection.execute(
                    """
                    SELECT * FROM agent_compiled_rule_versions
                    WHERE id = ? AND document_id = ?
                    """,
                    (compiled_version_id, document_id),
                ).fetchone()
                if candidate is None:
                    raise AgentRuleError(
                        "compiled_rule_not_found",
                        "Compiled Rule candidate was not found",
                        404,
                    )
                if (
                    candidate["status"] != "valid"
                    or not candidate["compiled_json"]
                ):
                    raise AgentRuleError(
                        "compiled_rule_invalid",
                        "Only a valid Compiled Rule can be activated",
                        409,
                    )
            connection.execute(
                """
                UPDATE agent_rule_documents
                SET active_compiled_version_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (compiled_version_id, _utc_now(), document_id),
            )
        self.audit(
            owner_user_id,
            (
                "agent_rule.activate"
                if compiled_version_id is not None
                else "agent_rule.deactivate"
            ),
            "agent_rule_document",
            document_id,
            "success",
            {"compiled_version_id": compiled_version_id},
        )
        return self.get_document(owner_user_id, document_id)

    def active_snapshots(
        self,
        owner_user_id: str,
    ) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT documents.id AS document_id,
                       documents.name,
                       versions.id AS compiled_version_id,
                       versions.source_version_id,
                       versions.specification_version,
                       versions.content_sha256
                FROM agent_rule_documents AS documents
                JOIN agent_compiled_rule_versions AS versions
                  ON versions.id =
                     documents.active_compiled_version_id
                WHERE documents.owner_user_id = ?
                  AND documents.target_module_id = ?
                  AND versions.status = 'valid'
                ORDER BY documents.updated_at, documents.id
                LIMIT ?
                """,
                (
                    owner_user_id,
                    TARGET_MODULE_ID,
                    MAX_ACTIVE_RULES_PER_TASK + 1,
                ),
            ).fetchall()
        if len(rows) > MAX_ACTIVE_RULES_PER_TASK:
            raise AgentRuleError(
                "too_many_active_rules",
                "Too many active Agent rules",
                409,
            )
        return [dict(row) for row in rows]
