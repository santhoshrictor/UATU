import io
import logging
from typing import Optional

from faster_whisper import WhisperModel
from livekit import rtc
from livekit.agents import stt
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions
from livekit.agents.utils import AudioBuffer

logger = logging.getLogger("offline_stt")


class LocalWhisperSTT(stt.STT):
    """
    Offline Speech-To-Text powered by faster-whisper (CTranslate2).
    Multilingual support (English, Tamil, Hindi, etc.) completely offline.
    """

    def __init__(
        self,
        model_path: str = "models/whisper-base",
        device: str = "cpu",
        compute_type: str = "int8",
        language: Optional[str] = None,
    ) -> None:
        super().__init__(
            capabilities=stt.STTCapabilities(streaming=False, interim_results=False)
        )
        if model_path is None:
            from pathlib import Path
            self._model_path = str(Path(__file__).resolve().parents[1] / "models" / "whisper-base")
        else:
            from pathlib import Path
            p = Path(model_path)
            if not p.is_absolute():
                p = (Path(__file__).resolve().parents[1] / model_path).resolve()
            self._model_path = str(p)
        self._device = device
        self._compute_type = compute_type
        self._language = language
        self._model: Optional[WhisperModel] = None

    def _ensure_model(self) -> WhisperModel:
        if self._model is None:
            logger.info("Loading local Whisper model from %s...", self._model_path)
            self._model = WhisperModel(
                self._model_path,
                device=self._device,
                compute_type=self._compute_type,
            )
            logger.info("Local Whisper model loaded successfully.")
        return self._model

    async def _recognize_impl(
        self,
        buffer: AudioBuffer,
        *,
        language: Optional[str] = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> stt.SpeechEvent:
        import asyncio

        try:
            combined = rtc.combine_audio_frames(buffer)
            wav_bytes = combined.to_wav_bytes()
        except Exception as e:
            logger.error("Failed to extract wav bytes: %s", e)
            return stt.SpeechEvent(
                type=stt.SpeechEventType.FINAL_TRANSCRIPT, alternatives=[]
            )

        lang_to_use = language or self._language

        def _transcribe() -> tuple[str, str]:
            model = self._ensure_model()
            segments, info = model.transcribe(
                io.BytesIO(wav_bytes),
                beam_size=1,
                language=lang_to_use,
                vad_filter=True,
            )
            text = " ".join([s.text for s in segments]).strip()
            return text, info.language

        try:
            text, detected_lang = await asyncio.to_thread(_transcribe)
            if not text:
                return stt.SpeechEvent(
                    type=stt.SpeechEventType.FINAL_TRANSCRIPT, alternatives=[]
                )

            logger.info("Transcribed (%s): %s", detected_lang, text)
            return stt.SpeechEvent(
                type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                alternatives=[stt.SpeechData(text=text, language=detected_lang)],
            )
        except Exception as e:
            logger.error("Whisper transcription error: %s", e)
            return stt.SpeechEvent(
                type=stt.SpeechEventType.FINAL_TRANSCRIPT, alternatives=[]
            )
