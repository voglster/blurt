from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)


FALLBACK_VOCABULARY = (
    "GitHub, GitLab, kubectl, Postgres, PostgreSQL, npm, JSON, YAML, AWS, "
    "Docker, Kubernetes, Python, JavaScript, TypeScript"
)


def build_system_prompt(vocabulary: str = "") -> str:
    """Build the cleanup prompt, spelling out the user's own vocabulary.

    `vocabulary` takes the comma-separated form of `[stt] hotwords`, so one
    config value drives both decode-time biasing and the cleanup pass.
    """
    terms = ", ".join(t.strip() for t in vocabulary.split(",") if t.strip())
    return (
        "You are a transcription post-processor. Fix capitalization, punctuation, "
        f"and the spelling of well-known technical terms (e.g., {terms or FALLBACK_VOCABULARY}). "
        "Do NOT paraphrase, summarize, expand, "
        "or change wording. Do NOT add or remove content. Return ONLY the "
        "corrected text with no quotes, no commentary, no explanation."
    )


class CleanupClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_ms: int,
        vocabulary: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_ms / 1000
        self._system_prompt = build_system_prompt(vocabulary)
        self._client = httpx.AsyncClient(transport=transport, timeout=self._timeout_s)

    async def cleanup(self, text: str) -> str:
        if not text.strip():
            return text
        try:
            resp = await self._client.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "system": self._system_prompt,
                    "prompt": text,
                    "stream": False,
                    "options": {"temperature": 0},
                },
            )
            resp.raise_for_status()
            return resp.json()["response"].strip()
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            log.warning("cleanup failed (%s); returning original", exc)
            return text

    async def aclose(self) -> None:
        await self._client.aclose()
