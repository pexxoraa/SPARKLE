from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sparkle.secrets import SecretNotFoundError, SecretResolver
from sparkle.security import (
    APIAccessPolicy,
    APIAuditStore,
    FixedWindowRateLimiter,
    is_loopback_host,
)


class APIAccessPolicyTests(unittest.TestCase):
    def test_authentication_uses_secret_reference_without_status_exposure(self):
        policy = APIAccessPolicy(
            SecretResolver({"SPARKLE_API_TOKEN": "unit-test-token"}),
            required=True,
        )
        self.assertFalse(policy.authorize(None))
        self.assertFalse(policy.authorize("Bearer wrong"))
        self.assertTrue(policy.authorize("Bearer unit-test-token"))
        status = policy.status()
        self.assertTrue(status["authentication_required"])
        self.assertTrue(status["token_configured"])
        self.assertNotIn("unit-test-token", str(status))

    def test_origin_requires_same_host_or_explicit_allowlist(self):
        policy = APIAccessPolicy(
            SecretResolver({}), allowed_origins=("https://console.example",),
        )
        self.assertTrue(policy.origin_allowed(None, "127.0.0.1:8765"))
        self.assertTrue(policy.origin_allowed(
            "http://127.0.0.1:8765", "127.0.0.1:8765",
        ))
        self.assertTrue(policy.origin_allowed(
            "https://console.example", "127.0.0.1:8765",
        ))
        self.assertFalse(policy.origin_allowed(
            "https://evil.example", "127.0.0.1:8765",
        ))
        self.assertFalse(policy.origin_allowed("null", "127.0.0.1:8765"))
        with self.assertRaises(ValueError):
            APIAccessPolicy(SecretResolver({}), allowed_origins=("*",))

    def test_non_loopback_bind_requires_configured_authentication(self):
        self.assertTrue(is_loopback_host("127.0.0.1"))
        self.assertTrue(is_loopback_host("::1"))
        self.assertFalse(is_loopback_host("0.0.0.0"))
        with self.assertRaisesRegex(ValueError, "requires authentication"):
            APIAccessPolicy(SecretResolver({})).validate_bind("0.0.0.0")
        with self.assertRaises(SecretNotFoundError):
            APIAccessPolicy(
                SecretResolver({}), required=True,
            ).validate_bind("0.0.0.0")
        with self.assertRaises(SecretNotFoundError):
            APIAccessPolicy(
                SecretResolver({}), required=True,
            ).validate_bind("127.0.0.1")
        APIAccessPolicy(
            SecretResolver({"SPARKLE_API_TOKEN": "configured"}), required=True,
        ).validate_bind("0.0.0.0")


class RateLimiterTests(unittest.TestCase):
    def test_fixed_window_limits_and_resets_deterministically(self):
        limiter = FixedWindowRateLimiter(2, 10)
        first = limiter.allow("client-a", now=0)
        second = limiter.allow("client-a", now=1)
        blocked = limiter.allow("client-a", now=2)
        reset = limiter.allow("client-a", now=11)
        self.assertTrue(first.allowed)
        self.assertEqual(first.remaining, 1)
        self.assertTrue(second.allowed)
        self.assertEqual(second.remaining, 0)
        self.assertFalse(blocked.allowed)
        self.assertEqual(blocked.retry_after, 8)
        self.assertTrue(reset.allowed)
        self.assertEqual(reset.remaining, 1)

    def test_client_state_is_bounded(self):
        limiter = FixedWindowRateLimiter(1, 60, max_clients=2)
        limiter.allow("one", now=0)
        limiter.allow("two", now=1)
        limiter.allow("three", now=2)
        self.assertEqual(len(limiter._buckets), 2)
        self.assertNotIn("one", limiter._buckets)


class APIAuditStoreTests(unittest.TestCase):
    def test_records_only_bounded_secret_free_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            store = APIAuditStore(Path(directory) / "audit.sqlite3")
            audit_id = store.record("get", "/api/health", 200, "success", 1.25)
            store.record("GET", "/api/private-value", 404, "client_error", 2)
            records = store.recent()
        self.assertEqual(records[0]["path"], "/api/[unknown]")
        self.assertEqual(records[1]["audit_id"], audit_id)
        self.assertEqual(records[1]["path"], "/api/health")
        encoded = str(records)
        self.assertNotIn("private-value", encoded)
        self.assertNotIn("secret-token", encoded)
        self.assertNotIn("127.0.0.1", encoded)
        self.assertNotIn("Origin", encoded)
        with tempfile.TemporaryDirectory() as directory:
            store = APIAuditStore(Path(directory) / "audit.sqlite3")
            with self.assertRaises(ValueError):
                store.record(
                    "GET", "/api/health?token=secret-token", 200, "success", 1,
                )
