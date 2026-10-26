"""Bounded recovery for one specific generic model-response loop.

No transcripts are logged and no refused request is automatically retried.
"""

import logging
import re
from collections.abc import Callable

from livekit.agents import Agent, AgentSession, ConversationItemAddedEvent, llm

logger = logging.getLogger("iris.recovery")


def _normalize(text: str) -> str:
    text = text.casefold().replace("\u2019", "'")
    text = text.replace("i'm", "i am").replace("can't", "cannot")
    return " ".join(re.findall(r"[a-z0-9]+", text))


_GENERIC_FAILURE = re.compile(
    r"(?:sorry )?i am (?:just )?(?:a|an) (?:large )?(?:language|ai language) model "
    r"(?:and )?(?:i )?(?:cannot|can not) help (?:you )?with that(?: sir)?"
)


def install_repetition_recovery(
    session: AgentSession, create_agent: Callable[[], Agent]
) -> None:
    """Refresh once after boilerplate replies to two different user turns.

    Gemini Live cannot remove existing messages through update_chat_ctx. A new
    agent/model creates a fresh provider session with the original guardrails.
    The replacement discloses the refresh and waits for a new request instead
    of replaying the old request or trying to override a legitimate refusal.
    """
    question = ""
    previous_failed_question = ""
    awaiting_reply = False
    recovered = False

    def on_item(event: ConversationItemAddedEvent) -> None:
        nonlocal question, previous_failed_question, awaiting_reply, recovered
        if recovered or not isinstance(event.item, llm.ChatMessage):
            return
        item = event.item
        text = _normalize(item.text_content or "")
        if item.role == "user":
            question = text
            awaiting_reply = bool(text)
            return
        if item.role != "assistant" or not awaiting_reply or not text:
            return
        awaiting_reply = False
        if item.interrupted or not _GENERIC_FAILURE.fullmatch(text):
            previous_failed_question = ""
            return
        if previous_failed_question and previous_failed_question != question:
            replacement = create_agent()
            session.update_agent(replacement)
            recovered = True
            logger.warning(
                "Repeated generic model failure detected; refreshed voice context once. "
                "No prior request was replayed."
            )
        else:
            previous_failed_question = question

    session.on("conversation_item_added", on_item)
