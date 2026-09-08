from __future__ import annotations

import json
from dataclasses import dataclass

from sparkle.content import ContentEnvelope
from sparkle.storage import KnowledgeStore, MemoryStore


@dataclass(slots=True)
class ContextBundle:
    memory: list[dict]
    knowledge: list[dict]

    def render(self) -> str:
        if not self.memory and not self.knowledge:
            return ""
        payload = {
            "trust": "untrusted_retrieved_data",
            "memory": [{"category": r["category"], "value": r["value"][:1000]}
                       for r in self.memory[:5]],
            "knowledge": [{"source_id": r["source_id"], "chunk_id": r["chunk_id"],
                           "position": r["position"], "title": r["title"][:256],
                           "content": r["content"][:1800]} for r in self.knowledge[:5]],
            "bounded_excerpt": True,
        }
        while True:
            rendered = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            if len(rendered.encode("utf-8")) <= 12000:
                return rendered
            if payload["knowledge"]:
                payload["knowledge"].pop()
            else:
                payload["memory"].pop()


class ContextBuilder:
    def __init__(self, memory: MemoryStore, knowledge: KnowledgeStore, *, memory_limit: int = 5, knowledge_limit: int = 5):
        self.memory = memory
        self.knowledge = knowledge
        self.memory_limit = memory_limit
        self.knowledge_limit = knowledge_limit

    def build(self, query: str) -> ContextBundle:
        return ContextBundle(
            memory=self.memory.search(query, limit=self.memory_limit),
            knowledge=self.knowledge.search(query, limit=self.knowledge_limit),
        )

    def build_content(self, content: ContentEnvelope) -> ContextBundle:
        return self.build(content.retrieval_text())
