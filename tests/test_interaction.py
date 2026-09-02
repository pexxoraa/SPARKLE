from __future__ import annotations

import unittest

from sparkle.interaction import (
    BrowserAdapter,
    BrowserRequest,
    BrowserResult,
    ComputerAction,
    ComputerAdapter,
    ComputerResult,
    InteractionService,
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
    def test_defaults_fail_closed_and_claim_no_live_runtime(self):
        service = InteractionService()
        status = service.status()
        self.assertEqual(status["contract"], "implemented")
        self.assertEqual(status["browser"], "unavailable")
        self.assertEqual(status["computer"], "unavailable")
        self.assertFalse(status["live_browser_verified"])
        self.assertFalse(status["live_computer_verified"])
        self.assertFalse(status["agent_tool_registered"])
        request = BrowserRequest(
            "https://example.com/path", ("example.com",),
        )
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
            ComputerAction("screenshot"),
            ComputerAction("click", x=10, y=20),
            ComputerAction("type_text", text="safe text"),
            ComputerAction("key", key="CTRL+L"),
        ]
        self.assertEqual([action.kind for action in valid], [
            "screenshot", "click", "type_text", "key",
        ])
        for value in [
            lambda: ComputerAction("shell"),
            lambda: ComputerAction("click", x=-1, y=2),
            lambda: ComputerAction("type_text", text=""),
            lambda: ComputerAction("key", key="bad key"),
        ]:
            with self.assertRaises(ValueError):
                value()

    def test_injected_adapters_are_test_harnesses_not_live_evidence(self):
        service = InteractionService(
            browser=DeterministicBrowser(), computer=DeterministicComputer(),
        )
        self.assertEqual(service.status()["browser"], "test_harness")
        self.assertEqual(service.status()["computer"], "test_harness")
        self.assertFalse(service.status()["live_browser_verified"])
        result = service.browse(BrowserRequest(
            "https://example.com", ("example.com",),
        ))
        self.assertEqual(result.status_code, 200)
        self.assertTrue(service.perform(
            ComputerAction("click", x=1, y=2),
        ).completed)

    def test_browser_result_cannot_escape_request_boundary(self):
        service = InteractionService(browser=RedirectingBrowser())
        with self.assertRaises(ValueError):
            service.browse(BrowserRequest(
                "https://example.com", ("example.com",),
            ))


if __name__ == "__main__":
    unittest.main()
