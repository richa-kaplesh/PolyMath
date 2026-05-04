from __future__ import annotations
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel , Field
from datetime import datetime
import uuid

class DocumentType(str, Enum):
    BOOK = "book"
    PAPER = "paper"
    UNKNOWN = "unknown"

class QueryMode(str, Enum):
    QA = "qa"
    SYNTHESIZE = "synthesize"

class RetrievalStrategy(str, Enum):
    STANDARD = "standard"
    HYDE = "hyde"
    MULTI_QUERY = "multi_query"
    HYBRID = "hybrid"

class EvalStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"

class ChapterEntry(BaseModel):
    title: str
    page_start: int
    page_end: Optional[int] = None
    level: int = Field(default=1)

class DocumentCatalogEntry(BaseModel):
    doc_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    title: str
    doc_type: DocumentType
    total_pages: int
    file_size_bytes: int
    file_hash: str
    upload_timestamp: datetime = Field(default_factory=datetime.utcnow)
    chapters: list[ChapterEntry] = Field(default_factory=list)
    preview_text: str = ""
    abstract: Optional[str] = None
    authors: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)
    index_path: str = ""
    chunks_path: str = ""
    total_chunks: int = 0


class ChunkMetadata(BaseModel):
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    doc_id: str
    doc_title: str
    doc_type: DocumentType
    filename: str
    page_number: int
    chapter_title: Optional[str] = None
    section_title: Optional[str] = None
    text: str
    contextualized_text: Optional[str] = None
    char_count: int = 0
    retrieval_score: float = 0.0
    rerank_score: Optional[float] = None

class RetrievedChunk(BaseModel):
    metadata: ChunkMetadata
    score: float
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.STANDARD

    @property
    def display_text(self) -> str:
        return self.metadata.contextualized_text or self.metadata.text

    @property
    def citation_label(self) -> str:
        loc = f"p.{self.metadata.page_number}"
        if self.metadata.chapter_title:
            loc = f"{self.metadata.chapter_title}, {loc}"
        return f"[{self.metadata.doc_title} — {loc}]"

class DocumentContext(BaseModel):
    doc_id: str
    doc_title: str
    doc_type: DocumentType
    chunks: list[RetrievedChunk]

    @property
    def formatted_text(self) -> str:
        lines = [f"=== SOURCE: {self.doc_title} ({self.doc_type}) ==="]
        for i, chunk in enumerate(self.chunks, 1):
            lines.append(
                f"\n[Chunk {i} | {chunk.citation_label}]\n{chunk.display_text}"
            )
        return "\n".join(lines)

class ConversationTurn(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    mode: Optional[QueryMode] = None
    doc_ids_used: list[str] = Field(default_factory=list)

class SessionMemory(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    turns: list[ConversationTurn] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def add_turn(self, role: str, content: str,
                 mode: Optional[QueryMode] = None,
                 doc_ids: Optional[list[str]] = None) -> None:
        self.turns.append(ConversationTurn(
            role=role, content=content,
            mode=mode, doc_ids_used=doc_ids or []
        ))

    def get_history_text(self, max_turns: int = 10) -> str:
        recent = self.turns[-max_turns * 2:]
        lines = []
        for turn in recent:
            prefix = "User" if turn.role == "user" else "Assistant"
            lines.append(f"{prefix}: {turn.content}")
        return "\n".join(lines)


class RAGASScores(BaseModel):
    faithfulness: float = Field(ge=0.0, le=1.0)
    answer_relevance: float = Field(ge=0.0, le=1.0)
    context_precision: float = Field(ge=0.0, le=1.0)
    context_recall: Optional[float] = None
    composite: float = Field(ge=0.0, le=1.0)

    @classmethod
    def compute_composite(
        cls,
        faithfulness: float,
        answer_relevance: float,
        context_precision: float,
        context_recall: Optional[float] = None
    ) -> "RAGASScores":
        scores = [faithfulness, answer_relevance, context_precision]
        weights = [0.4, 0.35, 0.25]
        if context_recall is not None:
            scores.append(context_recall)
            weights = [0.35, 0.30, 0.20, 0.15]
        composite = sum(s * w for s, w in zip(scores, weights))
        return cls(
            faithfulness=faithfulness,
            answer_relevance=answer_relevance,
            context_precision=context_precision,
            context_recall=context_recall,
            composite=composite
        )

class EvalResult(BaseModel):
    eval_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    query: str
    response: str
    scores: RAGASScores
    status: EvalStatus
    retry_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    mode: QueryMode = QueryMode.QA
    session_id: Optional[str] = None
    doc_ids: Optional[list[str]] = None
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    stream: bool = True

class QueryResponse(BaseModel):
    session_id: str
    query: str
    mode: QueryMode
    answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    eval_scores: Optional[RAGASScores] = None
    docs_used: list[str] = Field(default_factory=list)
    latency_ms: Optional[float] = None

class UploadResponse(BaseModel):
    doc_id: str
    filename: str
    title: str
    doc_type: DocumentType
    total_pages: int
    total_chunks: int
    chapters_found: int
    message: str = "Document processed successfully"

class SSEEvent(BaseModel):
    event: str  
    data: Any
    session_id: Optional[str] = None


class SynthesisSection(BaseModel):
    heading: str
    content: str
    source_doc_ids: list[str] = Field(default_factory=list)

class SynthesisOutput(BaseModel):
    synthesis_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    docs_synthesized: list[str]
    agreements: list[SynthesisSection] = Field(default_factory=list)
    contradictions: list[SynthesisSection] = Field(default_factory=list)
    unique_insights: list[SynthesisSection] = Field(default_factory=list)
    consolidated_notes: str = ""
    markdown_output: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow) 