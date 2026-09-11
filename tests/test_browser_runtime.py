from __future__ import annotations

import unittest

from sparkle.browser_runtime import BrowserTransportError, SafeHTTPSBrowserAdapter
from sparkle.interaction import BrowserRequest


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


if __name__ == "__main__":
    unittest.main()
