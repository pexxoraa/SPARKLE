# Voice

The voice boundary is implemented with `SpeechToText`, `TextToSpeech`, and
`VoiceService` interfaces. Both future voice and current text are designed to
enter the same core orchestrator.

This build environment exposes no microphone, speaker, ALSA, or PulseAudio
device. The active adapters therefore report `disabled` and raise an explicit
`VoiceUnavailableError`. No continuous audio is transmitted. Wake-word support
is not implemented.
