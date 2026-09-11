from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sparkle.interaction import (
    BrowserAdapter,
    BrowserRequest,
    BrowserResult,
    ComputerAction,
    ComputerAdapter,
    ComputerResult,
    InteractionService,
    InteractionSessionError,
    InteractionSessionStore,
    InteractionUnavailableError,
)


class DeterministicBrowser(BrowserAdapter):
    def browse(self, request):
        return BrowserResult(request.url, "Example", "bounded text", 200)


class DeterministicComputer(ComputerAdapter):
    def perform(self, action):
        return ComputerResult(action.kind, True, "deterministic harness evidence")


class RedirectingBrowser(BrowserAdapter):
    def browse(self, request):
        return BrowserResult("https://not-allowed.example", "Redirect", "text", 200)


class InteractionContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = InteractionSessionStore(Path(self.temp.name) / "sessions.sqlite3")

    def test_defaults_fail_closed_and_claim_no_live_runtime(self):
        service = InteractionService(session_store=self.store)
        status = service.status()
        self.assertEqual(status["contract"], "implemented")
        self.assertEqual(status["session_lifecycle"], "implemented")
        self.assertEqual(status["browser"], "externally_unconfigured")
        self.assertEqual(status["computer"], "externally_unconfigured")
        self.assertFalse(status["live_browser_verified"])
        self.assertFalse(status["live_computer_verified"])
        self.assertFalse(status["agent_tool_registered"])
        request = BrowserRequest("https://example.com/path", ("example.com",))
        with self.assertRaises(InteractionUnavailableError):
            service.browser.browse(request)
        with self.assertRaises(InteractionUnavailableError):
            service.computer.perform(ComputerAction("screenshot"))

    def test_requests_are_https_allowlisted_and_bounded(self):
        invalid = [
            ("http://example.com", ("example.com",)),
            ("https://user@example.com", ("example.com",)),
            ("https://example.com:8443", ("example.com",)),
            ("https://other.example", ("example.com",)),
            ("https://example.com:invalid", ("example.com",)),
        ]
        for url, hosts in invalid:
            with self.subTest(url=url), self.assertRaises(ValueError):
                BrowserRequest(url, hosts)
        with self.assertRaises(ValueError):
            BrowserRequest("https://example.com", ("example.com",), timeout_seconds=0)
        with self.assertRaises(ValueError):
            BrowserResult("https://example.com", "title", "text", 99)

    def test_computer_actions_are_typed_and_bounded(self):
        valid = [
            ComputerAction("screenshot"), ComputerAction("click", x=10, y=20),
            ComputerAction("type_text", text="safe text"), ComputerAction("key", key="CTRL+L"),
        ]
        self.assertEqual([action.kind for action in valid], ["screenshot", "click", "type_text", "key"])
        for value in [
            lambda: ComputerAction("shell"), lambda: ComputerAction("click", x=-1, y=2),
            lambda: ComputerAction("type_text", text=""), lambda: ComputerAction("key", key="bad key"),
        ]:
            with self.assertRaises(ValueError):
                value()

    def test_session_lifecycle_persists_browser_and_computer_evidence(self):
        service = InteractionService(
            browser=DeterministicBrowser(), computer=DeterministicComputer(), session_store=self.store,
        )
        browser = service.start_session("browser", allowed_hosts=["example.com"], ttl_seconds=60)
        result = service.browse_session(browser["id"], "https://example.com/path", expected_revision=1)
        self.assertEqual(result["session_revision"], 2)
        self.assertEqual(service.history(browser["id"])[0]["event"], "browse")
        closed = service.close_session(browser["id"], expected_revision=2)
        self.assertEqual(closed["status"], "closed")
        with self.assertRaisesRegex(InteractionSessionError, "not active"):
            service.browse_session(browser["id"], "https://example.com", expected_revision=3)

        computer = service.start_session("computer", allowed_actions=["screenshot", "click"], ttl_seconds=60)
        action = service.perform_session(computer["id"], {"kind": "click", "x": 3, "y": 4}, expected_revision=1)
        self.assertTrue(action["completed"])
        with self.assertRaisesRegex(InteractionSessionError, "not allowed"):
            service.perform_session(computer["id"], {"kind": "type_text", "text": "blocked"}, expected_revision=2)

    def test_session_revisions_fail_closed(self):
        service = InteractionService(browser=DeterministicBrowser(), session_store=self.store)
        session = service.start_session("browser", allowed_hosts=["example.com"], ttl_seconds=60)
        service.browse_session(session["id"], "https://example.com", expected_revision=1)
        with self.assertRaisesRegex(InteractionSessionError, "revision conflict"):
            service.browse_session(session["id"], "https://example.com", expected_revision=1)

    def test_browser_result_cannot_escape_request_boundary(self):
        service = InteractionService(browser=RedirectingBrowser(), session_store=self.store)
        with self.assertRaises(ValueError):
            service.browse(BrowserRequest("https://example.com", ("example.com",)))


if __name__ == "__main__":
    unittest.main()
