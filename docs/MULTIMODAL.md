# Multimodal content contract

SPARKLE `0.15.0-alpha.1` defines a provider-neutral transport contract for
text, image, audio, document, and mixed requests. This release verifies
validation, serialization, routing, context flow, adapter delivery, API flow,
safe tracing, and failure behavior. It does **not** claim semantic image,
audio, or document understanding by MiniMax-M3 or any live provider.

## Wire contract

An explicit message contains one `SPARKLE-CONTENT/1` envelope:

```json
{
  "protocol_version": "SPARKLE-CONTENT/1",
  "parts": [
    {
      "type": "text",
      "content_id": "spk-sha256:<64 lowercase hex characters>",
      "media_type": "text/plain",
      "encoding": "utf-8",
      "data": "Inspect this image",
      "metadata": {"language": "en"}
    },
    {
      "type": "image",
      "content_id": "spk-sha256:<64 lowercase hex characters>",
      "media_type": "image/png",
      "encoding": "base64",
      "data": "iVBORw0KGgo=",
      "metadata": {"height": 1, "width": 1}
    }
  ]
}
```

Text parts use UTF-8 strings. Image, audio, and document parts require canonical
base64. `content_id` is deterministically derived from the validated type,
media type, and decoded bytes; a supplied identifier must match that value.
Objects reject unknown fields. Metadata keys are sorted for canonical JSON and
values are restricted to bounded JSON primitives, arrays, and objects.

Legacy messages such as `Message("user", "hello")` remain plain strings and
serialize exactly as `{"role":"user","content":"hello"}`. No existing text
client must adopt an envelope.

## Bounds

| Boundary | Limit |
|---|---:|
| Parts per envelope | 16 |
| Decoded bytes per envelope | 8,000,000 |
| Messages per model request | 256 |
| Decoded content per model request | 16,000,000 |
| Text part | 1,000,000 bytes |
| Image part | 5,000,000 bytes |
| Audio part | 8,000,000 bytes |
| Document part | 5,000,000 bytes |
| Metadata per part | 4,096 encoded bytes |
| Multimodal `/api/chat` body | 12,000,000 HTTP bytes |

Metadata additionally limits nesting, item count, string size, key syntax, and
finite numeric values. Credential-like keys are rejected. MIME types must match
the declared modality; documents cannot use image, audio, or video MIME roots.

## Model independence

`Message` and `ModelRequest` carry the common envelope. A model adapter declares
`supported_modalities`, validates the complete request, and alone owns any
provider mapping. The model router can select a future enabled adapter that
supports the requested capability and every modality. If none exists,
`UnsupportedModalityError` names only the safe attempted model/provider and the
unsupported types.

The configured MiniMax-M3 adapter remains text-only. It accepts legacy strings
and text-only envelopes, but rejects image, audio, and document input before
secret resolution, request construction, or network access. This preserves the
verified MiniMax integration without inventing a provider contract.

## API

Legacy input is unchanged:

```json
{"message": "Teach me control systems", "agent": "learning"}
```

An explicit request uses `content` instead of `message`:

```json
{
  "agent": "research",
  "content": {
    "protocol_version": "SPARKLE-CONTENT/1",
    "parts": [
      {
        "type": "document",
        "content_id": "spk-sha256:<matching derived identifier>",
        "media_type": "text/plain",
        "encoding": "base64",
        "data": "bm90ZXM=",
        "metadata": {"filename": "notes.txt"}
      }
    ]
  }
}
```

Call `GET /api/content-contract` for machine-readable types and limits. Clients
may omit `content_id` when creating a new envelope; SPARKLE computes it during
validation. `message` and `content` are mutually exclusive.

## Context and traces

Text parts contribute text to retrieval and routing. Non-text parts contribute
only safe modality/MIME descriptors; SPARKLE does not decode their semantics in
the core. The validated envelope itself reaches the compatible adapter.

Traces record ordered input and output modalities, content identifiers,
processing stage, transformation names, destination, outcome, and bounded
execution metadata. Per-part trace metadata is restricted to content type,
derived identifier, media type, decoded byte size, and SHA-256 digest. Raw
text, base64, decoded bytes, and caller metadata are not traced.

Adding video, camera frames, sensor data, spatial content, or gestures requires
a new validated content type and a capable adapter. It does not require changes
to agents, memory, knowledge, tools, the dashboard, or application builders.
