from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dotenv is a convenience only
    def load_dotenv(*_args, **_kwargs):  # type: ignore
        return False

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = ROOT / "contracts"
FIXTURES_DIR = ROOT / "fixtures"
RUNS_DIR = ROOT / "runs"
RESULTS_DIR = ROOT / "results"

CORE_MODEL_PREFERENCES = [
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    "nvidia/Nemotron-3-Nano-30B-A3B",
    "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B",
    "nvidia/NVIDIA-Nemotron-3-Ultra",
    "nvidia/Llama-3_1-Nemotron-Ultra-253B-v1",
]

COMPARISON_MODEL_HINTS = [
    "Nano-30B",
    "Super-120B",
    "Super",
    "Ultra",
    "Llama-3_1-Nemotron-Ultra-253B",
]

TASK_CLASSES = ["inbox", "schedule", "research"]

CANARY_CATEGORIES = ["bank", "medical", "personal", "financial", "identity"]


@dataclass(slots=True)
class Settings:
    base_url: str = "https://api.tokenfactory.nebius.com/v1/"
    api_key: str = ""
    model: str = ""
    attacker_model: str = ""
    hf_token: str = ""
    user_name: str = "Bibaswan Sarkar"
    region: str = ""
    concurrency: int = 12
    max_usd: float = 25.0
    results_bucket: str = ""
    temperature: float = 0.2
    request_timeout: float = 90.0
    max_steps: int = 12
    fit_personas: int = 40
    eval_personas: int = 100
    quick_fit: int = 8
    quick_eval: int = 10
    shards: int = 5
    tau: float = 0.90
    epsilon: float = 0.02
    max_cegis_iters: int = 8
    adaptive_rounds: int = 3
    seed: int = 20260426
    runs_dir: Path = field(default_factory=lambda: RUNS_DIR)

    @property
    def has_key(self) -> bool:
        return bool(self.api_key.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(ROOT / ".env", override=False)
    region = os.getenv("PF_REGION", "").strip()
    return Settings(
        base_url=os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/").rstrip("/") + "/",
        api_key=os.getenv("NEBIUS_API_KEY", "").strip(),
        model=os.getenv("PF_MODEL", "").strip(),
        attacker_model=os.getenv("PF_ATTACKER_MODEL", "").strip(),
        hf_token=os.getenv("HF_TOKEN", "").strip(),
        user_name=os.getenv("PF_USER_NAME", "Bibaswan Sarkar"),
        region=region,
        concurrency=int(os.getenv("PF_CONCURRENCY", "12")),
        max_usd=float(os.getenv("PF_MAX_USD", "25")),
        results_bucket=os.getenv("PF_RESULTS_BUCKET", "").strip(),
        runs_dir=Path(os.getenv("PF_RUNS_DIR", str(RUNS_DIR))),
    )


def reset_settings_cache() -> None:
    get_settings.cache_clear()
