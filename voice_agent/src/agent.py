
import asyncio
import logging
import os
import time
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

logger = logging.getLogger("iris.agent_worker")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [LiveKit Agent] %(message)s",
)

# Resilience & Diagnostic Constants
ROOM_CONNECT_TIMEOUT_SEC = 10.0
HANDSHAKE_TIMEOUT_SEC = 12.0
GREETING_TIMEOUT_SEC = 8.0
MAX_SESSION_RETRIES = 2


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
    room_name = getattr(ctx.room, "name", "unknown_room")
    ctx.log_context_fields = {"room": room_name}
    logger.info(f"Accepted LiveKit job for room '{room_name}'. Connecting to RTC room...")

    # 1. Connect to LiveKit room with strict timeout to prevent indefinite hang
    try:
        t0_connect = time.perf_counter()
        await asyncio.wait_for(ctx.connect(), timeout=ROOM_CONNECT_TIMEOUT_SEC)
        connect_ms = (time.perf_counter() - t0_connect) * 1000
        logger.info(f"Connected to LiveKit room '{room_name}' in {connect_ms:.1f}ms")
    except asyncio.TimeoutError:
        logger.error(
            f"Timed out after {ROOM_CONNECT_TIMEOUT_SEC}s attempting to connect to LiveKit room '{room_name}'."
        )
        return
    except Exception as exc:
        logger.error(f"Failed to connect to LiveKit room '{room_name}': {exc}", exc_info=True)
        return

    disconnect_event = asyncio.Event()

    # 2. Register Room Lifecycle & Diagnostic Event Handlers
    @ctx.room.on("participant_connected")
    def on_participant_connected(participant):
        logger.info(
            f"Operator joined room '{room_name}': identity='{participant.identity}', name='{participant.name}'"
        )

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant):
        logger.info(f"Operator disconnected from room '{room_name}': identity='{participant.identity}'")
        # Trigger immediate teardown when operator disconnects so worker is immediately free for next room
        disconnect_event.set()

    @ctx.room.on("disconnected")
    def on_room_disconnected(reason=None):
        logger.warning(f"Room '{room_name}' disconnected. Reason: {reason}")
        disconnect_event.set()

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

    try:
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

        # 3. Initialize AgentSession with Handshake Timeout & Reconnect Fallback
        session_started = False
        session = None

        for attempt in range(1, MAX_SESSION_RETRIES + 1):
            try:
                logger.info(
                    f"Establishing Gemini Live WebSocket session (attempt {attempt}/{MAX_SESSION_RETRIES})..."
                )
                session = AgentSession()
                install_repetition_recovery(session, lambda: Assistant(recovered=True))
                session.on("conversation_item_added", on_conversation_item)

                t0_start = time.perf_counter()
                await asyncio.wait_for(
                    session.start(
                        agent=Assistant(),
                        room=ctx.room,
                        room_options=room_io.RoomOptions(video_input=True),
                    ),
                    timeout=HANDSHAKE_TIMEOUT_SEC,
                )
                handshake_ms = (time.perf_counter() - t0_start) * 1000
                logger.info(
                    f"Gemini Live session initialized successfully in {handshake_ms:.1f}ms (attempt {attempt})"
                )
                session_started = True
                break
            except asyncio.TimeoutError:
                logger.warning(
                    f"Gemini Live WebSocket handshake timed out after {HANDSHAKE_TIMEOUT_SEC}s (attempt {attempt}/{MAX_SESSION_RETRIES})"
                )
                if attempt < MAX_SESSION_RETRIES:
                    await asyncio.sleep(1.0)
            except Exception as exc:
                logger.error(
                    f"Gemini Live handshake failed on attempt {attempt}/{MAX_SESSION_RETRIES}: {exc}",
                    exc_info=True,
                )
                if attempt < MAX_SESSION_RETRIES:
                    await asyncio.sleep(1.0)

        if not session_started or session is None:
            logger.critical(
                f"Failed to establish Gemini Live WebSocket session for room '{room_name}' after {MAX_SESSION_RETRIES} attempts. Disconnecting room cleanly to unblock frontend."
            )
            try:
                await ctx.room.disconnect()
            except Exception as disc_err:
                logger.debug(f"Room disconnect error: {disc_err}")
            return

        # 4. Initial greeting with timeout fallback (does not crash session if delayed)
        try:
            logger.info("Dispatching initial operator greeting...")
            await asyncio.wait_for(
                session.generate_reply(
                    instructions=f'Greet the operator strictly with: "{INITIAL_GREETING}"'
                ),
                timeout=GREETING_TIMEOUT_SEC,
            )
            logger.info("Initial operator greeting dispatched successfully.")
        except asyncio.TimeoutError:
            logger.warning(
                f"Initial greeting timed out after {GREETING_TIMEOUT_SEC}s; agent remains active and listening."
            )
        except Exception as exc:
            logger.warning(
                f"Initial greeting skipped due to error: {exc}; agent remains active and listening."
            )

        # 5. Keep Session Active & Listen for Live Operator Telemetry / Reconnect Signals
        logger.info(f"LiveKit Agent active for room '{room_name}'. Listening continuously...")

        # Periodic keep-alive ping to ensure room connection remains fresh and active
        async def _room_keepalive_ping():
            try:
                while not disconnect_event.is_set():
                    await asyncio.sleep(15.0)
                    if hasattr(ctx.room, "connection_state") and getattr(ctx.room.connection_state, "name", "") == "CONNECTED":
                        logger.debug(f"[LiveKit KeepAlive] Room '{room_name}' connection healthy.")
            except asyncio.CancelledError:
                pass

        keepalive_task = asyncio.create_task(_room_keepalive_ping())
        background_tasks.add(keepalive_task)

        # Block entrypoint until operator disconnects or signals reconnect
        await disconnect_event.wait()
        logger.info(f"Operator teardown initiated for room '{room_name}'. Closing session cleanly...")

    finally:
        # Graceful cleanup of session so WebRTC tracks & Gemini sockets are immediately released
        if session is not None:
            try:
                await session.aclose()
            except Exception as close_err:
                logger.debug(f"Session aclose error: {close_err}")

        # Graceful cleanup of any pending background audit tasks
        for task in list(background_tasks):
            if not task.done():
                task.cancel()

        logger.info(
            f"Worker session for room '{room_name}' cleaned up. Standing by for immediate re-handshake."
        )


if __name__ == "__main__":
    cli.run_app(server)

