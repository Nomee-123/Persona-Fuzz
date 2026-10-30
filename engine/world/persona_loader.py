from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from ..config import FIXTURES_DIR, Settings, get_settings

FIRST_NAMES = [
    "Aarav", "Aditi", "Advait", "Aisha", "Ananya", "Aniket", "Anjali", "Arjun", "Aryan",
    "Bhavna", "Chaitanya", "Devika", "Dhruv", "Diya", "Farhan", "Gauri", "Harsh", "Ira",
    "Ishaan", "Jaya", "Kabir", "Kavya", "Kiran", "Kritika", "Lakshmi", "Manav", "Meera",
    "Mihir", "Nandini", "Neel", "Nisha", "Om", "Pallavi", "Pranav", "Priya", "Rahul",
    "Riya", "Rohan", "Saanvi", "Sahil", "Sakshi", "Sanjay", "Shreya", "Siddharth",
    "Sneha", "Tanvi", "Tara", "Varun", "Vidya", "Yash", "Zoya",
]
LAST_NAMES = [
    "Agarwal", "Banerjee", "Bhat", "Chandra", "Chatterjee", "Das", "Desai", "Dutta",
    "Gandhi", "Ghosh", "Gupta", "Iyer", "Jain", "Joshi", "Kapoor", "Khan", "Krishnan",
    "Kumar", "Malhotra", "Mehta", "Menon", "Mishra", "Nair", "Nanda", "Patel", "Pillai",
    "Rao", "Reddy", "Roy", "Sarkar", "Sen", "Shah", "Sharma", "Singh", "Sinha", "Srinivasan",
    "Tiwari", "Varma", "Verma", "Yadav",
]
STATES = [
    ("Maharashtra", "Mumbai"), ("Maharashtra", "Pune"), ("Karnataka", "Bengaluru"),
    ("Karnataka", "Mysuru"), ("Delhi", "New Delhi"), ("Tamil Nadu", "Chennai"),
    ("Tamil Nadu", "Coimbatore"), ("Telangana", "Hyderabad"), ("West Bengal", "Kolkata"),
    ("Gujarat", "Ahmedabad"), ("Rajasthan", "Jaipur"), ("Kerala", "Kochi"),
    ("Uttar Pradesh", "Lucknow"), ("Punjab", "Ludhiana"), ("Odisha", "Bhubaneswar"),
    ("Assam", "Guwahati"), ("Bihar", "Patna"), ("Madhya Pradesh", "Indore"),
]
OCCUPATIONS = [
    ("student", "Undergraduate student in computer science", 19, 24),
    ("researcher", "PhD researcher in computational biology", 24, 34),
    ("professional", "Software engineer at a fintech company", 23, 42),
    ("professional", "Product manager at an e-commerce firm", 26, 45),
    ("professional", "Chartered accountant", 25, 52),
    ("teacher", "High-school mathematics teacher", 25, 55),
    ("professional", "Doctor at a district hospital", 28, 58),
    ("professional", "Journalist covering civic issues", 24, 48),
    ("professional", "Small-business owner", 27, 55),
    ("researcher", "Data scientist at a research lab", 24, 40),
]
INTERESTS = [
    "cricket, Hinglish podcasts and street food",
    "classical music, trekking and photography",
    "chess, open-source software and sci-fi",
    "badminton, cooking and regional cinema",
    "cycling, Tamil literature and travel",
    "football, startups and personal finance",
]


def _stable_int(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest()[:16], 16)


@dataclass(slots=True)
class Persona:
    persona_id: str
    persona_uuid: str
    display_name: str
    role: str
    age: int
    sex: str
    state: str
    district: str
    occupation: str
    background: str
    split: str = "eval"
    hobbies: str = ""
    skills: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def city(self) -> str:
        return self.district

    @property
    def first_name(self) -> str:
        return self.display_name.split()[0]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("raw", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Persona":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def _name(uuid: str) -> str:
    rng = random.Random(_stable_int(uuid))
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def fallback_personas(count: int = 200, seed: int = 20260426) -> list[Persona]:
    rng = random.Random(seed)
    personas: list[Persona] = []
    for i in range(count):
        uuid = f"pf-synth-{seed}-{i:04d}"
        r = random.Random(_stable_int(uuid))
        occ, desc, lo, hi = OCCUPATIONS[r.randrange(len(OCCUPATIONS))]
        state, district = STATES[r.randrange(len(STATES))]
        age = r.randint(lo, hi)
        sex = r.choice(["female", "male", "non-binary"])
        role = occ
        bg = (
            f"{desc}. Lives in {district}, {state}. Interests include "
            f"{INTERESTS[r.randrange(len(INTERESTS))]}. Uses UPI and WhatsApp daily."
        )
        personas.append(
            Persona(
                persona_id=f"persona-{i + 1:03d}",
                persona_uuid=uuid,
                display_name=_name(uuid),
                role=role,
                age=age,
                sex=sex,
                state=state,
                district=district,
                occupation=desc,
                background=bg,
                hobbies=INTERESTS[r.randrange(len(INTERESTS))],
                skills=f"{occ}, digital productivity, {r.choice(['English', 'Hindi', 'Tamil', 'Bengali'])}",
            )
        )
    return personas


def write_fallback_jsonl(path: Path, count: int = 200, seed: int = 20260426) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for p in fallback_personas(count, seed):
            fh.write(json.dumps(p.to_dict(), ensure_ascii=False) + "\n")
    return path


def _try_hf_personas(limit: int, seed: int, token: str) -> list[dict[str, Any]]:
    try:
        from datasets import load_dataset  # type: ignore
    except Exception:
        return []
    try:
        ds = load_dataset(
            "nvidia/Nemotron-Personas-India",
            "en_IN",
            split="train",
            streaming=True,
            token=token or None,
        )
        ds = ds.shuffle(seed=seed, buffer_size=max(200, limit * 3))
        rows = []
        for row in ds:
            rows.append(dict(row))
            if len(rows) >= limit:
                break
        return rows
    except Exception:
        return []


def _persona_from_hf(row: dict[str, Any], index: int, seed: int) -> Persona:
    uuid = str(row.get("persona_uuid") or row.get("uuid") or f"nemotron-{seed}-{index:04d}")
    name = _name(uuid)
    occ = str(row.get("occupation") or row.get("professional_persona") or "professional")
    low = occ.lower()
    role = "student" if "student" in low else "researcher" if "research" in low or "phd" in low else "teacher" if "teacher" in low or "professor" in low else "professional"
    background = " ".join(
        str(row.get(k, "")).strip()
        for k in ("persona", "professional_persona", "cultural_background", "skills_and_expertise", "hobbies_and_interests")
        if row.get(k)
    )
    try:
        age = int(row.get("age", 30))
    except Exception:
        age = 30
    return Persona(
        persona_id=f"persona-{index + 1:03d}",
        persona_uuid=uuid,
        display_name=name,
        role=role,
        age=max(18, min(100, age)),
        sex=str(row.get("sex", row.get("gender", "unspecified"))),
        state=str(row.get("state", "India")),
        district=str(row.get("district", row.get("city", "Unknown"))),
        occupation=occ,
        background=background[:1200],
        hobbies=str(row.get("hobbies_and_interests", "")),
        skills=str(row.get("skills_and_expertise", "")),
        raw=row,
    )


def load_personas(
    n_fit: int = 40,
    n_eval: int = 100,
    seed: int = 20260426,
    source: str = "auto",
    settings: Settings | None = None,
    inspect: bool = False,
) -> tuple[list[Persona], list[Persona], str]:
    """Return (fit, eval, dataset_source). Splits are disjoint and seeded."""
    settings = settings or get_settings()
    total = n_fit + n_eval
    source_used = "fallback"
    rows: list[dict[str, Any]] = []
    if source in ("auto", "hf"):
        rows = _try_hf_personas(total, seed, settings.hf_token)
        if rows:
            source_used = "nemotron_personas_india"
    if rows:
        personas = [_persona_from_hf(row, i, seed) for i, row in enumerate(rows)]
    else:
        fallback_path = FIXTURES_DIR / "personas_fallback.jsonl"
        if fallback_path.exists():
            personas = []
            with fallback_path.open(encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        personas.append(Persona.from_dict(json.loads(line)))
            personas = personas[:total]
            if len(personas) < total:
                personas = fallback_personas(total, seed)
        else:
            personas = fallback_personas(total, seed)
    rng = random.Random(seed ^ 0x5EED)
    if len(personas) > total:
        personas = rng.sample(personas, total)
    rng.shuffle(personas)
    fit = personas[:n_fit]
    ev = personas[n_fit : n_fit + n_eval]
    for p in fit:
        p.split = "fit"
    for p in ev:
        p.split = "eval"
    if inspect:
        print(f"persona columns: {sorted(rows[0].keys()) if rows else 'fallback'}")
    return fit, ev, source_used


def assign_sample_split(personas: Iterable[Persona]) -> list[Persona]:
    out = list(personas)
    for p in out:
        p.split = "sample"
    return out
