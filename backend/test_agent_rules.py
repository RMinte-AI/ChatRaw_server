import json
import os
import shutil
import tempfile
import unittest
import uuid


TEST_DATA_DIR = tempfile.mkdtemp(prefix="chatraw-agent-rules-test-")
os.environ.setdefault("DATA_DIR", TEST_DATA_DIR)

from backend import main  # noqa: E402
from backend.agent_rules import (  # noqa: E402
    AgentRuleError,
    AgentRuleService,
    SPECIFICATION_VERSION,
)


def tearDownModule():
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


def compiled_rule():
    return {
        "schema_version": "1.0",
        "title": "收费站分页规则",
        "summary": "逐页获取收费站流水，直到返回空数据。",
        "execution_rules": [
            {
                "id": "station_pagination",
                "priority": 80,
                "when": {
                    "all": ["用户请求收费站流水"],
                    "any": [],
                    "none": [],
                },
                "instructions": ["按页调用查询工具并汇总结果。"],
                "tools": [
                    {
                        "selector": "收费站流水分页查询工具",
                        "names": [],
                        "argument_defaults": {},
                        "argument_constants": {},
                        "iteration": {
                            "cursor_argument": "page",
                            "start": 1,
                            "step": 1,
                            "page_size_argument": "size",
                            "page_size": 20,
                            "stop_when": "empty_result",
                            "stop_description": "",
                            "max_calls": 100,
                        },
                    }
                ],
                "response_requirements": ["汇总全部页面的数据。"],
            }
        ],
        "clarification_rules": [],
    }


class AgentRuleServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.user_id = str(uuid.uuid4())
        now = "2026-07-26T00:00:00Z"
        with main.db.connection(write=True) as connection:
            connection.execute(
                """
                INSERT INTO users (
                    id, username, password_hash, role, enabled,
                    created_at, updated_at, password_changed_at
                ) VALUES (?, ?, 'hash', 'member', 1, ?, ?, ?)
                """,
                (
                    self.user_id,
                    f"agent-rule-{self.user_id}",
                    now,
                    now,
                    now,
                ),
            )
        self.model_outputs = []
        self.audits = []

        async def compile_model(request):
            self.model_outputs.append(request)
            return {"content": json.dumps(compiled_rule())}

        self.service = AgentRuleService(
            main.db.connection,
            compile_model=compile_model,
            audit=lambda *args: self.audits.append(args),
        )

    async def asyncTearDown(self):
        with main.db.connection(write=True) as connection:
            document_ids = [
                row["id"]
                for row in connection.execute(
                    """
                    SELECT id FROM agent_rule_documents
                    WHERE owner_user_id = ?
                    """,
                    (self.user_id,),
                ).fetchall()
            ]
            for document_id in document_ids:
                connection.execute(
                    """
                    DELETE FROM module_task_rule_activations
                    WHERE document_id = ?
                    """,
                    (document_id,),
                )
                connection.execute(
                    """
                    DELETE FROM agent_compiled_rule_versions
                    WHERE document_id = ?
                    """,
                    (document_id,),
                )
                connection.execute(
                    """
                    DELETE FROM agent_rule_source_versions
                    WHERE document_id = ?
                    """,
                    (document_id,),
                )
            connection.execute(
                "DELETE FROM agent_rule_documents WHERE owner_user_id = ?",
                (self.user_id,),
            )
            connection.execute(
                "DELETE FROM users WHERE id = ?",
                (self.user_id,),
            )

    async def test_source_compile_validate_activate_and_version(self):
        created = self.service.create_document(
            self.user_id,
            name="收费站规则",
            source_document=(
                "分页查询，每页 20 条；page 从 1 开始递增，"
                "直到返回空数据。"
            ),
        )
        document_id = created["id"]
        source_id = created["current_source_version_id"]

        compiled = await self.service.compile_document(
            self.user_id,
            document_id,
            source_version_id=source_id,
        )
        candidate = compiled["compiled_candidates"][0]
        self.assertEqual(candidate["status"], "valid")
        self.assertEqual(
            candidate["specification_version"],
            SPECIFICATION_VERSION,
        )
        self.assertEqual(candidate["validation_errors"], [])
        self.assertEqual(
            candidate["compiled_rule"]["execution_rules"][0]["tools"][
                0
            ]["iteration"]["page_size"],
            20,
        )
        self.assertEqual(
            self.model_outputs[0]["profile"],
            "agent-compiler",
        )

        active = self.service.activate(
            self.user_id,
            document_id,
            compiled_version_id=candidate["id"],
        )
        self.assertEqual(
            active["active_compiled_version_id"],
            candidate["id"],
        )
        self.assertEqual(
            self.service.active_snapshots(self.user_id)[0][
                "compiled_version_id"
            ],
            candidate["id"],
        )

        updated = self.service.update_source(
            self.user_id,
            document_id,
            expected_source_version_id=source_id,
            source_document="更新：每页 50 条，直到空页。",
        )
        self.assertNotEqual(
            updated["current_source_version_id"],
            source_id,
        )
        self.assertEqual(
            updated["active_compiled_version_id"],
            candidate["id"],
        )
        with self.assertRaises(AgentRuleError) as conflict:
            self.service.update_source(
                self.user_id,
                document_id,
                expected_source_version_id=source_id,
                source_document="过期编辑",
            )
        self.assertEqual(conflict.exception.status_code, 409)

    async def test_invalid_candidate_is_retained_but_cannot_activate(self):
        async def invalid_model(_request):
            return {"content": '{"schema_version":"1.0"}'}

        service = AgentRuleService(
            main.db.connection,
            compile_model=invalid_model,
            audit=lambda *_args: None,
        )
        created = service.create_document(
            self.user_id,
            name="无效候选",
            source_document="查询数据。",
        )
        compiled = await service.compile_document(
            self.user_id,
            created["id"],
            source_version_id=created["current_source_version_id"],
        )
        candidate = compiled["compiled_candidates"][0]
        self.assertEqual(candidate["status"], "invalid")
        self.assertTrue(candidate["validation_errors"])
        with self.assertRaises(AgentRuleError) as invalid:
            service.activate(
                self.user_id,
                created["id"],
                compiled_version_id=candidate["id"],
            )
        self.assertEqual(invalid.exception.status_code, 409)
