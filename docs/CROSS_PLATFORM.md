# Cross-platform software support

SPARKLE's provider-neutral core targets Linux, Windows and macOS Python hosts. The
dashboard is browser-based and can be used from Android, iOS and GrapheneOS clients.
Mobile-hosted Python execution is not claimed as verified; it requires an embedded
Python application/runtime and platform-specific packaging outside this repository.

`platform_support.py` centralizes platform detection and capability claims. An explicit
`SPARKLE_PLATFORM` override supports `linux`, `windows`, `macos`, `android`, `ios`, or
`grapheneos` for controlled embedded environments. Unknown hosts fail closed instead of
being silently treated as Linux.

Default persistent-state locations are now platform-native when
`SPARKLE_DATA_DIR` is not set and SPARKLE is not running from a checkout:

- Linux/Android/GrapheneOS: `$XDG_STATE_HOME/sparkle` or `~/.local/state/sparkle`.
- Windows: `%LOCALAPPDATA%\\SPARKLE` (falling back to `~/AppData/Local/SPARKLE`).
- macOS/iOS: `~/Library/Application Support/SPARKLE`.

`SPARKLE_DATA_DIR` remains authoritative on every platform and is recommended for
mobile/embedded packaging where the application sandbox controls writable locations.

The controlled external worker remains Linux-specific because its hardened isolation
uses POSIX process groups and Bubblewrap namespaces. Windows, macOS, Android, iOS and
GrapheneOS hosts therefore use an external Linux worker for that capability. Browser,
computer and voice execution continue through provider-neutral adapters and must not be
reported as live until a host adapter has been configured and manually accepted.

This is software architecture coverage, not a claim that every OS/device has completed
manual installation, GUI, audio, browser, accessibility, or Level 3 acceptance testing.
