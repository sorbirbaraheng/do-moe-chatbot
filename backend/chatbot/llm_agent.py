"""
🤖 LLM Agent – Facade
Backward-compatible entry point that composes all mixin modules.

Usage:
    from .llm_agent import LLMAgent
    agent = LLMAgent(qdrant_client, llm)
    response, active = agent.process_query(question, context)
"""

from .agent import (
    AgentBase,
    EntityExtractorMixin,
    FollowUpMixin,
    ToolSelectorMixin,
    ResponseGeneratorMixin,
    WidgetMixin,
)


class LLMAgent(
    ToolSelectorMixin,      # tool selection, routing, enrichment, keyword fallback
    EntityExtractorMixin,   # regex-based entity extraction
    FollowUpMixin,          # follow-up context handling, multi-step plans
    ResponseGeneratorMixin, # LLM response generation + fallback formatting
    WidgetMixin,            # UI widgets (map, chart) + suggestions
    AgentBase,              # __init__, process_query orchestrator (base last)
):
    """
    Facade class: inherits all functionality from agent/ mixins.
    MRO ensures ToolSelectorMixin (which calls entity/followup methods) resolves first,
    then helpers, then AgentBase last as the true base.
    """
    pass
