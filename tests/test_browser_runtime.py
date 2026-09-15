from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from sparkle.browser_runtime import (
    BrowserTransportError,
    DefaultInteractionService,
    SafeHTTPSBrowserAdapter,
    run_browser_acceptance,
)
from sparkle.interaction import (
    BrowserRequest,
    InteractionSessionError,
    InteractionSessionStore,
)
from sparkle.interaction_cli import _read_artifact, _write_new_artifact


class BrowserRuntimeTests(unittest.TestCase):
    def test_html_fetch_uses_public_pinned_ip_and_extracts_text(self):
        seen = []

        def fetcher(url, ip, timeout, max_bytes):
            seen.append((url, ip, timeout, max_bytes))
            return (
                200,
                {"content-type": "text/html; charset=utf-8"},
                b"<html><head><title>Example</title></head><body>Hello <b>world</b></body></html>",
            )

        adapter = SafeHTTPSBrowserAdapter(
            resolver=lambda host: ["93.184.216.34"],
            fetcher=fetcher,
        )
        result = adapter.browse(
            BrowserRequest(
                "https://example.com/path",
                ("example.com",),
                timeout_seconds=7,
                max_text_chars=200,
            )
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.title, "Example")
        self.assertIn("Hello", result.text)
        self.assertIn("world", result.text)
        self.assertEqual(seen[0][1], "93.184.216.34")
        self.assertEqual(seen[0][2], 7)

    def test_private_dns_and_disallowed_redirect_fail_closed(self):
        called = False

        def fetcher(*args):
            nonlocal called
            called = True
            return (200, {"content-type": "text/plain"}, b"never")

        private = SafeHTTPSBrowserAdapter(
            resolver=lambda host: ["127.0.0.1"],
            fetcher=fetcher,
        )
        with self.assertRaisesRegex(BrowserTransportError, "non-public"):
            private.browse(
                BrowserRequest("https://example.com", ("example.com",))
            )
        self.assertFalse(called)

        redirect = SafeHTTPSBrowserAdapter(
            resolver=lambda host: ["93.184.216.34"],
            fetcher=lambda *args: (
                302,
                {
                    "content-type": "text/plain",
                    "location": "https://other.example/",
                },
                b"",
            ),
        )
        with self.assertRaises(ValueError):
            redirect.browse(
                BrowserRequest("https://example.com", ("example.com",))
            )

    def test_redirects_are_revalidated_and_bounded(self):
        calls = []

        def fetcher(url, ip, timeout, max_bytes):
            calls.append(url)
            if url.endswith("/start"):
                return (
                    302,
                    {
                        "content-type": "text/plain",
                        "location": "/final",
                    },
                    b"",
                )
            return (200, {"content-type": "text/plain"}, b"final")

        adapter = SafeHTTPSBrowserAdapter(
            resolver=lambda host: ["93.184.216.34"],
            fetcher=fetcher,
        )
        result = adapter.browse(
            BrowserRequest(
                "https://example.com/start", ("example.com",)
            )
        )
        self.assertEqual(result.final_url, "https://example.com/final")
        self.assertEqual(result.text, "final")
        self.assertEqual(len(calls), 2)

        loop = SafeHTTPSBrowserAdapter(
            resolver=lambda host: ["93.184.216.34"],
            fetcher=lambda url, *_: (
                302,
                {"content-type": "text/plain", "location": url},
                b"",
            ),
        )
        with self.assertRaisesRegex(BrowserTransportError, "loop"):
            loop.browse(
                BrowserRequest("https://example.com/a", ("example.com",))
            )

    def test_content_type_compression_and_text_bounds_fail_closed(self):
        for headers, body, message in (
            ({"content-type": "application/octet-stream"}, b"x", "content type"),
            (
                {
                    "content-type": "text/plain",
                    "content-encoding": "gzip",
                },
                b"x",
                "compressed",
            ),
            ({"content-type": "text/plain"}, b"0123456789", "extracted text"),
        ):
            with self.subTest(message=message):
                adapter = SafeHTTPSBrowserAdapter(
                    resolver=lambda host: ["93.184.216.34"],
                    fetcher=lambda *args, h=headers, b=body: (200, h, b),
                )
                request = BrowserRequest(
                    "https://example.com",
                    ("example.com",),
                    max_text_chars=5 if message == "extracted text" else 20,
                )
                with self.assertRaisesRegex(BrowserTransportError, message):
                    adapter.browse(request)

    def test_host_acceptance_is_bound_persistent_expiring_and_revocable(self):
        def resolver(host):
            if host in {"127.0.0.1", "10.0.0.1", "192.0.2.1"}:
                return [host]
            return ["93.184.216.34"]

        def fetcher(url, *_):
            if url.startswith("https://wrong.host.badssl.com/"):
                raise BrowserTransportError(
                    "Browser transport failed (SSLCertVerificationError)"
                )
            if url.startswith("https://httpbin.org/redirect-to"):
                return (
                    302,
                    {
                        "content-type": "text/plain",
                        "location": "https://example.com/",
                    },
                    b"",
                )
            return (
                200,
                {"content-type": "text/html; charset=utf-8"},
                b"<html><head><title>Example</title></head>"
                b"<body>This deliberately long bounded browser acceptance body "
                b"contains more than thirty two characters.</body></html>",
            )

        adapter = SafeHTTPSBrowserAdapter(resolver=resolver, fetcher=fetcher)
        evidence = run_browser_acceptance(adapter)
        self.assertTrue(evidence["passed"])
        self.assertTrue(all(evidence["checks"].values()))
        encoded = (
            json.dumps(evidence, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        with tempfile.TemporaryDirectory() as directory:
            store_path = Path(directory) / "sessions.sqlite3"
            service = DefaultInteractionService(
                browser=adapter,
                session_store=InteractionSessionStore(store_path),
            )
            self.assertFalse(service.status()["live_browser_verified"])
            accepted = service.record_browser_acceptance(
                evidence,
                artifact_sha256=hashlib.sha256(encoded).hexdigest(),
                artifact_ref="browser-acceptance.json",
                operator="test-operator",
                expires_at=time.time() + 3_600,
            )
            self.assertTrue(accepted["verified"])
            self.assertTrue(service.status()["live_browser_verified"])

            reopened = DefaultInteractionService(
                browser=adapter,
                session_store=InteractionSessionStore(store_path),
            )
            self.assertTrue(reopened.browser_acceptance()["verified"])
            with self.assertRaisesRegex(
                InteractionSessionError, "already recorded"
            ):
                reopened.record_browser_acceptance(
                    evidence,
                    artifact_sha256=hashlib.sha256(encoded).hexdigest(),
                    artifact_ref="browser-acceptance.json",
                    operator="test-operator",
                    expires_at=time.time() + 3_600,
                )
            tampered = dict(evidence)
            tampered["build_sha256"] = "0" * 64
            with self.assertRaisesRegex(
                InteractionSessionError, "current passing contract"
            ):
                reopened.record_browser_acceptance(
                    tampered,
                    artifact_sha256="1" * 64,
                    artifact_ref="tampered.json",
                    operator="test-operator",
                    expires_at=time.time() + 3_600,
                )
            revoked = reopened.revoke_browser_acceptance(
                str(accepted["record_id"]),
                operator="test-operator",
                reason="acceptance environment changed",
            )
            self.assertFalse(revoked["verified"])
            self.assertEqual(revoked["reason"], "revoked")

    def test_acceptance_artifact_is_owner_only_new_and_not_a_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, artifact_sha256 = _write_new_artifact(
                str(root / "acceptance.json"), {"passed": True}
            )
            self.assertEqual(
                artifact_sha256,
                hashlib.sha256(b'{\n  "passed": true\n}\n').hexdigest(),
            )
            self.assertEqual(target.stat().st_mode & 0o077, 0)
            reopened, raw, decoded = _read_artifact(str(target))
            self.assertEqual(reopened, target)
            self.assertTrue(raw.endswith(b"\n"))
            self.assertEqual(decoded, {"passed": True})
            with self.assertRaisesRegex(ValueError, "new regular file"):
                _write_new_artifact(str(target), {"passed": True})

            alias = root / "acceptance-link.json"
            alias.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "owner-only"):
                _read_artifact(str(alias))
            os.chmod(target, 0o644)
            with self.assertRaisesRegex(ValueError, "owner-only"):
                _read_artifact(str(target))


if __name__ == "__main__":
    unittest.main()
