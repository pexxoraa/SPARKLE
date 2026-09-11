from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sparkle import config
from sparkle.platform_support import (
    default_state_root,
    detect_platform,
    platform_status,
)


class PlatformSupportTests(unittest.TestCase):
    def test_platform_detection_and_explicit_override(self):
        self.assertEqual(detect_platform("linux", {}), "linux")
        self.assertEqual(detect_platform("darwin", {}), "macos")
        self.assertEqual(detect_platform("win32", {}), "windows")
        self.assertEqual(detect_platform("linux", {"ANDROID_ROOT": "/system"}), "android")
        self.assertEqual(
            detect_platform("linux", {"SPARKLE_PLATFORM": "grapheneos"}),
            "grapheneos",
        )
        with self.assertRaises(ValueError):
            detect_platform("plan9", {})
        with self.assertRaises(ValueError):
            detect_platform("linux", {"SPARKLE_PLATFORM": "unknown"})

    def test_default_state_roots_are_platform_native(self):
        home = Path("/home/example")
        self.assertEqual(
            default_state_root(
                platform_name="linux",
                environ={"XDG_STATE_HOME": "/state"},
                home=home,
            ),
            Path("/state/sparkle"),
        )
        self.assertEqual(
            default_state_root(
                platform_name="windows",
                environ={"LOCALAPPDATA": "/local"},
                home=home,
            ),
            Path("/local/SPARKLE"),
        )
        self.assertEqual(
            default_state_root(platform_name="macos", environ={}, home=home),
            Path("/home/example/Library/Application Support/SPARKLE"),
        )
        self.assertEqual(
            default_state_root(platform_name="ios", environ={}, home=home),
            Path("/home/example/Library/Application Support/SPARKLE"),
        )
        self.assertEqual(
            default_state_root(platform_name="grapheneos", environ={}, home=home),
            Path("/home/example/.local/state/sparkle"),
        )

    def test_data_root_explicit_override_remains_authoritative(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                os.environ, {"SPARKLE_DATA_DIR": directory}, clear=False
            ):
                self.assertEqual(config.data_root(), Path(directory).resolve())

    def test_platform_status_matches_software_and_external_boundaries(self):
        linux = platform_status(platform_name="linux", environ={})
        self.assertEqual(linux["browser"], "stdlib_safe_https")
        self.assertEqual(linux["computer"], "adapter_dependent")
        self.assertEqual(linux["voice"], "adapter_dependent")
        self.assertEqual(linux["external_worker"], "software_supported_linux_only")
        self.assertFalse(linux["platform_verified_on_current_host"])
        mobile = platform_status(platform_name="grapheneos", environ={})
        self.assertEqual(
            mobile["core_runtime"], "external_embedded_python_host_required"
        )
        self.assertEqual(mobile["browser"], "stdlib_safe_https")
        self.assertEqual(
            mobile["external_worker"], "external_linux_worker_required"
        )
        self.assertTrue(mobile["mobile_host_acceptance_required"])
        self.assertFalse(mobile["platform_verified_on_current_host"])


if __name__ == "__main__":
    unittest.main()
