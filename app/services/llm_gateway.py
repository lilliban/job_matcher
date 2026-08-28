"""
LLMGateway — astrazione unificata sui provider LLM.

Strategia (RNF1):
  1. Cache SQLite  — se la stessa coppia (prompt, model) è già stata
     elaborata, restituisce il risultato salvato. Zero chiamate API.
  2. Gemini Flash  — provider primario, free tier 1500 req/giorno.
  3. Ollama locale — fallback automatico quando Gemini è a quota o
     non configurato. Gratuito e illimitato.

Il chiamante non sa mai quale provider ha risposto: l'interfaccia è
sempre `complete()` / `complete_json()`.
"""
import hashlib
import json
import logging
import random
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import (
    GEMINI_API_KEY,
    GEMINI_BASE_URL,
    GEMINI_MODEL,
    LLM_CACHE_ENABLED,
    LLM_TIMEOUT,
    OLLAMA_MODEL,
    OLLAMA_URL,
)
from app.models import LLMCache

logger = logging.getLogger(__name__)


class LLMGatewayError(Exception):
    """Nessun provider LLM disponibile."""


class LLMGateway:
    def __init__(self, db: Session | None = None, timeout: float = LLM_TIMEOUT):
        self.db = db
        self.timeout = timeout
        self.last_model_used: str | None = None

    # -----------------------------------------------------------------
    # API pubblica
    # -----------------------------------------------------------------
    async def complete(self, prompt: str, *, json_mode: bool = False, system_prompt: str | None = None) -> str:
        """Genera testo. Cache → Gemini → Ollama."""
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        else:
            full_prompt = prompt

        cached = self._cache_get(full_prompt)
        if cached is not None:
            logger.debug("LLM cache HIT")
            return cached

        result: str | None = None

        if GEMINI_API_KEY:
            try:
                result = await self._call_gemini(full_prompt, json_mode=json_mode)
                self.last_model_used = f"gemini/{GEMINI_MODEL}"
                logger.info(f"✅ Gemini risposto correttamente")
            except Exception as exc:
                logger.warning(f"Gemini non disponibile ({exc}) → fallback Ollama")

        if result is None:
            try:
                logger.info("🔄 Provo con Ollama...")
                result = await self._call_ollama(full_prompt, json_mode=json_mode)
                self.last_model_used = f"ollama/{OLLAMA_MODEL}"
                logger.info(f"✅ Ollama risposto correttamente")
            except Exception as exc:
                logger.error(f"❌ Ollama fallito: {exc}")
                raise LLMGatewayError(
                    "Nessun provider LLM disponibile. Configura GEMINI_API_KEY "
                    "nel file .env oppure avvia Ollama in locale (ollama serve)."
                ) from exc

        # <--- AGGIUNGI QUESTO CONTROLLO --->
        if result is None:
            raise LLMGatewayError("LLM ha restituito None")

        self._cache_set(full_prompt, result)
        return result       
                
                
    async def complete_json(self, prompt: str, *, default: Any = None, system_prompt: str | None = None) -> Any:
        """Genera e parsifica JSON."""
        try:
            raw = await self.complete(prompt, json_mode=True, system_prompt=system_prompt)
        except LLMGatewayError:
            raise
        except Exception as exc:
            logger.warning("complete_json fallito: %s", exc)
            return default

        
        if raw is None:
            logger.warning("complete_json: raw è None, restituisco default")
            return default

        cleaned = self._strip_code_fences(raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            extracted = self._extract_json_block(cleaned)
            if extracted is not None:
                return extracted
            logger.warning("Risposta LLM non è JSON valido: %s", cleaned[:200])
            return default

    # -----------------------------------------------------------------
    # Cache (RNF2)
    # -----------------------------------------------------------------
    @staticmethod
    def _hash(prompt: str) -> str:
        model_tag = GEMINI_MODEL if GEMINI_API_KEY else OLLAMA_MODEL
        return hashlib.sha256(f"{model_tag}::{prompt}".encode()).hexdigest()

    def _cache_get(self, prompt: str) -> str | None:
        if not (LLM_CACHE_ENABLED and self.db):
            return None
        try:
            row = (
                self.db.query(LLMCache)
                .filter(LLMCache.prompt_hash == self._hash(prompt))
                .first()
            )
            if row:
                row.hit_count += 1
                self.db.commit()
                self.last_model_used = row.model
                return row.response
        except Exception as exc:  # noqa: BLE001
            logger.debug("Cache lookup fallito: %s", exc)
        return None

    def _cache_set(self, prompt: str, response: str) -> None:
        if not (LLM_CACHE_ENABLED and self.db):
            return
        try:
            self.db.add(
                LLMCache(
                    prompt_hash=self._hash(prompt),
                    model=self.last_model_used or "unknown",
                    response=response,
                )
            )
            self.db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Cache write fallito: %s", exc)
            self.db.rollback()

    # -----------------------------------------------------------------
    # Provider: Gemini
    # -----------------------------------------------------------------
    async def _call_gemini(self, prompt: str, *, json_mode: bool) -> str:
        url = f"{GEMINI_BASE_URL}/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        logger.info(f"🔄 Chiamata Gemini: {url[:100]}...")
        payload: dict = {"contents": [{"parts": [{"text": prompt}]}]}
        if json_mode:
            payload["generationConfig"] = {"response_mime_type": "application/json"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates") or []
        if not candidates:
            raise LLMGatewayError("Gemini ha restituito una risposta vuota")
        parts = candidates[0].get("content", {}).get("parts") or []
        if not parts:
            raise LLMGatewayError("Gemini ha restituito contenuto vuoto")
        return parts[0].get("text", "")

    # -----------------------------------------------------------------
    # Provider: Ollama (fallback locale)
    # -----------------------------------------------------------------
    async def _call_ollama(self, prompt: str, *, json_mode: bool) -> str:
        payload: dict = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
        if json_mode:
            payload["format"] = "json"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(OLLAMA_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return data.get("response", "")

    # -----------------------------------------------------------------
    # Helper
    # -----------------------------------------------------------------
    @staticmethod
    def _strip_code_fences(text: str) -> str:
        t = text.strip()
        if t.startswith("```"):
            t = t.split("\n", 1)[-1] if "\n" in t else t
            t = t.removeprefix("json").strip()
            if t.endswith("```"):
                t = t[: t.rfind("```")]
        return t.strip()

    @staticmethod
    def _extract_json_block(text: str) -> Any | None:
        """Cerca il primo array o oggetto JSON bilanciato nel testo."""
        for opener, closer in (("[", "]"), ("{", "}")):
            start = text.find(opener)
            if start == -1:
                continue
            depth = 0
            for i in range(start, len(text)):
                if text[i] == opener:
                    depth += 1
                elif text[i] == closer:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start : i + 1])
                        except json.JSONDecodeError:
                            break
        return None


def get_llm_gateway(db: Session | None = None) -> LLMGateway:
    """Factory — il gateway non è singleton perché porta con sé la
    sessione DB per la cache."""
    return LLMGateway(db=db)
