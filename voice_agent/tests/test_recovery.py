from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from livekit.agents import llm

from recovery import install_repetition_recovery

BOILERPLATE = "I'm just a language model. I can't help you with that."


def setup_recovery():
    session = Mock()
    factory = Mock(return_value=object())
    install_repetition_recovery(session, factory)
    return session, factory, session.on.call_args.args[1]


def emit(callback, role, text, *, message_id=None):
    kwargs = {"id": message_id} if message_id else {}
    item = llm.ChatMessage(role=role, content=[text], **kwargs)
    callback(SimpleNamespace(item=item))


def test_two_generic_failures_on_different_questions_refresh_once():
    session, factory, callback = setup_recovery()
    for question in ["Hello", "What is two plus two?"]:
        emit(callback, "user", question)
        emit(callback, "assistant", BOILERPLATE)
    session.update_agent.assert_called_once_with(factory.return_value)
    # No automatic replay or prompt asking the model to override a refusal.
    session.generate_reply.assert_not_called()
    for question in ["What is your name?", "Can you hear me?"]:
        emit(callback, "user", question)
        emit(callback, "assistant", BOILERPLATE)
    assert session.update_agent.call_count == 1


def test_normal_and_legitimate_refusals_do_not_refresh():
    session, factory, callback = setup_recovery()
    for question in ["Do something unsafe", "Do it anyway"]:
        emit(callback, "user", question)
        emit(callback, "assistant", "I cannot help with harming someone, sir.")
    factory.assert_not_called()
    session.update_agent.assert_not_called()


def test_normal_answer_breaks_the_streak():
    session, _, callback = setup_recovery()
    for question, answer in [
        ("Hi", BOILERPLATE),
        ("Two plus two?", "Four, sir."),
        ("Hello?", BOILERPLATE),
    ]:
        emit(callback, "user", question)
        emit(callback, "assistant", answer)
    session.update_agent.assert_not_called()


def test_duplicate_events_and_repeated_same_question_do_not_refresh():
    session, _, callback = setup_recovery()
    emit(callback, "user", "Hello", message_id="user-one")
    emit(callback, "assistant", BOILERPLATE, message_id="reply-one")
    emit(callback, "assistant", BOILERPLATE, message_id="reply-one")
    emit(callback, "user", "Hello")
    emit(callback, "assistant", BOILERPLATE)
    session.update_agent.assert_not_called()


def test_quoted_boilerplate_is_not_a_failure():
    session, _, callback = setup_recovery()
    for question in ["What did I say?", "Explain that phrase"]:
        emit(callback, "user", question)
        emit(
            callback,
            "assistant",
            f'You quoted: "{BOILERPLATE}" That is not a useful answer.',
        )
    session.update_agent.assert_not_called()


def test_curly_apostrophes_and_case_variants_are_recognized():
    session, _, callback = setup_recovery()
    for question in ["Hello", "Can you hear me?"]:
        emit(callback, "user", question)
        emit(
            callback,
            "assistant",
            "I\u2019M JUST A LANGUAGE MODEL. I CAN\u2019T HELP WITH THAT.",
        )
    session.update_agent.assert_called_once()


def test_interrupted_response_does_not_trigger_recovery():
    session, _, callback = setup_recovery()
    emit(callback, "user", "Hello")
    emit(callback, "assistant", BOILERPLATE)
    emit(callback, "user", "What is your name?")
    callback(
        SimpleNamespace(
            item=llm.ChatMessage(
                role="assistant", content=[BOILERPLATE], interrupted=True
            )
        )
    )
    session.update_agent.assert_not_called()


@pytest.mark.asyncio
async def test_replacement_preserves_guardrails_but_not_old_context(monkeypatch):
    from agent import Assistant, google
    from prompts import AGENT_INSTRUCTIONS

    # No provider calls or microphone access in this test.
    models = [Mock(), Mock()]
    monkeypatch.setattr(google.realtime, "RealtimeModel", Mock(side_effect=models))
    original = Assistant()
    await original.update_chat_ctx(
        llm.ChatContext(
            items=[llm.ChatMessage(role="assistant", content=[BOILERPLATE])]
        )
    )
    replacement = Assistant(recovered=True)
    assert replacement.llm is not original.llm
    assert replacement.instructions == AGENT_INSTRUCTIONS
    assert replacement.chat_ctx.items == []
    session = Mock(generate_reply=AsyncMock())
    monkeypatch.setattr(Assistant, "session", property(lambda self: session))
    await replacement.on_enter()
    instructions = session.generate_reply.call_args.kwargs["instructions"]
    assert "earlier context is no longer available" in instructions
    assert "Do not answer or retry any earlier request" in instructions
