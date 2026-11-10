"""The agent loop (pure generators), client-tool dispatch, and the embedded facade."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from flow_harness.agent.agent import Agent

__all__ = ["Agent"]


# lazy: an eager import here would cycle (agent.py -> session.py -> agent.loop -> here)
def __getattr__(name: str):
	if name == "Agent":
		from flow_harness.agent.agent import Agent

		return Agent
	raise AttributeError(name)
