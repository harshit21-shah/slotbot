"""
LangGraph conversation state machine for SlotBot.

Graph flow:
  START
    └─ greeting ─────────────────────────────────────────┐
         └─ collect_name ──► (retry or)                  │
               └─ collect_reason ──► (retry or)          │
                     └─ collect_datetime ──► (retry or)  │
                           └─ check_availability          │
                                 ├─ offer_alternatives ◄─┤
                                 └─ confirm_slot          │
                                       └─ booking         │
                                             └─ send_confirmation
                                                   └─ goodbye ──► END
  Any state ──► emergency_escalate ──► END
  Any state ──► human_escalate ──► END
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from services.agents.state_types import SlotBotState
from services.agents.states.booking import booking_node
from services.agents.states.check_availability import check_availability_node
from services.agents.states.clarify import clarify_node
from services.agents.states.collect_datetime import collect_datetime_node
from services.agents.states.collect_name import collect_name_node
from services.agents.states.collect_reason import collect_reason_node
from services.agents.states.confirm_slot import confirm_slot_node
from services.agents.states.emergency_escalate import emergency_escalate_node
from services.agents.states.goodbye import goodbye_node
from services.agents.states.greeting import greeting_node
from services.agents.states.human_escalate import human_escalate_node
from services.agents.states.offer_alternatives import offer_alternatives_node
from services.agents.states.send_confirmation import send_confirmation_node

# ── Routing functions ─────────────────────────────────────────────────────────

_MAX_CLARIFICATIONS = 2


def _should_escalate(state: SlotBotState) -> bool:
    return state.get("needs_human", False) or state.get("clarification_attempts", 0) >= _MAX_CLARIFICATIONS


def route_after_greeting(state: SlotBotState) -> str:
    if state.get("is_emergency"):
        return "emergency_escalate"
    return "collect_name"


def route_after_collect_name(state: SlotBotState) -> str:
    if state.get("is_emergency"):
        return "emergency_escalate"
    if _should_escalate(state):
        return "human_escalate"
    if state.get("collected_name"):
        return "collect_reason"
    return "collect_name"  # retry


def route_after_collect_reason(state: SlotBotState) -> str:
    if state.get("is_emergency"):
        return "emergency_escalate"
    if _should_escalate(state):
        return "human_escalate"
    if state.get("collected_reason"):
        return "collect_datetime"
    return "collect_reason"  # retry


def route_after_collect_datetime(state: SlotBotState) -> str:
    if state.get("is_emergency"):
        return "emergency_escalate"
    if _should_escalate(state):
        return "human_escalate"
    has_date_or_flexible = state.get("collected_date") or state.get("time_is_flexible")
    if has_date_or_flexible:
        return "check_availability"
    return "collect_datetime"  # retry


def route_after_check_availability(state: SlotBotState) -> str:
    if state.get("needs_human"):
        return "human_escalate"
    slots = state.get("available_slots", [])
    if not slots:
        return "collect_datetime"  # no slots on this date — ask for different date
    requested_time = state.get("collected_time")
    if requested_time and requested_time in slots:
        return "confirm_slot"  # exact match
    return "offer_alternatives"  # show alternatives


def route_after_offer_alternatives(state: SlotBotState) -> str:
    if state.get("is_emergency"):
        return "emergency_escalate"
    # Patient wants a completely different time
    if not state.get("collected_date") and not state.get("time_is_flexible"):
        return "collect_datetime"
    if state.get("confirmed_slot_datetime"):
        return "confirm_slot"
    return "offer_alternatives"  # re-present options


def route_after_confirm_slot(state: SlotBotState) -> str:
    if state.get("is_emergency"):
        return "emergency_escalate"
    confirmed = state.get("confirmed_slot_datetime")
    if confirmed:
        return "booking"
    # If patient rejected, check if date/time was reset
    if not state.get("collected_date"):
        return "collect_datetime"
    return "confirm_slot"  # re-ask for confirmation


def route_after_booking(state: SlotBotState) -> str:
    if state.get("needs_human"):
        return "human_escalate"
    # Slot was taken between confirm and book — offer new alternatives
    if state.get("available_slots") and not state.get("booking_id"):
        return "offer_alternatives"
    if state.get("booking_id"):
        return "send_confirmation"
    return "human_escalate"


def route_after_send_confirmation(state: SlotBotState) -> str:
    if state.get("call_ended"):
        return END  # type: ignore[return-value]
    return "goodbye"


# ── Graph assembly ─────────────────────────────────────────────────────────────

def build_graph() -> CompiledStateGraph:
    graph: StateGraph = StateGraph(SlotBotState)

    # Nodes
    graph.add_node("greeting", greeting_node)
    graph.add_node("collect_name", collect_name_node)
    graph.add_node("collect_reason", collect_reason_node)
    graph.add_node("collect_datetime", collect_datetime_node)
    graph.add_node("check_availability", check_availability_node)
    graph.add_node("offer_alternatives", offer_alternatives_node)
    graph.add_node("confirm_slot", confirm_slot_node)
    graph.add_node("booking", booking_node)
    graph.add_node("send_confirmation", send_confirmation_node)
    graph.add_node("goodbye", goodbye_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("emergency_escalate", emergency_escalate_node)
    graph.add_node("human_escalate", human_escalate_node)

    # Entry
    graph.add_edge(START, "greeting")

    # Conditional routing
    graph.add_conditional_edges(
        "greeting",
        route_after_greeting,
        {"collect_name": "collect_name", "emergency_escalate": "emergency_escalate"},
    )
    graph.add_conditional_edges(
        "collect_name",
        route_after_collect_name,
        {
            "collect_name": "collect_name",
            "collect_reason": "collect_reason",
            "human_escalate": "human_escalate",
            "emergency_escalate": "emergency_escalate",
        },
    )
    graph.add_conditional_edges(
        "collect_reason",
        route_after_collect_reason,
        {
            "collect_reason": "collect_reason",
            "collect_datetime": "collect_datetime",
            "human_escalate": "human_escalate",
            "emergency_escalate": "emergency_escalate",
        },
    )
    graph.add_conditional_edges(
        "collect_datetime",
        route_after_collect_datetime,
        {
            "collect_datetime": "collect_datetime",
            "check_availability": "check_availability",
            "human_escalate": "human_escalate",
            "emergency_escalate": "emergency_escalate",
        },
    )
    graph.add_conditional_edges(
        "check_availability",
        route_after_check_availability,
        {
            "confirm_slot": "confirm_slot",
            "offer_alternatives": "offer_alternatives",
            "collect_datetime": "collect_datetime",
            "human_escalate": "human_escalate",
        },
    )
    graph.add_conditional_edges(
        "offer_alternatives",
        route_after_offer_alternatives,
        {
            "collect_datetime": "collect_datetime",
            "confirm_slot": "confirm_slot",
            "offer_alternatives": "offer_alternatives",
            "emergency_escalate": "emergency_escalate",
        },
    )
    graph.add_conditional_edges(
        "confirm_slot",
        route_after_confirm_slot,
        {
            "booking": "booking",
            "collect_datetime": "collect_datetime",
            "confirm_slot": "confirm_slot",
            "emergency_escalate": "emergency_escalate",
        },
    )
    graph.add_conditional_edges(
        "booking",
        route_after_booking,
        {
            "send_confirmation": "send_confirmation",
            "offer_alternatives": "offer_alternatives",
            "human_escalate": "human_escalate",
        },
    )
    graph.add_conditional_edges(
        "send_confirmation",
        route_after_send_confirmation,
        {"goodbye": "goodbye", END: END},
    )

    # Terminal nodes
    graph.add_edge("goodbye", END)
    graph.add_edge("emergency_escalate", END)
    graph.add_edge("human_escalate", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


# Module-level singleton — compiled once at import
conversation_graph: CompiledStateGraph = build_graph()
