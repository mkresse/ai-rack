"""
title: Listening Trainer
author: martin
description: Generates speech audio for listening comprehension training. Text is hidden — the user hears it but cannot see it.
version: 0.2.0
"""

import httpx
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

VOICES = {
    "english": "gb_oliver_neutral",
    "french": "fr_marie_neutral",
}


async def emit_status(emitter, description: str, done: bool = False):
    await emitter({"type": "status", "data": {"description": description, "done": done}})


class Tools:
    def __init__(self):
        self.valves = self.Valves()

    class Valves(BaseModel):
        mistral_api_key: str = Field("", description="Mistral API key for TTS")
        mistral_api_base_url: str = Field("https://api.mistral.ai/v1", description="Mistral API base URL")
        tts_model: str = Field("voxtral-mini-tts-2603", description="Mistral TTS model to use")

    async def speak_text(
            self,
            text: str,
            language: str,
            speed: float = 1.0,
            __event_emitter__=None,
    ):
        """
        Convert text to speech for listening comprehension practice.
        Call this tool with text that the user should listen to and try to understand.
        The audio will be played but the text will remain hidden.
        IMPORTANT: After calling this tool, do NOT reveal or repeat the text in your response.
        Instead, ask the user what they heard or understood.

        :param text: The text to convert to speech (hidden from user).
        :param language: The language of the text. Must be "english" or "french".
        :param speed: Playback speed. Use 0.5 or 0.75 if the user wants slower speech. Default 1.0.
        :return: Status message for the assistant.
        """
        language = language.lower().strip()
        voice_id = VOICES.get(language)
        if not voice_id:
            return f"Error: unsupported language '{language}'. Use 'english' or 'french'."

        if not self.valves.mistral_api_key:
            await emit_status(__event_emitter__, "Mistral API key not configured", done=True)
            return "Error: Mistral API key is not set. Ask an admin to configure it in the tool valves."

        await emit_status(__event_emitter__, f"Generating {language} audio...")

        client = MistralTtsClient(self.valves.mistral_api_base_url, self.valves.mistral_api_key)
        try:
            audio_b64 = await client.synthesize(text, self.valves.tts_model, voice_id)
        except httpx.HTTPStatusError as e:
            await emit_status(__event_emitter__, f"TTS API error: {e.response.status_code}", done=True)
            return f"Error generating audio: {e.response.status_code}"
        except Exception as e:
            await emit_status(__event_emitter__, f"Error: {e}", done=True)
            return f"Error generating audio: {e}"
        await emit_status(__event_emitter__, "Audio ready", done=True)

        html = AudioPlayerHtml.render(audio_b64, speed)
        return HTMLResponse(content=html, headers={"Content-Disposition": "inline"}), {
            "status": "success",
            "description": (
                f"{language.capitalize()} listening exercise audio has been generated. "
                "Do NOT reveal, repeat, or hint at the text. "
                "Ask the user what they heard or understood. "
                "Only reveal the text after the user makes an attempt."
            ),
        }


class MistralTtsClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def synthesize(self, text: str, model: str, voice_id: str) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/audio/speech",
                headers=self.headers,
                json={
                    "input": text,
                    "model": model,
                    "voice_id": voice_id,
                    "response_format": "mp3",
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()["audio_data"]


class AudioPlayerHtml:
    @staticmethod
    def render(audio_b64: str, speed: float = 1.0) -> str:
        return f"""<!DOCTYPE html>
<html>
<head>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: system-ui, -apple-system, sans-serif;
    background: transparent;
  }}
  .player {{
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    padding: 12px 16px;
  }}
  .label {{
    font-size: 14px;
    color: #888;
    white-space: nowrap;
  }}
  audio {{
    flex: 1;
    min-width: 0;
    height: 36px;
  }}
  .speed {{
    display: flex;
    gap: 4px;
  }}
  .speed button {{
    border: 1px solid #ccc;
    border-radius: 4px;
    background: transparent;
    color: #888;
    font-size: 12px;
    padding: 2px 6px;
    cursor: pointer;
  }}
  .speed button.active {{
    background: #555;
    color: #fff;
    border-color: #555;
  }}
</style>
</head>
<body>
  <div class="player">
    <span class="label">Listen :</span>
    <audio id="audio" controls preload="auto"></audio>
    <div class="speed" id="speed">
      <button data-rate="0.5">0.5x</button>
      <button data-rate="0.75">0.75x</button>
      <button data-rate="1" class="active">1x</button>
    </div>
  </div>
  <script>
    const b64 = "{audio_b64}";
    const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    const blob = new Blob([bytes], {{ type: 'audio/mpeg' }});
    const initialSpeed = {speed};
    const audio = document.getElementById('audio');
    audio.src = URL.createObjectURL(blob);
    audio.playbackRate = initialSpeed;
    audio.addEventListener('loadedmetadata', () => {{
      if (audio.duration === Infinity || isNaN(audio.duration)) {{
        audio.currentTime = 1e99;
        audio.addEventListener('timeupdate', function fix() {{
          audio.removeEventListener('timeupdate', fix);
          audio.currentTime = 0;
        }});
      }}
    }});
    audio.addEventListener('ended', () => {{ audio.currentTime = 0; }});

    document.querySelectorAll('.speed button').forEach(b => {{
      b.classList.toggle('active', parseFloat(b.dataset.rate) === initialSpeed);
    }});
    document.getElementById('speed').addEventListener('click', e => {{
      const btn = e.target.closest('button[data-rate]');
      if (!btn) return;
      audio.playbackRate = parseFloat(btn.dataset.rate);
      document.querySelectorAll('.speed button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    }});

    function reportHeight() {{
      try {{
        const h = document.querySelector('.player').offsetHeight;
        window.parent.postMessage({{ type: 'iframe:height', height: h }}, '*');
      }} catch(e) {{}}
    }}
    reportHeight();
    window.addEventListener('load', reportHeight);
    new ResizeObserver(reportHeight).observe(document.documentElement);
  </script>
</body>
</html>"""
