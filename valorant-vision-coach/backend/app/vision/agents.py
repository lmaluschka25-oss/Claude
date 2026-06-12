"""Known Valorant agents and label normalization helpers."""
from __future__ import annotations

# Roster used for recognition / label normalization. Extend as new agents ship;
# unknown labels are preserved verbatim rather than dropped.
AGENTS: tuple[str, ...] = (
    "Astra", "Breach", "Brimstone", "Chamber", "Clove", "Cypher", "Deadlock",
    "Fade", "Gekko", "Harbor", "Iso", "Jett", "KAY/O", "Killjoy", "Neon",
    "Omen", "Phoenix", "Raze", "Reyna", "Sage", "Skye", "Sova", "Viper",
    "Vyse", "Yoru",
)

_NORMALIZED = {a.lower().replace("/", "").replace(" ", ""): a for a in AGENTS}


def normalize_agent(name: str | None) -> str | None:
    """Map a raw label to a canonical agent name, or return it unchanged.

    Examples: ``"kayo" -> "KAY/O"``, ``"jett" -> "Jett"``.
    """
    if not name:
        return None
    key = name.lower().replace("/", "").replace(" ", "").replace("_", "")
    return _NORMALIZED.get(key, name)
