from __future__ import annotations

from ..agent.tasks import TaskSpec, check_utility
from ..world.state import World


def utility_ok(world: World, task: TaskSpec) -> tuple[bool, str]:
    return check_utility(world, task)
