"""Optional BYOK LLM polishing of the generated narrative.

The rule-based generator always runs first; the LLM only rewrites the
spoken text into a more natural nurse voice while keeping every fact,
number and abbreviation intact.  Works with the Anthropic API or any
OpenAI-compatible endpoint (Ollama, vLLM, OpenAI ...).
"""
from __future__ import annotations

import re
from typing import Any

SYSTEM_PROMPT = """당신은 한국 종합병원 외과 병동에서 10년 이상 근무한 간호사입니다.
아래에 주어진 간호기록 구술 대본을, 실제 간호사가 녹음기에 대고 말하듯 자연스러운 구어체로 다듬어 주세요.

규칙:
1. 첫 줄(시그널: 날짜, 시각, 환자명, 기록 종류)은 한 글자도 바꾸지 말고 그대로 두세요.
2. 숫자, 약어(HTN, PCA, JP, POD 등), 약 이름, 용량, 시각 등 모든 사실은 절대 바꾸지 마세요. 새로운 사실을 추가하지 마세요.
3. 문장 순서는 유지하되 어색한 연결을 자연스럽게 고치고, 현장 말투("~하시구요", "~측정되었습니다", "노티했습니다")를 섞어 주세요.
4. 마지막 줄의 종료 문장도 유지하세요.
5. 설명이나 머리말 없이 다듬어진 대본 텍스트만 출력하세요. 줄바꿈 구조(문단)는 유지하세요."""


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n", "", text)
    text = re.sub(r"\n```$", "", text)
    return text.strip()


def polish(spoken_text: str, settings: dict[str, Any]) -> str:
    provider = settings.get("llm_provider", "none")
    api_key = settings.get("llm_api_key", "")
    if provider == "none" or not api_key:
        return spoken_text
    if provider == "anthropic":
        return _anthropic(spoken_text, api_key, settings.get("llm_model") or "claude-opus-5-5")
    if provider == "openai_compatible":
        return _openai_compatible(spoken_text, api_key, settings.get("llm_model") or "gpt-4o-mini",
                                  settings.get("llm_base_url") or "https://api.openai.com/v1")
    return spoken_text


def _anthropic(text: str, api_key: str, model: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except TypeError:
        # Older SDK without the fallbacks parameter.
        response = client.messages.create(
            model=model, max_tokens=4000, system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
    if getattr(response, "stop_reason", "") == "refusal":
        return text
    out = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
    return _validate(text, _strip_fences(out))


def _openai_compatible(text: str, api_key: str, model: str, base_url: str) -> str:
    import httpx

    r = httpx.post(
        base_url.rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}],
            "temperature": 0.7,
        },
        timeout=120.0,
    )
    r.raise_for_status()
    out = r.json()["choices"][0]["message"]["content"]
    return _validate(text, _strip_fences(out))


def _validate(original: str, polished: str) -> str:
    """Reject rewrites that lost the signal line or dropped numbers."""
    if not polished:
        return original
    first_orig = original.strip().splitlines()[0].strip()
    first_new = polished.strip().splitlines()[0].strip()
    if first_orig != first_new:
        polished = first_orig + "\n" + "\n".join(polished.strip().splitlines()[1:])
    nums_o = set(re.findall(r"\d+(?:\.\d+)?", original))
    nums_n = set(re.findall(r"\d+(?:\.\d+)?", polished))
    if not nums_o.issubset(nums_n):
        return original
    return polished
