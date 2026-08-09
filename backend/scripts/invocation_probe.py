"""Agent Engine invocation compatibility probe.

Phase 1 gate: determines which REST interface AgentOps should use to invoke a
deployed Agent Engine. `:query` accepts a `classMethod` that defaults to
`query`, while `:streamQuery` is the endpoint documented for streaming --
whether `:query` + classMethod=stream_query behaves identically to
`:streamQuery` is an assumption, not a guarantee, so it gets measured.

For each variant this records: HTTP status, response shape, where the answer
text actually lives, whether a session/invocationId is produced, whether tool
events are persisted, whether sessions.events.list holds the COMPLETE
trajectory (functionCall AND functionResponse), and latency.

Standalone by design -- imports nothing from app/ so it can run before any of
the invoker refactor exists.

Usage:
    python backend/scripts/invocation_probe.py --engine 4370486702397980672
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import google.auth
from google.auth.transport.requests import AuthorizedSession

USER_ID = "agentops-probe"
DEFAULT_PROMPT = "Reply with the single word: ok"

# The three candidate interfaces. Order matters only for report readability.
VARIANTS = [
    ("A", "query", "query"),
    ("B", "query", "stream_query"),
    ("C", "streamQuery", "stream_query"),
]


@dataclass
class VariantResult:
    label: str
    endpoint: str
    class_method: str
    status: int | None = None
    latency_ms: int | None = None
    error: str | None = None
    response_kind: str | None = None
    response_keys: list[str] = field(default_factory=list)
    text_location: str | None = None
    text_preview: str | None = None
    session_created: bool = False
    session_id: str | None = None
    event_count: int = 0
    invocation_ids: list[str] = field(default_factory=list)
    authors: list[str] = field(default_factory=list)
    function_calls: list[str] = field(default_factory=list)
    function_responses: list[str] = field(default_factory=list)

    @property
    def complete_trajectory(self) -> bool:
        """Both halves of every tool interaction survived into the event log."""
        return bool(self.function_calls) and bool(self.function_responses)

    @property
    def verdict(self) -> str:
        if self.error:
            return "FAIL"
        if not self.text_location:
            return "NO TEXT"
        if not self.event_count:
            return "NO EVENTS"
        if not self.complete_trajectory:
            return "PARTIAL"
        return "PASS"


class AgentEngineProbe:
    def __init__(self, project: str, region: str, engine_id: str) -> None:
        credentials, default_project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self.project = project or default_project
        if not self.project:
            raise SystemExit("No project: pass --project or set one in ADC")
        self.region = region
        self.engine_id = engine_id
        self.session = AuthorizedSession(credentials)
        self.base = (
            f"https://{region}-aiplatform.googleapis.com/v1/"
            f"projects/{self.project}/locations/{region}/reasoningEngines/{engine_id}"
        )

    # -- raw helpers ----------------------------------------------------

    def _post(self, suffix: str, body: dict[str, Any], *, stream: bool = False):
        return self.session.post(
            self.base + suffix,
            json=body,
            stream=stream,
            timeout=300,
            headers={"x-goog-user-project": self.project},
        )

    def _get(self, suffix: str) -> Any:
        r = self.session.get(
            self.base + suffix,
            timeout=60,
            headers={"x-goog-user-project": self.project},
        )
        r.raise_for_status()
        return r.json()

    # -- session lifecycle ----------------------------------------------

    def create_session(self) -> str:
        r = self._post("/sessions", {"userId": USER_ID})
        r.raise_for_status()
        op = r.json()
        # sessions.create is a long-running operation; poll it out.
        name = op.get("response", {}).get("name") or self._await_operation(op)
        return name.split("/")[-1]

    def _await_operation(self, op: dict[str, Any], timeout_s: int = 120) -> str:
        op_name = op.get("name")
        if not op_name:
            raise RuntimeError(f"sessions.create returned no operation: {op}")
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            r = self.session.get(
                f"https://{self.region}-aiplatform.googleapis.com/v1/{op_name}",
                timeout=60,
                headers={"x-goog-user-project": self.project},
            )
            r.raise_for_status()
            cur = r.json()
            if cur.get("done"):
                if "error" in cur:
                    raise RuntimeError(f"sessions.create failed: {cur['error']}")
                return cur["response"]["name"]
            time.sleep(1)
        raise TimeoutError("sessions.create did not complete")

    def delete_session(self, session_id: str) -> None:
        try:
            self.session.delete(
                f"{self.base}/sessions/{session_id}",
                timeout=60,
                headers={"x-goog-user-project": self.project},
            )
        except Exception as exc:  # cleanup must never mask a probe result
            print(f"  ! session cleanup failed: {exc}", file=sys.stderr)

    def list_events(self, session_id: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        page = ""
        while True:
            suffix = f"/sessions/{session_id}/events?pageSize=200"
            if page:
                suffix += f"&pageToken={page}"
            data = self._get(suffix)
            events.extend(data.get("sessionEvents", []))
            page = data.get("nextPageToken", "")
            if not page:
                return events

    # -- probe ----------------------------------------------------------

    def run_variant(
        self, label: str, endpoint: str, class_method: str, prompt: str
    ) -> VariantResult:
        res = VariantResult(label=label, endpoint=f":{endpoint}", class_method=class_method)
        session_id: str | None = None
        try:
            session_id = self.create_session()
            res.session_created = True
            res.session_id = session_id
        except Exception as exc:
            res.error = f"sessions.create: {exc}"
            return res

        body = {
            "classMethod": class_method,
            "input": {
                "user_id": USER_ID,
                "session_id": session_id,
                "message": prompt,
            },
        }

        start = time.perf_counter()
        try:
            streaming = endpoint == "streamQuery"
            r = self._post(f":{endpoint}", body, stream=streaming)
            res.status = r.status_code
            if r.status_code >= 400:
                res.error = r.text[:400]
            else:
                payload = _read_stream(r) if streaming else r.json()
                res.response_kind = type(payload).__name__
                if isinstance(payload, dict):
                    res.response_keys = sorted(payload.keys())
                elif isinstance(payload, list) and payload and isinstance(payload[0], dict):
                    res.response_keys = sorted(payload[0].keys())
                loc, text = find_text(payload)
                res.text_location = loc
                res.text_preview = (text or "")[:160]
        except Exception as exc:
            res.error = f"{type(exc).__name__}: {exc}"
        res.latency_ms = int((time.perf_counter() - start) * 1000)

        try:
            events = self.list_events(session_id)
            res.event_count = len(events)
            for e in events:
                inv = e.get("invocationId")
                if inv and inv not in res.invocation_ids:
                    res.invocation_ids.append(inv)
                author = e.get("author")
                if author and author not in res.authors:
                    res.authors.append(author)
                for part in (e.get("content") or {}).get("parts") or []:
                    if "functionCall" in part:
                        res.function_calls.append(part["functionCall"].get("name", "?"))
                    if "functionResponse" in part:
                        res.function_responses.append(part["functionResponse"].get("name", "?"))
        except Exception as exc:
            res.error = (res.error or "") + f" | events.list: {exc}"

        self.delete_session(session_id)
        return res

    def probe_bad_class_method(self) -> str:
        """How does the API fail on a nonsense classMethod? Shapes error handling."""
        try:
            r = self._post(
                ":query",
                {"classMethod": "definitely_not_a_method", "input": {"message": "x"}},
            )
            return f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"


def _read_stream(response) -> Any:
    """streamQuery emits a sequence of JSON chunks; collect them all."""
    chunks: list[Any] = []
    buffer = ""
    for raw in response.iter_lines(decode_unicode=True):
        if not raw:
            continue
        line = raw.lstrip("[,").rstrip("]").strip()
        if line.startswith("data:"):
            line = line[5:].strip()
        if not line:
            continue
        buffer += line
        try:
            chunks.append(json.loads(buffer))
            buffer = ""
        except json.JSONDecodeError:
            continue  # chunk spans multiple lines
    if buffer:
        try:
            chunks.append(json.loads(buffer))
        except json.JSONDecodeError:
            chunks.append({"_unparsed": buffer[:500]})
    return chunks


def find_text(payload: Any, path: str = "$") -> tuple[str | None, str | None]:
    """Locate the answer text and report the JSON path it was found at."""
    if isinstance(payload, str):
        return (path, payload) if payload.strip() else (None, None)
    if isinstance(payload, dict):
        # ADK content shape wins over a bare stringly-typed field.
        for key in ("content", "output", "response", "text", "result"):
            if key in payload:
                loc, text = find_text(payload[key], f"{path}.{key}")
                if text:
                    return loc, text
        for key, value in payload.items():
            loc, text = find_text(value, f"{path}.{key}")
            if text:
                return loc, text
    if isinstance(payload, list):
        # Last non-empty entry: streaming emits partials, the answer is at the end.
        for i in range(len(payload) - 1, -1, -1):
            loc, text = find_text(payload[i], f"{path}[{i}]")
            if text:
                return loc, text
    return None, None


def render_report(engine: str, project: str, region: str,
                  results: list[VariantResult], bad_method: str) -> str:
    lines = [
        "# Agent Engine invocation compatibility",
        "",
        "Generated by `backend/scripts/invocation_probe.py` (Phase 1 gate).",
        "",
        f"- Project: `{project}`",
        f"- Region: `{region}`",
        f"- Engine: `{engine}`",
        "",
        "## Summary",
        "",
        "| # | Endpoint | classMethod | Status | Verdict | Latency | Events | Tool calls | Tool responses |",
        "|---|----------|-------------|--------|---------|---------|--------|------------|----------------|",
    ]
    for r in results:
        lines.append(
            f"| {r.label} | `{r.endpoint}` | `{r.class_method}` | {r.status or '-'} | "
            f"**{r.verdict}** | {r.latency_ms or '-'} ms | {r.event_count} | "
            f"{len(r.function_calls)} | {len(r.function_responses)} |"
        )

    lines += ["", "## Detail", ""]
    for r in results:
        lines += [
            f"### {r.label} — `{r.endpoint}` classMethod=`{r.class_method}`",
            "",
            f"- Verdict: **{r.verdict}**",
            f"- HTTP status: `{r.status}`",
            f"- Latency: `{r.latency_ms} ms`",
            f"- Session created: `{r.session_created}`",
            f"- Response type: `{r.response_kind}`",
            f"- Top-level keys: `{r.response_keys}`",
            f"- Answer text found at: `{r.text_location}`",
            f"- Text preview: `{(r.text_preview or '').strip()[:120]}`",
            f"- Events persisted: `{r.event_count}`",
            f"- invocationId produced: `{bool(r.invocation_ids)}` ({len(r.invocation_ids)})",
            f"- Authors seen: `{r.authors}`",
            f"- functionCall: `{r.function_calls}`",
            f"- functionResponse: `{r.function_responses}`",
            f"- Complete trajectory: `{r.complete_trajectory}`",
            f"- Error: `{r.error}`",
            "",
        ]

    passing = [r for r in results if r.verdict == "PASS"]
    usable = passing or [r for r in results if r.verdict in ("PARTIAL", "NO EVENTS")]
    lines += [
        "## Bad classMethod behaviour",
        "",
        f"```\n{bad_method}\n```",
        "",
        "## Gate decision",
        "",
    ]
    if passing:
        chosen = passing[0]
        lines.append(
            f"**GATE PASSED.** Chosen interface: `{chosen.endpoint}` with "
            f"`classMethod={chosen.class_method}` — complete trajectory "
            f"(functionCall + functionResponse) recoverable from `sessions.events.list`."
        )
    elif usable:
        chosen = usable[0]
        lines.append(
            f"**GATE PASSED WITH CAVEAT.** No variant produced a complete tool "
            f"trajectory on this engine. Best available: `{chosen.endpoint}` with "
            f"`classMethod={chosen.class_method}`. Note the probe agent may simply "
            f"not call tools for this prompt — re-run against a tool-using agent "
            f"before treating this as a limitation of the interface."
        )
    else:
        lines.append("**GATE FAILED.** No variant returned usable output. Do not proceed.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--engine", required=True, help="Reasoning engine numeric ID")
    ap.add_argument("--project", default="", help="GCP project (defaults to ADC project)")
    ap.add_argument("--region", default="us-central1")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--out", default="docs/invocation_compatibility.md")
    args = ap.parse_args()

    probe = AgentEngineProbe(args.project, args.region, args.engine)
    print(f"Probing {probe.base}\n")

    results = []
    for label, endpoint, class_method in VARIANTS:
        print(f"[{label}] :{endpoint} classMethod={class_method} ...", flush=True)
        r = probe.run_variant(label, endpoint, class_method, args.prompt)
        print(
            f"    {r.verdict} status={r.status} {r.latency_ms}ms "
            f"events={r.event_count} calls={len(r.function_calls)} "
            f"resp={len(r.function_responses)} text_at={r.text_location}"
        )
        if r.error:
            print(f"    error: {r.error[:200]}")
        results.append(r)

    print("\n[bad classMethod] ...", flush=True)
    bad = probe.probe_bad_class_method()
    print(f"    {bad[:200]}")

    report = render_report(args.engine, probe.project, args.region, results, bad)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(report)
    print(f"\nWrote {args.out}")

    return 0 if any(r.verdict in ("PASS", "PARTIAL", "NO EVENTS") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
