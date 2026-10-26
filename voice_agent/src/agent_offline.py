import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli, stt
from livekit.agents.beta.tools import EndCallTool
from livekit.plugins import openai, silero

from audit_logger import UATUAuditLogger
from hardware_tools import HardwareTools
from knowledge import KnowledgeTools
from network_utils import enable_ipv4_preference
from offline_stt import LocalWhisperSTT
from offline_tts import LocalTTS
from prompts import AGENT_INSTRUCTIONS, INITIAL_GREETING
from uatu_tools import UATUTools
from vision_tools import VisionTools

enable_ipv4_preference()

# Load offline environment configuration if available, otherwise fallback to local
env_offline = Path(__file__).resolve().parents[1] / ".env.offline"
if env_offline.exists():
    load_dotenv(env_offline, override=True)
else:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env.local")

# Defaults for complete local offline operation
LLAMA_SERVER_URL = os.getenv("LLAMA_SERVER_URL", "http://127.0.0.1:8080/v1")
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "qwen2.5-1.5b-instruct-q4_k_m.gguf")


class OfflineAssistant(Agent):
    def __init__(self) -> None:
        self.audit_logger = UATUAuditLogger()
        self.knowledge_tools = KnowledgeTools()
        self.hardware_tools = HardwareTools()
        self.vision_tools = VisionTools()
        self.uatu_tools = UATUTools(audit_logger=self.audit_logger)
        self._end_call_tool = EndCallTool(
            extra_description="Only end the call after the user clearly says goodbye or asks to end the call.",
            end_instructions="Give UATU's brief, professional status confirmation, then end the call.",
        )

        # 1. Local Voice Activity Detection
        vad = silero.VAD.load()

        # 2. Local Whisper Speech-To-Text wrapped with VAD StreamAdapter
        whisper_stt = LocalWhisperSTT()
        stt_stream = stt.StreamAdapter(stt=whisper_stt, vad=vad)

        # 3. Local LLM via llama-server (OpenAI-compatible)
        local_llm = openai.LLM(
            base_url=LLAMA_SERVER_URL,
            api_key="local",
            model=LLAMA_MODEL,
        )

        # 4. Local Neural TTS (Windows SAPI5)
        local_tts = LocalTTS()

        super().__init__(
            vad=vad,
            stt=stt_stream,
            llm=local_llm,
            tts=local_tts,
            instructions=AGENT_INSTRUCTIONS,
            tools=[
                *self.knowledge_tools.tools,
                *self.hardware_tools.tools,
                *self.vision_tools.tools,
                *self.uatu_tools.tools,
                *self._end_call_tool.tools,
            ],
            allow_interruptions=True,
        )


server = AgentServer()


@server.rtc_session(agent_name=os.getenv("AGENT_NAME", "iris"))
async def my_agent(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    await ctx.connect()

    audit_logger = UATUAuditLogger()
    background_tasks: set[asyncio.Task] = set()

    init_task = asyncio.create_task(
        asyncio.to_thread(
            audit_logger.log_event,
            action_type="SYSTEM_HEALTH_CHECK",
            query_or_command="Offline session connected",
            response_summary=INITIAL_GREETING,
            human_review_disclaimer_applied=False,
        )
    )
    background_tasks.add(init_task)
    init_task.add_done_callback(background_tasks.discard)

    session = AgentSession()

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
        agent=OfflineAssistant(),
        room=ctx.room,
    )
    await session.generate_reply(
        instructions=f'Greet the operator strictly with: "{INITIAL_GREETING}"'
    )


if __name__ == "__main__":
    cli.run_app(server)
