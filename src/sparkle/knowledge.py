from __future__ import annotations

import mimetypes
from pathlib import Path

from sparkle.storage import KnowledgeStore


class KnowledgeIngestError(RuntimeError):
    pass


TEXT_EXTENSIONS = {
    ".txt", ".md", ".rst", ".csv", ".tsv", ".json", ".yaml", ".yml", ".xml",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp", ".h", ".hpp",
    ".go", ".rs", ".sql", ".sh", ".html", ".css",
}


class KnowledgeIngestor:
    def __init__(self, store: KnowledgeStore, *, max_bytes: int = 50_000_000):
        self.store = store
        self.max_bytes = max_bytes

    def extract(self, path: Path) -> tuple[str, str]:
        target = path.resolve()
        if not target.is_file():
            raise KnowledgeIngestError("Knowledge source does not exist")
        if target.stat().st_size > self.max_bytes:
            raise KnowledgeIngestError("Knowledge source exceeds the configured size limit")
        extension = target.suffix.lower()
        if extension in TEXT_EXTENSIONS:
            return target.read_text(encoding="utf-8"), mimetypes.guess_type(target.name)[0] or "text/plain"
        if extension == ".pdf":
            try:
                from pypdf import PdfReader
            except ImportError as exc:
                raise KnowledgeIngestError("PDF ingestion requires the 'documents' optional dependencies") from exc
            reader = PdfReader(target)
            return "\n\n".join(page.extract_text() or "" for page in reader.pages), "application/pdf"
        if extension == ".docx":
            try:
                from docx import Document
            except ImportError as exc:
                raise KnowledgeIngestError("DOCX ingestion requires the 'documents' optional dependencies") from exc
            document = Document(target)
            return "\n\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        raise KnowledgeIngestError(f"Unsupported knowledge format: {extension or 'none'}")

    def ingest(
        self,
        path: Path,
        *,
        title: str | None = None,
        monitor_key: str | None = None,
    ) -> int:
        content, media_type = self.extract(path)
        if not content.strip():
            raise KnowledgeIngestError("Knowledge source contains no extractable text")
        metadata = (
            {"research_monitor": True, "monitor_key": monitor_key}
            if monitor_key is not None else None
        )
        return self.store.ingest_text(
            title or path.stem,
            content,
            source_uri=str(path.resolve()),
            media_type=media_type,
            metadata=metadata,
        )
