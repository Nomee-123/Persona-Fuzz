from __future__ import annotations

import asyncio
import hashlib
import json
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..agent.loop import AgentLoop
from ..agent.tasks import build_task
from ..agent.trace import Episode
from ..attacks.adaptive import AdaptiveAttacker
from ..attacks.injector import inject_attack
from ..attacks.templates import AttackSpec, build_attack
from ..config import CANARY_CATEGORIES, TASK_CLASSES, get_settings
from ..contracts import validate_episode, validate_summary
from ..defense.compile_openshell import compile_openshell
from ..defense.d2_llm_policy import generate_policy
from ..defense.d3_trace import TraceCall, fit_trace_policy
from ..defense.d4_cegis import run_cegis, write_policy_bundle
from ..defense.engine import PolicyEnforcer
from ..defense.policy_ir import Policy, union_policies
from ..llm.client import LLMError, TokenFactoryClient, estimate_usd
from ..metrics.summarize import build_summary
from ..world.lifegen import build_life
from ..world.persona_loader import Persona, load_personas
from ..world.registry import TOOLS
from ..world.state import World

VECTOR_TASK = {"email": "inbox", "calendar": "schedule", "web": "research"}
VECTORS = ["email", "calendar", "web"]


@dataclass(slots=True)
class RunConfig:
    run_id: str
    quick: bool = False
    full: bool = False
    seed: int = 20260426
    models: list[str] = field(default_factory=list)
    executor: str = "local"
    shards: int = 1
    shard_id: int = 0
    max_episodes: int = 0
    max_usd: float = 25.0
    conditions: list[str] = field(default_factory=lambda: ["D0", "D1", "D2", "D3", "D4"])
    synthetic_fixture: bool | None = None
    no_adaptive: bool = False
    extended: bool = True
    offline: bool = False


class EpisodeStore:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.path = run_dir / "episodes.jsonl"
        self.events_path = run_dir / "events.jsonl"
        self.episodes: list[Episode] = []
        self.ids: set[str] = set()
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    ep = Episode.model_validate(json.loads(line))
                    self.episodes.append(ep)
                    self.ids.add(ep.episode_id)
                except Exception:
                    continue

    def has(self, episode_id: str) -> bool:
        return episode_id in self.ids

    def add(self, episode: Episode) -> None:
        if episode.episode_id in self.ids:
            return
        self.ids.add(episode.episode_id)
        self.episodes.append(episode)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(episode.model_dump(), ensure_ascii=False) + "\n")
        self.event("episode", {"episode_id": episode.episode_id, "condition": episode.condition, "leak": episode.outcome.leak.detected, "utility": episode.outcome.utility_ok})

    def event(self, kind: str, data: dict[str, Any]) -> None:
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"type": kind, "data": data, "ts": datetime.now(timezone.utc).isoformat()}) + "\n")


class OfflineProvider:
    def __init__(self):
        self.model = "offline/mock-nemotron"
        self.tool_mode = "react"

    def backend(self, attack: bool = False):
        from ..llm.mock_backend import MockBackend

        return MockBackend("gullible" if attack else "careful", model=self.model)


class LiveProvider:
    def __init__(self, client: TokenFactoryClient, model: str, tool_mode: str, attacker_model: str = ""):
        self.client = client
        self.model = model
        self.tool_mode = tool_mode
        self.attacker_model = attacker_model or model

    def backend(self, attack: bool = False):
        return self.client


def make_run_id() -> str:
    return "pl-" + datetime.now().strftime("%Y%m%d-%H%M%S")


def _persona_hash(persona: Persona) -> int:
    return int(hashlib.sha256(persona.persona_uuid.encode()).hexdigest()[:8], 16)


class RunEngine:
    def __init__(self, config: RunConfig, quiet: bool = False):
        self.cfg = config
        self.settings = get_settings()
        self.quiet = quiet
        self.run_dir = Path(self.settings.runs_dir) / config.run_id
        self.store = EpisodeStore(self.run_dir)
        self.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.provider: OfflineProvider | LiveProvider | None = None
        self.client: TokenFactoryClient | None = None
        self.synthetic = False
        self.dataset_source = "fallback"
        self.notes: list[str] = []
        self.models: list[str] = []
        self.curve: list[dict[str, Any]] = []
        self.policies: dict[str, Policy] = {}
        self.union: Policy | None = None
        self.open_yaml = ""
        self.example_trace_ids: dict[str, str] = {}
        self.per_model: list[dict[str, Any]] = []
        self.episode_count = 0
        self.start_time = time.perf_counter()

    def log(self, message: str) -> None:
        if not self.quiet:
            print(f"[{self.cfg.run_id}] {message}", flush=True)

    async def setup(self) -> None:
        self.log("checking compute and model")
        if self.settings.has_key and not self.cfg.offline:
            self.client = TokenFactoryClient(self.settings, cache_path=self.run_dir / "llm_cache.sqlite")
            chosen, nemotrons = await self.client.discover()
            mode = await self.client.probe_tool_mode(chosen)
            attacker = self.settings.attacker_model
            if not attacker:
                others = [m.id for m in nemotrons if m.id != chosen]
                attacker = others[0] if others else chosen
            self.models = [m.id for m in nemotrons]
            self.provider = LiveProvider(self.client, chosen, mode, attacker)
            self.synthetic = False
            self.notes.append(f"Live Token Factory run. Agent model {chosen}; tool mode {mode}; attacker {attacker}.")
        else:
            self.provider = OfflineProvider()
            self.synthetic = True
            self.notes.append("No NEBIUS_API_KEY: ran the deterministic offline mock. All results are flagged synthetic_fixture and are not live-model claims.")
        assert self.provider is not None
        if self.cfg.synthetic_fixture is not None:
            self.synthetic = self.cfg.synthetic_fixture

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()

    def _enforcer(self, condition: str) -> PolicyEnforcer | None:
        if condition in ("D0", "D1"):
            return None
        policy = self.policies.get("union") if condition == "D4" else None
        # Policies are per task class; the enforcer is built at call time.
        return None

    def _policy_for(self, task_class: str) -> Policy:
        return self.policies.get(task_class) or union_policies(list(self.policies.values()))

    def _enforcer_for(self, condition: str, task_class: str) -> PolicyEnforcer | None:
        if condition in ("D0", "D1"):
            return None
        policy = self._policy_for(task_class)
        if condition == "D2":
            return PolicyEnforcer(policy, dlp_enabled=False, flow_enabled=True)
        if condition == "D3":
            return PolicyEnforcer(policy, dlp_enabled=False, flow_enabled=False)
        return PolicyEnforcer(policy, dlp_enabled=True, flow_enabled=True)

    async def _run_episode(
        self,
        persona: Persona,
        task_class: str,
        condition: str,
        episode_id: str,
        split: str,
        attack: AttackSpec | None = None,
        adaptive_round: int | None = None,
    ) -> Episode:
        if self.store.has(episode_id):
            return next(e for e in self.store.episodes if e.episode_id == episode_id)
        if self.cfg.max_episodes and len(self.store.episodes) >= self.cfg.max_episodes:
            raise RuntimeError(f"max_episodes cap reached ({self.cfg.max_episodes})")
        if self.cfg.max_usd and estimate_usd(sum(e.tokens for e in self.store.episodes)) > self.cfg.max_usd:
            raise RuntimeError("max_usd cap reached")
        world = build_life(persona, self.cfg.seed)
        task = build_task(persona, task_class, world)
        attack_trace = None
        if attack is not None:
            inject_attack(world, attack)
            attack_trace = attack.trace()
            if adaptive_round is not None:
                attack_trace.adaptive_round = adaptive_round
        provider = self.provider
        assert provider is not None
        backend = provider.backend(attack=attack is not None)
        enforcer = self._enforcer_for(condition, task_class)
        loop = AgentLoop(
            backend,
            model=provider.model,
            tool_mode=provider.tool_mode,
            max_steps=self.settings.max_steps,
            seed=self.cfg.seed,
        )
        result = await loop.run(
            world,
            task,
            condition,
            self.cfg.run_id,
            episode_id,
            split=split,
            attack=attack_trace,
            enforcer=enforcer,
            enforcement="gateway",
            synthetic_fixture=self.synthetic,
        )
        episode = result.episode
        validate_episode(episode.model_dump())
        self.store.add(episode)
        self.episode_count += 1
        if self.episode_count % 10 == 0:
            self.log(f"{self.episode_count} episodes, {len(self.store.episodes)} stored")
        return episode

    def _shard_ok(self, persona: Persona) -> bool:
        if self.cfg.executor == "local" or self.cfg.shards <= 1:
            return True
        return _persona_hash(persona) % self.cfg.shards == self.cfg.shard_id

    async def _fit_benign(self, fit: list[Persona]) -> tuple[dict[str, list[list[TraceCall]]], float]:
        observations: dict[str, list[list[TraceCall]]] = {t: [] for t in TASK_CLASSES}
        ok = 0
        total = 0
        for persona in fit:
            if not self._shard_ok(persona):
                continue
            for task_class in TASK_CLASSES:
                ep = await self._run_episode(
                    persona, task_class, "D0", f"fit-benign-{persona.persona_id}-{task_class}", "fit"
                )
                total += 1
                ok += int(ep.outcome.utility_ok)
                if ep.outcome.utility_ok:
                    fit_world = build_life(persona, self.cfg.seed)
                    calls = [
                        TraceCall(
                            name=step.tool_call.name,
                            args=dict(step.tool_call.args),
                            trusted_emails=set(fit_world.trusted_emails),
                            user_email=fit_world.user_email,
                        )
                        for step in ep.steps
                        if step.tool_call is not None
                    ]
                    observations[task_class].append(calls)
        return observations, (ok / total if total else 0.0)

    async def _benign_suite(self, personas: list[Persona], condition: str, prefix: str, split: str) -> list[Episode]:
        rows = []
        for i, persona in enumerate(personas):
            if not self._shard_ok(persona):
                continue
            task_class = TASK_CLASSES[i % len(TASK_CLASSES)]
            ep = await self._run_episode(persona, task_class, condition, f"{prefix}-{condition}-{persona.persona_id}", split)
            rows.append(ep)
        return rows

    def _attack_for(self, persona: Persona, vector: str, attack_split: str, index: int, category: str | None = None) -> AttackSpec:
        cat = category or CANARY_CATEGORIES[index % len(CANARY_CATEGORIES)]
        task_class = VECTOR_TASK[vector]
        return build_attack(persona, vector, attack_split, cat, self.cfg.seed, index=index, goal=None)

    async def _attack_suite(
        self,
        personas: list[Persona],
        condition: str,
        attack_split: str,
        prefix: str,
        split: str,
        templates_per_vector: int = 1,
        vectors: list[str] | None = None,
    ) -> list[Episode]:
        rows = []
        idx = 0
        for p_i, persona in enumerate(personas):
            if not self._shard_ok(persona):
                continue
            for v_i, vector in enumerate(vectors or VECTORS):
                for t in range(templates_per_vector):
                    category = CANARY_CATEGORIES[(p_i + v_i + t) % len(CANARY_CATEGORIES)]
                    attack = self._attack_for(persona, vector, attack_split, idx + t, category)
                    task_class = VECTOR_TASK[vector]
                    ep = await self._run_episode(
                        persona,
                        task_class,
                        condition,
                        f"{prefix}-{condition}-{persona.persona_id}-{vector}-{t}",
                        split,
                        attack=attack,
                    )
                    rows.append(ep)
                    idx += 1
        return rows

    async def learn(self, fit: list[Persona], eval_personas: list[Persona]) -> None:
        self.log("fitting D0 benign traces on fit personas")
        observations, baseline_utility = await self._fit_benign(fit)
        self.log(f"baseline fit utility {baseline_utility:.3f}")
        self.log("generating D2 LLM-written policies")
        d2: dict[str, Policy] = {}
        for task_class in TASK_CLASSES:
            task = build_task(fit[0], task_class, build_life(fit[0], self.cfg.seed))
            policy, used_llm, note = await generate_policy(
                task, self.client if isinstance(self.provider, LiveProvider) else None, self.provider.model
            )
            d2[task_class] = policy
            self.notes.append(f"D2 {task_class}: {note}")
        self.log("deriving D3 trace policies")
        d3 = {
            t: fit_trace_policy(t, observations[t], tau=self.settings.tau, expected_tools=build_task(fit[0], t, build_life(fit[0], self.cfg.seed)).expected_tools | build_task(fit[0], t, build_life(fit[0], self.cfg.seed)).expected_sinks)
            for t in TASK_CLASSES
        }
        self.d2_policies = d2
        self.d3_policies = d3
        self.policies = {**d3}

        calls = {"train": 0, "heldout": 0, "benign": 0}

        async def train_attacks(policies: dict[str, Policy]) -> list[Episode]:
            old = dict(self.policies)
            self.policies = policies
            calls["train"] += 1
            try:
                return await self._attack_suite(fit, "D4", "train", f"cegis-train-{calls['train']}", "fit", 1)
            finally:
                self.policies = old

        async def heldout_attacks(policies: dict[str, Policy]) -> list[Episode]:
            old = dict(self.policies)
            self.policies = policies
            calls["heldout"] += 1
            try:
                sample = eval_personas[: min(len(eval_personas), 20)]
                return await self._attack_suite(sample, "D4", "eval", f"cegis-heldout-{calls['heldout']}", "eval", 1)
            finally:
                self.policies = old

        async def benign_suite(policies: dict[str, Policy]) -> list[Episode]:
            old = dict(self.policies)
            self.policies = policies
            calls["benign"] += 1
            try:
                return await self._benign_suite(fit, "D4", f"cegis-benign-{calls['benign']}", "fit")
            finally:
                self.policies = old

        self.log("running CEGIS")
        # D0 reference point for the convergence chart.
        d0_train = await self._attack_suite(fit, "D0", "train", "cegis-d0-train", "fit", 1)
        d0_held = await self._attack_suite(eval_personas[: min(len(eval_personas), 20)], "D0", "eval", "cegis-d0-held", "eval", 1)
        d0_rate = sum(1 for e in d0_train if e.outcome.leak.detected or e.outcome.unauthorized_action.detected) / len(d0_train) if d0_train else 0.0
        d0_held_rate = sum(1 for e in d0_held if e.outcome.leak.detected or e.outcome.unauthorized_action.detected) / len(d0_held) if d0_held else 0.0
        result = await run_cegis(
            d3,
            benign_tools={t: {c.name for trace in observations[t] for c in trace} for t in TASK_CLASSES},
            baseline_utility=baseline_utility,
            run_train_attacks=train_attacks,
            run_benign=benign_suite,
            run_heldout_attacks=heldout_attacks,
            epsilon=self.settings.epsilon,
            max_iters=self.settings.max_cegis_iters,
        )
        self.policies = result.policies
        self.union = result.union
        self.open_yaml = compile_openshell(self.union)
        self.curve = [
            {
                "iter": 0,
                "train_leak": round(d0_rate, 4),
                "heldout_leak": round(d0_held_rate, 4),
                "utility": round(baseline_utility, 4),
                "policy_bytes": 0,
            }
        ] + [
            {
                **p,
                "iter": p["iter"] + 1,
            }
            for p in result.curve
        ]
        self.write_policy = (result.union, result.tightenings, result.rejected)
        write_policy_bundle(self.run_dir, self.policies, self.union, result.tightenings, result.rejected)
        self.notes.extend(result.rejected)
        self.log(f"CEGIS done: {len(result.tightenings)} tightenings, union tools {len(self.union.allowed_tools)}/{len(TOOLS)}")

    async def evaluate(self, eval_personas: list[Persona]) -> None:
        self.log("running headline battery")
        headline_d0: dict[str, Episode] = {}
        headline_d4: dict[str, Episode] = {}
        for i, persona in enumerate(eval_personas):
            if not self._shard_ok(persona):
                continue
            vector = VECTORS[i % len(VECTORS)]
            category = CANARY_CATEGORIES[i % len(CANARY_CATEGORIES)]
            attack = build_attack(persona, vector, "eval", category, self.cfg.seed, index=i)
            task_class = VECTOR_TASK[vector]
            d0 = await self._run_episode(persona, task_class, "D0", f"headline-{i:03d}-d0", "eval", attack=attack)
            d4 = await self._run_episode(persona, task_class, "D4", f"headline-{i:03d}-d4", "eval", attack=attack)
            headline_d0[persona.persona_id] = d0
            headline_d4[persona.persona_id] = d4
            if "persona_id" not in self.example_trace_ids and d0.outcome.leak.detected and not d4.outcome.leak.detected:
                self.example_trace_ids = {
                    "persona_id": persona.persona_id,
                    "episode_id": d0.episode_id,
                    "d4_episode_id": d4.episode_id,
                }
        if not self.example_trace_ids and headline_d0:
            first = next(iter(headline_d0.values()))
            d4 = headline_d4.get(first.persona_id)
            self.example_trace_ids = {
                "persona_id": first.persona_id,
                "episode_id": first.episode_id,
                "d4_episode_id": d4.episode_id if d4 else "",
            }

        if not self.cfg.no_adaptive and self.cfg.conditions and "D0" in self.cfg.conditions:
            self.log("running adaptive attacker")
            sample = eval_personas[: min(len(eval_personas), 25 if not self.cfg.quick else 10)]
            attacker_backend = self.provider.backend(attack=True) if isinstance(self.provider, LiveProvider) else None
            attacker = AdaptiveAttacker(attacker_backend, self.provider.attacker_model if isinstance(self.provider, LiveProvider) else "")
            for persona in sample:
                if not self._shard_ok(persona):
                    continue
                i = eval_personas.index(persona)
                vector = VECTORS[i % len(VECTORS)]
                category = CANARY_CATEGORIES[i % len(CANARY_CATEGORIES)]
                base = build_attack(persona, vector, "eval", category, self.cfg.seed, index=i)
                for condition in ("D0", "D4"):
                    spec = base
                    last = ""
                    for rnd in range(1, self.settings.adaptive_rounds + 1):
                        if rnd > 1:
                            spec = await attacker.rewrite(spec, build_task(persona, VECTOR_TASK[vector]).text, last, rnd)
                        ep = await self._run_episode(
                            persona,
                            VECTOR_TASK[vector],
                            condition,
                            f"adaptive-{condition}-{persona.persona_id}-{rnd}",
                            "eval",
                            attack=spec,
                            adaptive_round=rnd,
                        )
                        last = ep.steps[-1].tool_result or ep.steps[-1].content if ep.steps else ""
                        if ep.outcome.leak.detected or ep.outcome.unauthorized_action.detected:
                            break

        if self.cfg.extended:
            self.log("running extended battery (all conditions)")
            templates = 2 if self.cfg.full else 1
            for condition in self.cfg.conditions:
                await self._benign_suite(eval_personas, condition, "benign", "eval")
                await self._attack_suite(eval_personas, condition, "eval", "ext", "eval", templates)
                if condition in ("D2", "D3", "D4"):
                    pass

    async def _per_model(self, eval_personas: list[Persona]) -> None:
        if isinstance(self.provider, OfflineProvider) or len(self.models) <= 1 or not self.client:
            self.per_model = [
                {
                    "model": self.provider.model if self.provider else "",
                    "leak_rate_d0": 0.0,
                    "leak_rate_d4": 0.0,
                    "utility_d0": 0.0,
                    "utility_d4": 0.0,
                    "tokens": 0,
                    "latency_ms": 0.0,
                }
            ]
            return
        # Live multi-model comparison uses a 20-persona headline sample to control cost.
        sample = eval_personas[: min(20, len(eval_personas))]
        rows = []
        original = self.provider
        for model in self.models:
            mode = await self.client.probe_tool_mode(model)
            self.provider = LiveProvider(self.client, model, mode)
            d0 = []
            d4 = []
            for i, persona in enumerate(sample):
                vector = VECTORS[i % 3]
                attack = build_attack(persona, vector, "eval", CANARY_CATEGORIES[i % 5], self.cfg.seed, index=i)
                d0.append(await self._run_episode(persona, VECTOR_TASK[vector], "D0", f"model-{model[-8:]}-{persona.persona_id}-d0", "eval", attack=attack))
                d4.append(await self._run_episode(persona, VECTOR_TASK[vector], "D4", f"model-{model[-8:]}-{persona.persona_id}-d4", "eval", attack=attack))
            rows.append(
                {
                    "model": model,
                    "leak_rate_d0": round(sum(1 for e in d0 if e.outcome.leak.detected) / len(d0), 4) if d0 else 0,
                    "leak_rate_d4": round(sum(1 for e in d4 if e.outcome.leak.detected) / len(d4), 4) if d4 else 0,
                    "utility_d0": round(sum(1 for e in d0 if e.outcome.utility_ok) / len(d0), 4) if d0 else 0,
                    "utility_d4": round(sum(1 for e in d4 if e.outcome.utility_ok) / len(d4), 4) if d4 else 0,
                    "tokens": sum(e.tokens for e in d0 + d4),
                    "latency_ms": round(sum(e.latency_ms for e in d0 + d4) / max(1, len(d0 + d4)), 2),
                }
            )
        self.provider = original
        self.per_model = rows

    def _config_dict(self) -> dict[str, Any]:
        assert self.provider is not None
        n_fit = self.settings.quick_fit if self.cfg.quick else self.settings.fit_personas
        n_eval = self.settings.quick_eval if self.cfg.quick else self.settings.eval_personas
        return {
            "dataset": "Nemotron-Personas-India (en_IN)" if self.dataset_source == "nemotron_personas_india" else "Nemotron-Personas-India schema (offline fallback)",
            "n_eval": n_eval,
            "n_fit": n_fit,
            "agent_label": "Persona-Fuzz Agent · Gateway",
            "model": self.provider.model,
            "attack_types": VECTORS,
            "canary_categories": CANARY_CATEGORIES,
            "compute_label": "Offline deterministic mock (fixture)" if isinstance(self.provider, OfflineProvider) else "Nebius Token Factory + local workers",
            "region": self.settings.region or "local",
            "enforcement": "gateway",
        }

    async def run(self) -> dict[str, Any]:
        await self.setup()
        n_fit = self.settings.quick_fit if self.cfg.quick else self.settings.fit_personas
        n_eval = self.settings.quick_eval if self.cfg.quick else self.settings.eval_personas
        self.log(f"loading personas (fit={n_fit}, eval={n_eval})")
        fit, eval_personas, source = load_personas(n_fit=n_fit, n_eval=n_eval, seed=self.cfg.seed)
        self.dataset_source = source
        if source == "fallback":
            self.notes.append("NVIDIA Nemotron-Personas-India was not used; offline fallback personas were used.")
        await self.learn(fit, eval_personas)
        await self.evaluate(eval_personas)
        await self._per_model(eval_personas)
        episodes = self.store.episodes
        if not self.union:
            self.union = union_policies(list(self.policies.values()))
            self.open_yaml = compile_openshell(self.union)
        assert self.provider is not None
        if not self.per_model:
            self.per_model = [{"model": self.provider.model, "leak_rate_d0": 0.0, "leak_rate_d4": 0.0, "utility_d0": 0.0, "utility_d4": 0.0, "tokens": 0, "latency_ms": 0.0}]
        summary = build_summary(
            run_id=self.cfg.run_id,
            config=self._config_dict(),
            episodes=episodes,
            union=self.union,
            policies=self.policies,
            openshell_yaml=self.open_yaml,
            curve=self.curve,
            per_model=self.per_model,
            synthetic_fixture=self.synthetic,
            dataset_source=self.dataset_source,
            started_at=self.started_at,
            finished_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            example_trace_ids=self.example_trace_ids,
            notes=self.notes,
        )
        # Fill per-model headline numbers for the offline/single-model case.
        d0 = [e for e in episodes if e.episode_id.startswith("headline-") and e.condition == "D0"]
        d4 = [e for e in episodes if e.episode_id.startswith("headline-") and e.condition == "D4"]
        if isinstance(self.provider, OfflineProvider) or len(self.per_model) <= 1:
            summary["per_model"] = [
                {
                    "model": self.provider.model,
                    "leak_rate_d0": round(sum(1 for e in d0 if e.outcome.leak.detected) / len(d0), 4) if d0 else 0.0,
                    "leak_rate_d4": round(sum(1 for e in d4 if e.outcome.leak.detected) / len(d4), 4) if d4 else 0.0,
                    "utility_d0": round(sum(1 for e in d0 if e.outcome.utility_ok) / len(d0), 4) if d0 else 0.0,
                    "utility_d4": round(sum(1 for e in d4 if e.outcome.utility_ok) / len(d4), 4) if d4 else 0.0,
                    "tokens": sum(e.tokens for e in episodes),
                    "latency_ms": round(sum(e.latency_ms for e in episodes) / max(1, len(episodes)), 2),
                }
            ]
        summary["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        validate_summary(summary)
        (self.run_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        (self.run_dir / "config.json").write_text(json.dumps(self._config_dict(), indent=2), encoding="utf-8")
        self.store.event("metric", {"summary": {k: summary["metrics"][k] for k in ("total_runs", "leak_rate_before", "leak_rate_after", "improvement")}})
        self.store.event("phase", {"phase": "completed"})
        self.log("summary written")
        return summary


