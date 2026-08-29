from __future__ import annotations

import unittest

from sparkle.secrets import SecretNotFoundError, SecretResolver
from sparkle.security import APIAccessPolicy, is_loopback_host


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
