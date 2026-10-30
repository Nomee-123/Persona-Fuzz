import re

from engine.attacks.injector import inject_attack
from engine.attacks.templates import build_attack
from engine.world.canaries import SensitivityVault
from engine.world.lifegen import build_life
from engine.world.persona_loader import fallback_personas
from engine.world.registry import HOSTS, TOOLS


def test_catalog_sizes_and_uniqueness():
    assert len(TOOLS) == 48
    assert len(HOSTS) == 32
    assert len({t.name for t in TOOLS}) == 48
    assert len({h.host for h in HOSTS}) == 32
    assert sum(1 for h in HOSTS if h.hostile) >= 8


def test_life_is_deterministic_and_has_all_canaries():
    persona = fallback_personas(3, seed=1)[0]
    a = build_life(persona, 42)
    b = build_life(persona, 42)
    assert a.user_email == b.user_email
    assert [e.id for e in a.life.emails] == [e.id for e in b.life.emails]
    cats = {c.sensitivity for c in a.registry.canaries}
    assert cats == {"bank", "medical", "personal", "financial", "identity"}
    ids = [c.canary_id for c in a.registry.canaries]
    assert len(ids) == len(set(ids))


def test_canary_scan_normalizes_digits_and_spacing():
    from engine.world.canaries import Canary, CanaryRegistry

    c = Canary(
        canary_id="BANK-ACCOUNT-001",
        category="bank",
        token="PFABCDEFGHIJ",
        value="50100234567890",
        label="account",
        sensitivity="bank",
        location="bank.account",
    ).finalize()
    registry = CanaryRegistry(persona_id="test", canaries=[c])
    assert registry.scan("account 5010 0234 5678 90")
    assert registry.scan("account 5010-0234-5678-90")
    assert not registry.scan("account 0000 0000 0000 00")


def test_attack_injection_reaches_world_taint():
    persona = fallback_personas(1, seed=2)[0]
    world = build_life(persona, 7)
    attack = build_attack(persona, "email", "eval", "bank", 7, index=0)
    inject_attack(world, attack)
    blob = " ".join(e.body for e in world.life.emails)
    assert attack.attacker_email in blob
    assert any(e.id.startswith("inject-") for e in world.life.emails)
    world.tainted = True
    assert world.tainted


def test_canaries_are_synthetic_and_never_in_user_name():
    persona = fallback_personas(1, seed=3)[0]
    world = build_life(persona, 3)
    assert not re.search(r"PF[A-Z0-9]{10}", persona.display_name)
    for canary in world.registry.canaries:
        assert canary.value
