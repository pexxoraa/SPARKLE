"""Strict final-answer contract and content-free response diagnostics.

Classification never extracts, repairs or substitutes an answer.
"""
import hashlib
import json

CONTRACT_VERSION = 'SPARKLE-BENCHMARK-RESPONSE/2'
RESPONSE_CONTRACT = '''Benchmark final-response contract:
Use the available native tool-call protocol for actions and observations.
After tool use, return exactly one JSON object as your final assistant text.
No Markdown fences or prose outside the object. Put a requested numeric result
in "answer". Put source citations in "citations", a list of source identifiers
with chunk positions (source_uri without a benchmark: prefix, then :position).
For a task with no numeric answer or citations, a JSON object confirmation is
sufficient for response formatting; task actions are independently checked.
Do not invent evidence or claim actions succeeded when tools failed. Explanations
or uncertainty may be string fields inside the object. Do not expose private data.
'''


def response_shape(text, finish_reason, tool_count=0):
    stripped = text.strip()
    parse_error = None
    try:
        parsed = json.loads(text)
        category = 'json_object' if isinstance(parsed, dict) else 'json_non_object'
    except json.JSONDecodeError as exc:
        parse_error = {'line': exc.lineno, 'column': exc.colno, 'position': exc.pos}
        if not stripped:
            category = 'empty'
        elif stripped.startswith('```'):
            category = 'markdown_fence'
        elif any(tag in stripped for tag in ('<think>', '</think>', '<analysis>', '</analysis>')):
            category = 'reasoning_markup'
        elif stripped.startswith(('{', '[')):
            category = 'malformed_or_extra_json'
        elif '{' in stripped or '[' in stripped:
            category = 'text_with_json_marker'
        else:
            category = 'natural_language_or_unclassified'
    safe_finish = finish_reason if finish_reason in {
        'stop', 'end_turn', 'length', 'max_tokens', 'tool_calls', 'tool_use',
        'content_filter', 'unknown',
    } else 'other'
    return {'response_received': True, 'finish_reason': safe_finish,
            'output_characters': len(text), 'output_bytes': len(text.encode('utf-8')),
            'response_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'format_category': category, 'tool_calls_present': bool(tool_count),
            'tool_call_count': tool_count,
            'truncated': safe_finish in {'length', 'max_tokens'},
            'json_parse_error': parse_error}


class RecordingModels:
    def __init__(self, delegate):
        self.delegate = delegate
        self.responses = []

    @property
    def registry(self):
        return self.delegate.registry

    def complete(self, *args, **kwargs):
        decision, response = self.delegate.complete(*args, **kwargs)
        evidence = response_shape(response.text, response.finish_reason, len(response.tool_calls))
        # NVIDIA normalization supplies flags, never reasoning text.
        for item in response.raw_assistant_content or []:
            if isinstance(item, dict) and item.get('type') == 'nvidia_chat_message':
                evidence['provider_content_type'] = item.get('content_type', 'unknown')
                evidence['reasoning_field_present'] = item.get('reasoning_field_present', False)
        self.responses.append(evidence)
        return decision, response
