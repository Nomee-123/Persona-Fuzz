from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .canaries import CanaryRegistry, SensitivityVault
from .persona_loader import Persona


@dataclass(slots=True)
class Email:
    id: str
    sender: str
    to: list[str]
    subject: str
    body: str
    received: str
    unread: bool = True
    external: bool = False
    folder: str = "inbox"
    labels: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Event:
    id: str
    title: str
    start: str
    end: str
    attendees: list[str] = field(default_factory=list)
    description: str = ""
    organizer: str = ""
    external: bool = False


@dataclass(slots=True)
class Note:
    id: str
    title: str
    body: str
    created: str
    sensitivity: str = "private"


@dataclass(slots=True)
class File:
    id: str
    path: str
    content: str
    sensitivity: str = "private"


@dataclass(slots=True)
class Contact:
    name: str
    email: str
    phone: str
    trusted: bool = True
    group: str = ""


@dataclass(slots=True)
class ChatMessage:
    sender: str
    body: str
    ts: str


@dataclass(slots=True)
class ChatThread:
    id: str
    name: str
    contact: str
    messages: list[ChatMessage] = field(default_factory=list)


@dataclass(slots=True)
class Transaction:
    id: str
    date: str
    description: str
    amount: float
    direction: str


@dataclass(slots=True)
class Life:
    persona_id: str
    user_email: str
    user_phone: str
    city: str
    emails: list[Email] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    files: list[File] = field(default_factory=list)
    contacts: list[Contact] = field(default_factory=list)
    chats: list[ChatThread] = field(default_factory=list)
    transactions: list[Transaction] = field(default_factory=list)
    apps: list[str] = field(default_factory=list)
    reminders: list[dict[str, str]] = field(default_factory=list)
    bank: dict[str, Any] = field(default_factory=dict)
    clipboard: str = ""
    weather: dict[str, str] = field(default_factory=dict)
    headlines: list[str] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        return {
            "inbox_count": len(self.emails),
            "calendar_count": len(self.events),
            "notes_count": len(self.notes),
            "apps_count": len(self.apps),
            "contacts_count": len(self.contacts),
            "files_count": len(self.files),
            "chat_count": len(self.chats),
        }


@dataclass(slots=True)
class World:
    persona: Persona
    life: Life
    registry: CanaryRegistry
    vault: SensitivityVault
    now: str
    hostile_log: list[dict[str, Any]] = field(default_factory=list)
    web_pages: dict[str, dict[str, str]] = field(default_factory=dict)
    changes: list[dict[str, Any]] = field(default_factory=list)
    tainted: bool = False
    taint_sources: list[str] = field(default_factory=list)
    injected: dict[str, Any] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)
    initial_email_ids: set[str] = field(default_factory=set)
    initial_event_ids: set[str] = field(default_factory=set)
    initial_note_ids: set[str] = field(default_factory=set)

    @property
    def user_email(self) -> str:
        return self.life.user_email

    @property
    def trusted_contacts(self) -> list[Contact]:
        return [c for c in self.life.contacts if c.trusted]

    @property
    def trusted_emails(self) -> set[str]:
        return {c.email.lower() for c in self.trusted_contacts} | {self.user_email.lower()}

    def mark_untrusted(self, source: str) -> None:
        self.tainted = True
        if source not in self.taint_sources:
            self.taint_sources.append(source)

    def record(self, tool: str, args: dict[str, Any], result: Any = None, egress: bool = False) -> None:
        self.counters[tool] = self.counters.get(tool, 0) + 1
        self.changes.append(
            {"tool": tool, "args": args, "result": result if isinstance(result, (str, int, float, bool, type(None))) else None, "egress": egress}
        )

    def internal_recipient(self, recipient: str) -> bool:
        value = (recipient or "").lower()
        if not value:
            return True
        if value == self.user_email.lower():
            return True
        return value in self.trusted_emails
