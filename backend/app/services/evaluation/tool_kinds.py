"""Tool classification and retrieval-context extraction.

Not every tool output is retrieval context. Feeding a calculator result or an
email-send confirmation to FaithfulnessMetric produces a confident, meaningless
score, so anything not positively identified as retrieval is excluded rather
than guessed at.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolKind(str, Enum):
    RETRIEVAL = "retrieval"
    ACTION = "action"
    COMPUTATION = "computation"
    COMMUNICATION = "communication"
    UNKNOWN = "unknown"


# Substrings checked against the tool name, most specific family first.
_NAME_HINTS: list[tuple[ToolKind, tuple[str, ...]]] = [
    (
        ToolKind.RETRIEVAL,
        ("search", "retrieve", "lookup", "query_index", "vector", "rag",
         "knowledge", "document", "corpus", "grounding", "fetch_doc", "find_doc"),
    ),
    (
        ToolKind.COMMUNICATION,
        ("send_", "email", "notify", "slack", "sms", "message_", "publish", "post_to"),
    ),
    (
        ToolKind.COMPUTATION,
        ("calc", "compute", "sum", "math", "convert", "format_", "parse_", "aggregate"),
    ),
    (
        ToolKind.ACTION,
        ("create", "update", "delete", "write", "insert", "upsert", "execute",
         "run_", "trigger", "submit", "approve", "cancel"),
    ),
]

# Keys that commonly hold the document text in a retrieval payload.
_TEXT_KEYS = ("text", "content", "snippet", "chunk", "page_content", "body", "document")
# Lists of strings that are the passages themselves. The live search_documents
# tool returns {"result": [{"title", "source_url", "snippets": [...]}]}.
_SNIPPET_LIST_KEYS = ("snippets", "passages", "chunks", "excerpts", "contents")
_ID_KEYS = ("id", "document_id", "doc_id", "title", "name", "uri", "url", "source")
_SOURCE_KEYS = ("source_url", "source", "uri", "url", "link")
_SCORE_KEYS = ("score", "relevance", "distance", "similarity", "confidence")
# Keys whose value is the list of records in a retrieval response.
_CONTAINER_KEYS = (
    "result",
    "results",
    "documents",
    "chunks",
    "matches",
    "hits",
    "items",
    "passages",
    "records",
    "sources",
    "citations",
)


@dataclass
class RetrievalDoc:
    document_id: str | None = None
    text: str = ""
    score: float | None = None
    rank: int | None = None
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def classify_tool(
    tool_name: str,
    tool_result: Any = None,
    *,
    overrides: dict[str, str] | None = None,
) -> ToolKind:
    """Classify a tool: explicit per-agent override, then name, then payload shape."""
    if overrides:
        override = overrides.get(tool_name)
        if override:
            try:
                return ToolKind(override)
            except ValueError:
                pass

    lowered = (tool_name or "").lower()
    for kind, hints in _NAME_HINTS:
        if any(hint in lowered for hint in hints):
            return kind

    # Nothing in the name -- a payload that looks like ranked documents is
    # retrieval regardless of what it is called.
    if _looks_like_documents(tool_result):
        return ToolKind.RETRIEVAL
    return ToolKind.UNKNOWN


def _records_of(payload: Any) -> list[dict[str, Any]]:
    """Pull the list of record dicts out of a tool response, if there is one."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in _CONTAINER_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                return [r for r in value if isinstance(r, dict)]
        # A single document returned bare.
        if any(k in payload for k in _TEXT_KEYS) or any(
            k in payload for k in _SNIPPET_LIST_KEYS
        ):
            return [payload]
    return []


def _snippets_of(record: dict[str, Any]) -> list[str]:
    for key in _SNIPPET_LIST_KEYS:
        value = record.get(key)
        if isinstance(value, list):
            texts = [s.strip() for s in value if isinstance(s, str) and s.strip()]
            if texts:
                return texts
    return []


def _looks_like_documents(payload: Any) -> bool:
    records = _records_of(payload)
    if not records:
        return False
    with_text = sum(1 for r in records if _first_str(r, _TEXT_KEYS) or _snippets_of(r))
    if not with_text:
        return False
    # Text plus an identifier or a score is document-shaped; text alone is not
    # enough, since plenty of action tools return a message string.
    return any(
        _first_present(r, _ID_KEYS) or _first_present(r, _SCORE_KEYS) for r in records
    ) or with_text >= 2


def _first_present(record: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def _first_str(record: dict[str, Any], keys: tuple[str, ...]) -> str:
    value = _first_present(record, keys)
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return ""
    return str(value) if value is not None else ""


def extract_retrieval_docs(tool_result: Any) -> list[RetrievalDoc]:
    """Normalize a RETRIEVAL tool response into ranked documents.

    Callers must classify first -- this does not re-check the tool kind, so
    passing a non-retrieval payload will produce nonsense by design.
    """
    records = _records_of(tool_result)
    if not records:
        # Some retrieval tools return one blob of text.
        if isinstance(tool_result, str) and tool_result.strip():
            return [RetrievalDoc(text=tool_result.strip(), rank=0)]
        return []

    docs: list[RetrievalDoc] = []
    rank = 0
    for record in records:
        raw_score = _first_present(record, _SCORE_KEYS)
        try:
            score = float(raw_score) if raw_score is not None else None
        except (TypeError, ValueError):
            score = None
        doc_id = _first_present(record, _ID_KEYS)
        source = _first_str(record, _SOURCE_KEYS) or None
        metadata = {
            k: v
            for k, v in record.items()
            if k not in _TEXT_KEYS
            and k not in _SNIPPET_LIST_KEYS
            and not isinstance(v, (dict, list))
        }

        # A record can carry several passages. Emitting one doc per passage
        # keeps contextual precision meaningful -- a single concatenated blob
        # would score as one relevant-or-not unit no matter how much of it
        # was noise.
        snippets = _snippets_of(record)
        texts = snippets or ([_first_str(record, _TEXT_KEYS)] if _first_str(record, _TEXT_KEYS) else [])
        for offset, text in enumerate(texts):
            if not text.strip():
                continue
            suffix = f"#{offset}" if len(texts) > 1 else ""
            docs.append(
                RetrievalDoc(
                    document_id=f"{doc_id}{suffix}" if doc_id is not None else None,
                    text=text.strip(),
                    score=score,
                    rank=rank,
                    source=source,
                    metadata=dict(metadata),
                )
            )
            rank += 1
    return docs


def infer_capabilities(tool_names: list[str], overrides: dict[str, str] | None = None) -> list[str]:
    """Map observed tool names onto the agent capability vocabulary."""
    capabilities: set[str] = set()
    for name in tool_names:
        kind = classify_tool(name, overrides=overrides)
        if kind is ToolKind.RETRIEVAL:
            capabilities.add("retrieval")
        if kind is not ToolKind.UNKNOWN:
            capabilities.add("tool_use")
        lowered = name.lower()
        if any(h in lowered for h in ("exec", "shell", "python", "code", "sandbox")):
            capabilities.add("code_execution")
        if any(h in lowered for h in ("http", "api", "request", "webhook")):
            capabilities.add("external_api")
    if tool_names:
        capabilities.add("tool_use")
    return sorted(capabilities)


def infer_agent_type(
    tool_names: list[str],
    authors: list[str],
    *,
    class_methods: list[str] | None = None,
) -> str:
    """Propose an agent type from observed behaviour.

    A proposal, not a verdict -- onboarding lets the user override it.
    """
    capabilities = infer_capabilities(tool_names)
    # More than one non-user author means sub-agents handed off to each other.
    non_user_authors = {a for a in authors if a and a != "user"}
    if len(non_user_authors) > 1:
        return "multi_agent"
    if "retrieval" in capabilities:
        return "rag"
    if "tool_use" in capabilities:
        return "tool_calling"
    if class_methods and any("stream" in m for m in class_methods):
        return "conversational"
    return "unknown"
