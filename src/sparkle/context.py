from __future__ import annotations

from dataclasses import dataclass

from sparkle.content import ContentEnvelope
from sparkle.storage import KnowledgeStore, MemoryStore


@dataclass(slots=True)
class ContextBundle:
    memory: list[dict]
    knowledge: list[dict]

    def render(self) -> str:
        sections: list[str] = []
        if self.memory:
            values = "\n".join(f"- [{item['category']}] {item['value']}" for item in self.memory)
            sections.append(f"Relevant personal memory:\n{values}")
        if self.knowledge:
            values = "\n".join(
                f"- {item['title']} (chunk {item['position']}): {item['content']}" for item in self.knowledge
            )
            sections.append(f"Relevant stored knowledge:\n{values}")
        return "\n\n".join(sections)


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
