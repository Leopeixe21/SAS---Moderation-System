from __future__ import annotations

import re


OBSERVATION_MARKER = re.compile(
    r"(?<!\w)(?:\*\*)?observa(?:ção|cao)(?:\*\*)?\s*:\s*",
    flags=re.IGNORECASE,
)


def split_reason_observation(reason: str) -> tuple[str, str | None]:
    """Separa a primeira marca 'Observação:' de um motivo de moderação."""
    match = OBSERVATION_MARKER.search(reason)
    if match is None:
        return reason.strip(), None

    observation = reason[match.end() :].strip()
    if not observation:
        return reason.strip(), None

    main_reason = reason[: match.start()].strip() or "Não informado."
    return main_reason, observation
