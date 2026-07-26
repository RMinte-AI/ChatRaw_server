import os
import shutil
import sys
import tempfile
import unittest

TEST_DATA_DIR = tempfile.mkdtemp(prefix="chatraw-title-test-")
os.environ["DATA_DIR"] = TEST_DATA_DIR

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend import main  # noqa: E402


def tearDownModule():
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


class FakeTitleLLM(main.LLMService):
    def __init__(self, db):
        super().__init__(db)
        self.raw_calls = []
        self.result = "Model generated title"
        self.error = None
        self.before_return = None

    async def _call_chat_completion_raw(
        self,
        config,
        messages,
        max_tokens,
        temperature=0.2,
    ):
        self.raw_calls.append({
            "config": config,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })
        if self.before_return is not None:
            self.before_return()
        if self.error is not None:
            raise self.error
        return self.result


class ChatTitleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="chatraw-title-db-")
        self.db = main.Database(os.path.join(self.tmpdir, "chatraw.db"))
        self.db.save_model_config(main.ModelConfig(
            id="default-chat",
            name="Fake Chat Model",
            api_url="http://example.test/v1",
            model_id="fake-chat",
            context_length=4096,
            max_output=1024,
            type="chat",
        ))
        self.llm = FakeTitleLLM(self.db)
        self.service = main.ChatTitleService(self.db, self.llm)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def create_first_exchange(self, user_message="Explain atomic writes"):
        chat = self.db.create_chat(main.DEFAULT_CHAT_TITLE)
        self.db.add_message(chat.id, "user", user_message)
        return chat

    async def test_first_exchange_uses_model_title_once(self):
        chat = self.create_first_exchange()

        await main.save_assistant_message(
            self.db,
            chat.id,
            "Explain atomic writes",
            "Atomic writes prevent partially visible state.",
            title_service=self.service,
        )
        first_title = self.db.get_chats()[0].title
        await self.service.maybe_title_chat(
            chat.id,
            "Explain atomic writes",
            "Atomic writes prevent partially visible state.",
        )

        self.assertEqual(first_title, "Model generated title")
        self.assertEqual(len(self.llm.raw_calls), 1)
        prompt = self.llm.raw_calls[0]["messages"]
        self.assertIn("Explain atomic writes", prompt[1]["content"])
        self.assertIn("partially visible state", prompt[1]["content"])
        self.assertEqual(self.llm.raw_calls[0]["max_tokens"], 64)

    async def test_manual_rename_wins_model_race(self):
        chat = self.create_first_exchange()
        self.db.add_message(chat.id, "assistant", "Answer")
        self.llm.before_return = lambda: self.db.update_chat_title(
            chat.id,
            "Manual title",
        )

        updated = await self.service.maybe_title_chat(
            chat.id,
            "Explain atomic writes",
            "Answer",
        )

        self.assertFalse(updated)
        self.assertEqual(self.db.get_chats()[0].title, "Manual title")

    async def test_model_failure_uses_existing_deterministic_fallback(self):
        user_message = "x" * 40
        chat = self.create_first_exchange(user_message)
        self.db.add_message(chat.id, "assistant", "Answer")
        self.llm.error = RuntimeError("model unavailable")

        updated = await self.service.maybe_title_chat(
            chat.id,
            user_message,
            "Answer",
        )

        self.assertTrue(updated)
        self.assertEqual(self.db.get_chats()[0].title, ("x" * 30) + "...")

    async def test_non_initial_exchange_does_not_call_title_model(self):
        chat = self.create_first_exchange()
        self.db.add_message(chat.id, "assistant", "First answer")
        self.db.add_message(chat.id, "user", "Second question")
        self.db.add_message(chat.id, "assistant", "Second answer")

        updated = await self.service.maybe_title_chat(
            chat.id,
            "Second question",
            "Second answer",
        )

        self.assertFalse(updated)
        self.assertEqual(self.llm.raw_calls, [])
        self.assertEqual(self.db.get_chats()[0].title, main.DEFAULT_CHAT_TITLE)
