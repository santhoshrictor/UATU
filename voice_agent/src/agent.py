import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from google.genai import types
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli, room_io
from livekit.agents.beta.tools import EndCallTool
from livekit.plugins import google

from audit_logger import UATUAuditLogger
from hardware_tools import HardwareTools
from knowledge import KnowledgeTools
from network_utils import enable_ipv4_preference
from prompts import AGENT_INSTRUCTIONS, INITIAL_GREETING
from recovery import install_repetition_recovery
from uatu_tools import UATUTools
from vision_tools import VisionTools

enable_ipv4_preference()
load_dotenv(Path(__file__).resolve().parents[1] / ".env.local")


class Assistant(Agent):
    def __init__(self, *args, recovered: bool = False, **kwargs) -> None:
        self._recovered = recovered
        self.audit_logger = UATUAuditLogger()
        self.knowledge_tools = KnowledgeTools()
        self.hardware_tools = HardwareTools()
        self.vision_tools = VisionTools()
        self.uatu_tools = UATUTools(audit_logger=self.audit_logger)
        self._end_call_tool = EndCallTool(
            extra_description="Only end the call after the user clearly says goodbye or asks to end the call.",
            end_instructions="Give UATU's brief, professional status confirmation, then end the call.",
        )
        super().__init__(
            llm=google.realtime.RealtimeModel(
                model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-live-preview"),
                voice=os.getenv("GEMINI_VOICE", "Enceladus"),
                realtime_input_config=types.RealtimeInputConfig(
                    automatic_activity_detection=types.AutomaticActivityDetection(
                        disabled=False,
                        start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,
                        end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
                        prefix_padding_ms=100,
                        silence_duration_ms=250,
                    ),
                    activity_handling=types.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS,
                ),
            ),
            instructions=AGENT_INSTRUCTIONS,
            tools=[
                *self.knowledge_tools.tools,
                *self.hardware_tools.tools,
                *self.vision_tools.tools,
                *self.uatu_tools.tools,
                *self._end_call_tool.tools,
            ],
        )

    async def on_enter(self) -> None:
        if self._recovered:
            await self.session.generate_reply(
                instructions=(
                    "Briefly tell the operator the conversation has been refreshed and "
                    "earlier context is no longer available. Ask them to repeat their "
                    "last query. Do not answer or retry any earlier request. "
                    "Keep all safety rules and capability limitations unchanged."
                )
            )


server = AgentServer()


@server.rtc_session(agent_name=os.getenv("AGENT_NAME", "iris"))
async def my_agent(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    # Connect to room immediately so frontend detects agent presence without timing out
    await ctx.connect()

    audit_logger = UATUAuditLogger()
    background_tasks: set[asyncio.Task] = set()

    # Non-blocking initial session audit
    init_task = asyncio.create_task(
        asyncio.to_thread(
            audit_logger.log_event,
            action_type="SYSTEM_HEALTH_CHECK",
            query_or_command="System session connected",
            response_summary=INITIAL_GREETING,
            human_review_disclaimer_applied=False,
        )
    )
    background_tasks.add(init_task)
    init_task.add_done_callback(background_tasks.discard)

    # Gemini supplies its own turn detection, speech recognition and voice output.
    session = AgentSession()
    install_repetition_recovery(session, lambda: Assistant(recovered=True))

    last_user_query = ""

    def on_conversation_item(event) -> None:
        nonlocal last_user_query
        item = getattr(event, "item", None)
        if not item:
            return
        role = getattr(item, "role", "")
        text = getattr(item, "text_content", "") or ""
        if role == "user":
            last_user_query = text
        elif role == "assistant" and text:
            disclaimer_applied = (
                "human review" in text.lower() or "human verification" in text.lower()
            )
            log_task = asyncio.create_task(
                asyncio.to_thread(
                    audit_logger.log_event,
                    action_type="VOICE_OR_TEXT_QUERY",
                    query_or_command=last_user_query,
                    response_summary=text[:300],
                    human_review_disclaimer_applied=disclaimer_applied,
                )
            )
            background_tasks.add(log_task)
            log_task.add_done_callback(background_tasks.discard)

    session.on("conversation_item_added", on_conversation_item)

    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_options=room_io.RoomOptions(video_input=True),
    )
    await session.generate_reply(
        instructions=f'Greet the operator strictly with: "{INITIAL_GREETING}"'
    )


if __name__ == "__main__":
    cli.run_app(server)
