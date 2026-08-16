"""Vulnerability, attack and framework catalogue, derived from installed DeepTeam.

The previous catalogue was two hand-written Python literals. They exposed 21 of
the 39 vulnerabilities DeepTeam ships and 9 of its 31 attacks, omitting every
agentic vulnerability -- goal theft, recursive hijacking, tool orchestration
abuse, unexpected code execution, agent identity abuse -- which are exactly the
ones that matter for an ADK tool-using agent. A hand-written list also drifts
silently on every upgrade.

Everything here is introspected from the installed package, so the catalogue is
whatever the library actually supports.
"""

from __future__ import annotations

import inspect
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class DeepTeamUnavailable(RuntimeError):
    """DeepTeam is not installed. Dynamic scans cannot run."""


@dataclass
class VulnerabilitySpec:
    name: str
    label: str
    category: str
    types: list[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AttackSpec:
    name: str
    label: str
    kind: str  # single_turn | multi_turn
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FrameworkSpec:
    name: str
    label: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Grouping is presentation only; membership is checked against what is installed
# so a vulnerability that exists but is not listed here still appears, under
# "other", rather than vanishing.
_CATEGORY_HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("Data privacy", ("PIILeakage", "PromptLeakage")),
    (
        "Responsible AI",
        ("Bias", "Toxicity", "Fairness", "Ethics", "ChildProtection", "GraphicContent",
         "PersonalSafety", "IllegalActivity", "Misinformation", "IntellectualProperty",
         "Competition", "Politics", "Religion", "Profanity", "SafetyGuardrails"),
    ),
    (
        "Security & access",
        ("BFLA", "BOLA", "RBAC", "DebugAccess", "ShellInjection", "SQLInjection",
         "SSRF", "UnauthorizedAccess"),
    ),
    (
        "Agentic",
        ("ExcessiveAgency", "Robustness", "GoalTheft", "RecursiveHijacking",
         "ToolOrchestrationAbuse", "UnexpectedCodeExecution", "AgentIdentityAbuse",
         "MemoryPoisoning", "PromptInjection"),
    ),
]

_SKIP = {"BaseVulnerability", "CustomVulnerability", "TYPE_CHECKING"}
_ATTACK_SKIP = {"BaseAttack", "BaseSingleTurnAttack", "BaseMultiTurnAttack",
                "AttackParameter", "StopReason"}


def _humanize(name: str) -> str:
    """CamelCase -> spaced words, keeping known acronyms intact."""
    out: list[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i and not name[i - 1].isupper():
            out.append(" ")
        out.append(ch)
    return "".join(out)


def _category_for(name: str) -> str:
    for label, members in _CATEGORY_HINTS:
        if name in members:
            return label
    return "Other"


def _first_line(obj: Any) -> str:
    doc = inspect.getdoc(obj) or ""
    return doc.strip().split("\n")[0][:220]


def _types_of(cls: Any) -> list[str]:
    """Sub-types a vulnerability supports, read from its own default instance."""
    try:
        instance = cls()
    except Exception:
        return []
    values: list[str] = []
    for attr in ("types",):
        raw = getattr(instance, attr, None) or []
        for item in raw:
            value = getattr(item, "value", item)
            if isinstance(value, str):
                values.append(value)
    return values


@lru_cache(maxsize=1)
def vulnerabilities() -> list[VulnerabilitySpec]:
    try:
        import deepteam.vulnerabilities as module
    except ImportError as exc:  # pragma: no cover - depends on install
        raise DeepTeamUnavailable(
            "deepteam is not installed. Run: pip install -r requirements.txt"
        ) from exc

    specs: list[VulnerabilitySpec] = []
    for name in dir(module):
        if not name[0].isupper() or name in _SKIP:
            continue
        cls = getattr(module, name)
        if not inspect.isclass(cls):
            continue
        specs.append(
            VulnerabilitySpec(
                name=name,
                label=_humanize(name),
                category=_category_for(name),
                types=_types_of(cls),
                description=_first_line(cls),
            )
        )
    specs.sort(key=lambda s: (s.category, s.label))
    return specs


@lru_cache(maxsize=1)
def attacks() -> list[AttackSpec]:
    try:
        import deepteam.attacks.multi_turn as multi
        import deepteam.attacks.single_turn as single
    except ImportError as exc:  # pragma: no cover
        raise DeepTeamUnavailable(
            "deepteam is not installed. Run: pip install -r requirements.txt"
        ) from exc

    specs: list[AttackSpec] = []
    for module, kind in ((single, "single_turn"), (multi, "multi_turn")):
        for name in dir(module):
            if not name[0].isupper() or name in _ATTACK_SKIP:
                continue
            cls = getattr(module, name)
            if not inspect.isclass(cls):
                continue
            specs.append(
                AttackSpec(
                    name=name,
                    label=_humanize(name),
                    kind=kind,
                    description=_first_line(cls),
                )
            )
    specs.sort(key=lambda s: (s.kind, s.label))
    return specs


@lru_cache(maxsize=1)
def frameworks() -> list[FrameworkSpec]:
    """Standards presets: DeepTeam maps each to its own vulnerabilities and attacks.

    This is the shortcut most users want -- "scan for OWASP Top 10" rather than
    assembling 39 checkboxes by hand.
    """
    try:
        import deepteam.frameworks as module
    except ImportError as exc:  # pragma: no cover
        raise DeepTeamUnavailable(
            "deepteam is not installed. Run: pip install -r requirements.txt"
        ) from exc

    specs: list[FrameworkSpec] = []
    for name in dir(module):
        if not name[0].isupper() or name == "RedTeamingFramework":
            continue
        cls = getattr(module, name)
        if not inspect.isclass(cls):
            continue
        label = getattr(cls, "name", "") or _humanize(name)
        specs.append(
            FrameworkSpec(
                name=name,
                label=label,
                description=getattr(cls, "description", "") or _first_line(cls),
            )
        )
    specs.sort(key=lambda s: s.label)
    return specs


def resolve_vulnerability(name: str, types: list[str] | None = None) -> Any:
    """Instantiate a vulnerability by name.

    Unknown names raise. The previous implementation logged a warning and
    continued, so a typo silently shrank the scan instead of failing it.
    """
    import deepteam.vulnerabilities as module

    cls = getattr(module, name, None)
    if cls is None or not inspect.isclass(cls):
        raise ValueError(
            f"Unknown vulnerability '{name}'. "
            f"Valid: {[v.name for v in vulnerabilities()]}"
        )
    if types:
        try:
            return cls(types=types)
        except Exception as exc:
            raise ValueError(
                f"Vulnerability '{name}' rejected types {types}: {exc}"
            ) from exc
    return cls()


def resolve_attack(name: str, **kwargs: Any) -> Any:
    import deepteam.attacks.multi_turn as multi
    import deepteam.attacks.single_turn as single

    cls = getattr(single, name, None) or getattr(multi, name, None)
    if cls is None or not inspect.isclass(cls):
        raise ValueError(
            f"Unknown attack '{name}'. Valid: {[a.name for a in attacks()]}"
        )
    try:
        return cls(**kwargs) if kwargs else cls()
    except Exception as exc:
        raise ValueError(f"Attack '{name}' could not be constructed: {exc}") from exc


def resolve_framework(name: str) -> Any:
    import deepteam.frameworks as module

    cls = getattr(module, name, None)
    if cls is None or not inspect.isclass(cls):
        raise ValueError(
            f"Unknown framework '{name}'. Valid: {[f.name for f in frameworks()]}"
        )
    # red_team() takes an instance, and each preset populates its own
    # vulnerabilities and attacks on construction.
    return cls()


def is_available() -> bool:
    try:
        import deepteam  # noqa: F401
    except ImportError:
        return False
    return True


def installed_version() -> str | None:
    try:
        from importlib.metadata import version

        return version("deepteam")
    except Exception:
        return None
