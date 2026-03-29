"""Agent package: prompt definitions, intent taxonomy, profile builder, session manager, and core loop."""

from kara_api.agent.loop import AgentError, AgentLoop, AgentResponse, ToolCallRecord
from kara_api.agent.profile_builder import ProfileBuilder
from kara_api.agent.session import SessionManager
from kara_api.agent.prompts import (
    ALL_SLOTS,
    ENHANCED_SYSTEM_PROMPT,
    INTENT_SPECS,
    Intent,
    IntentSpec,
    SlotDefinition,
    get_intent_spec,
    get_required_slots,
    get_slot_definition,
)

__all__ = [
    "ALL_SLOTS",
    "AgentError",
    "AgentLoop",
    "AgentResponse",
    "ENHANCED_SYSTEM_PROMPT",
    "INTENT_SPECS",
    "Intent",
    "IntentSpec",
    "ProfileBuilder",
    "SessionManager",
    "SlotDefinition",
    "ToolCallRecord",
    "get_intent_spec",
    "get_required_slots",
    "get_slot_definition",
]
