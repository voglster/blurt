from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are a transcription post-processor. Fix capitalization, punctuation, "
    "and the spelling of well-known technical terms (e.g., GitHub, GitLab, "
    "kubectl, Postgres, PostgreSQL, npm, JSON, YAML, AWS, Docker, Kubernetes, "
    "Python, JavaScript, TypeScript). Do NOT paraphrase, summarize, expand, "
    "or change wording. Do NOT add or remove content. Return ONLY the "
    "corrected text with no quotes, no commentary, no explanation."
)


class CleanupClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_ms: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_ms / 1000
        self._client = httpx.AsyncClient(transport=transport, timeout=self._timeout_s)

    async def cleanup(self, text: str) -> str:
        if not text.strip():
            return text
        try:
            resp = await self._client.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "system": SYSTEM_PROMPT,
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
