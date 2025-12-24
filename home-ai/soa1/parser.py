"""Staged PDF parser emitting structured events for orchestrator consumption."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Dict, Generator, Iterable, List, Protocol

import pdfplumber


class ParseStage(Enum):
    METADATA_READY = auto()
    HEADERS_READY = auto()
    DOC_TEXT_READY = auto()


@dataclass
class ParseEvent:
    stage: ParseStage
    doc_id: str
    filename: str
    payload: Dict


class ParseEventHandler(Protocol):
    def __call__(self, event: ParseEvent) -> None:  # pragma: no cover - typing only
        ...


def iter_pdf_events(doc_id: str, path: Path) -> Generator[ParseEvent, None, None]:
    """Yield staged parse events for a single PDF."""

    with pdfplumber.open(path) as pdf:
        filename = path.name
        metadata = {
            "pages": len(pdf.pages),
            "title": pdf.metadata.get("Title") if pdf.metadata else None,
            "producer": pdf.metadata.get("Producer") if pdf.metadata else None,
            "file_size_bytes": path.stat().st_size,
        }
        yield ParseEvent(
            stage=ParseStage.METADATA_READY,
            doc_id=doc_id,
            filename=filename,
            payload=metadata,
        )

        if pdf.pages:
            first_page = pdf.pages[0]
            header_text = (first_page.extract_text() or "").splitlines()[:10]
            yield ParseEvent(
                stage=ParseStage.HEADERS_READY,
                doc_id=doc_id,
                filename=filename,
                payload={"header_lines": header_text},
            )

        page_chunks: List[str] = []
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                page_chunks.append(text)
        yield ParseEvent(
            stage=ParseStage.DOC_TEXT_READY,
            doc_id=doc_id,
            filename=filename,
            payload={"pages": page_chunks},
        )


def parse_documents(paths: Iterable[Path], handler: ParseEventHandler) -> None:
    """Parse multiple PDFs and dispatch staged events via the handler."""

    for idx, path in enumerate(paths):
        doc_id = f"doc-{idx + 1}"
        for event in iter_pdf_events(doc_id, path):
            handler(event)
