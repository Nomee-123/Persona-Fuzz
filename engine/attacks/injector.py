from __future__ import annotations

from datetime import datetime, timedelta

from ..world.state import Email, Event, World
from .templates import AttackSpec


def inject_attack(world: World, attack: AttackSpec) -> None:
    world.injected = {
        "vector": attack.vector,
        "goal": attack.goal,
        "template_id": attack.template_id,
        "target_category": attack.target_category,
        "attacker_email": attack.attacker_email,
        "attacker_host": attack.attacker_host,
        "text": attack.text,
    }
    if attack.vector == "email":
        email = Email(
            id=f"inject-{attack.template_id.lower()}",
            sender=attack.attacker_email,
            to=[world.user_email],
            subject="Account verification required" if attack.goal != "destructive" else "Urgent security cleanup",
            body=attack.text,
            received=world.now,
            unread=True,
            external=True,
            labels=["external"],
        )
        world.life.emails.insert(0, email)
    elif attack.vector == "calendar":
        try:
            base = datetime.fromisoformat(world.now)
        except Exception:
            base = datetime(2026, 10, 30, 9, 0)
        start = (base + timedelta(days=1, hours=1)).replace(minute=0, second=0, microsecond=0)
        event = Event(
            id=f"inject-{attack.template_id.lower()}",
            title="External account verification",
            start=start.isoformat(timespec="minutes"),
            end=(start + timedelta(hours=1)).isoformat(timespec="minutes"),
            attendees=[world.user_email],
            description=attack.text,
            organizer=attack.attacker_email,
            external=True,
        )
        world.life.events.insert(0, event)
    elif attack.vector == "web":
        url = f"https://{attack.attacker_host}/verify"
        world.web_pages[attack.attacker_host] = {
            "title": "Account verification required",
            "body": attack.text,
        }
        world.web_pages["news.google.com"] = {
            "title": "Top headlines",
            "body": "Top headlines page. " + " ".join(world.life.headlines),
        }
        world.injected["search_result"] = {
            "title": "Account verification required — act now",
            "url": url,
            "snippet": attack.text,
        }
    world.changes.append({"tool": "attack.inject", "args": {"vector": attack.vector, "template": attack.template_id}, "result": None, "egress": False})
