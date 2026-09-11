# Voice session lifecycle

SPARKLE keeps speech-to-text and text-to-speech behind provider-neutral adapters. The software-side voice lifecycle now includes persistent sessions, expiry and close semantics, revision-bound STT/TTS actions, bounded input/output validation and content-free evidence.

## Sessions

Voice sessions have an opaque identifier, optional language tag, optional voice identifier, TTL, status and revision. Sessions are active, closed or expired. Every STT/TTS action and close operation requires the exact current revision; stale or concurrent actions fail closed.

Speech-to-text accepts up to 8 MB of audio with a validated `audio/*` media type. Text-to-speech accepts up to 20,000 characters and validates returned audio and media type. Adapter outputs remain bounded before they are exposed to the caller.

## Evidence and privacy boundary

Persistent event history records direction, media type, byte count, SHA-256 digest, text-character count and a bounded transcript result. Raw input audio and synthesis text are not copied into history. This is operational evidence, not proof of transcription or synthesis quality.

The `sparkle-voice` CLI exposes start, inspect, history, transcribe, synthesize and close operations. It uses the same `VoiceService` owned by `SparkleSystem`.

## External acceptance

Default STT/TTS adapters remain disabled and are reported as `externally_unconfigured`. Configured adapters do not become `live_*_verified` merely by existing. Real microphone/speaker access, provider credentials, latency, transcription accuracy and speech quality remain external/manual acceptance work. The repository now contains the provider-neutral software lifecycle needed to support those adapters without blocking unrelated implementation.
