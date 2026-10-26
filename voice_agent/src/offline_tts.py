import contextlib
import os
import tempfile
import uuid

import pyttsx3
import soundfile as sf
from livekit.agents import tts, utils
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions


class LocalTTS(tts.TTS):
    """
    Offline Text-to-Speech using Windows local SAPI5 neural voices.
    Zero latency, completely offline, zero cloud dependency.
    """

    def __init__(self, voice_id: str | None = None, rate: int = 175) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=22050,
            num_channels=1,
        )
        self._voice_id = voice_id
        self._rate = rate

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> tts.ChunkedStream:
        return LocalTTSChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
            voice_id=self._voice_id,
            rate=self._rate,
        )


class LocalTTSChunkedStream(tts.ChunkedStream):
    def __init__(
        self,
        *,
        tts: LocalTTS,
        input_text: str,
        conn_options: APIConnectOptions,
        voice_id: str | None,
        rate: int,
    ) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._voice_id = voice_id
        self._rate = rate
        self._audio_generated = False

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        if self._audio_generated:
            return

        clean_text = self.input_text.strip()
        if not clean_text:
            return

        temp_path = os.path.join(
            tempfile.gettempdir(), f"iris_tts_{uuid.uuid4().hex[:8]}.wav"
        )
        try:
            # Run pyttsx3 in thread to prevent blocking the asyncio event loop
            import asyncio

            def _synthesize() -> None:
                engine = pyttsx3.init()
                if self._voice_id:
                    engine.setProperty("voice", self._voice_id)
                engine.setProperty("rate", self._rate)
                engine.save_to_file(clean_text, temp_path)
                engine.runAndWait()
                engine.stop()

            await asyncio.to_thread(_synthesize)

            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 44:
                data, sr = sf.read(temp_path, dtype="int16")
                # Ensure mono
                if len(data.shape) > 1:
                    data = data[:, 0]
                audio_bytes = data.tobytes()

                output_emitter.initialize(
                    request_id=utils.shortuuid(),
                    sample_rate=sr,
                    num_channels=1,
                    mime_type="audio/pcm",
                )
                output_emitter.push(audio_bytes)
                output_emitter.flush()
                self._audio_generated = True
        except Exception as exc:
            import logging
            logging.getLogger("offline_tts").error("Local TTS failed: %s", exc)
        finally:
            if os.path.exists(temp_path):
                with contextlib.suppress(Exception):
                    os.remove(temp_path)
