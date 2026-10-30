from __future__ import annotations

import importlib.util
import logging

log = logging.getLogger(__name__)

_FALLBACK: list[str] = []


def garak_templates() -> list[str]:
    """Optional NVIDIA garak adapter.

    garak's probe payloads are version-specific. We only import if garak is
    installed and can expose string payloads; otherwise we skip silently and
    record the reason. Built-in templates remain the source of truth.
    """
    if importlib.util.find_spec("garak") is None:
        log.info("garak not installed; using built-in injection seeds")
        return []
    try:
        from garak import _config  # type: ignore  # noqa: F401
        from garak.probes import promptinject  # type: ignore

        payloads: list[str] = []
        for attr in dir(promptinject):
            obj = getattr(promptinject, attr)
            triggers = getattr(obj, "triggers", None)
            if isinstance(triggers, list):
                payloads.extend(str(t) for t in triggers if isinstance(t, str) and 10 < len(t) < 500)
        log.info("harvested %d garak payloads", len(payloads))
        return payloads[:20]
    except Exception as exc:
        log.info("garak import failed (%s); using built-in seeds", exc)
        return []
