"""
Optional ChatGPT-based postprocessing: paragraphing, punctuation, and speaker label mapping.

Safe to ignore if no API key is provided.
"""
import os
from typing import Optional


DEFAULT_SYSTEM_PROMPT = (
    "你是中文编辑助手。请在不改变原意的前提下：\n"
    "1) 按自然语气断句分段；2) 补充合理标点；3) 保留并规范化说话人标签（如[ SPEAKER_00 ] → 主持，[ SPEAKER_01 ] → 受访者）。\n"
    "输出纯文本，不要解释。"
)


def polish_with_chatgpt(
    text: str,
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
    system_prompt: Optional[str] = None,
) -> str:
    """
    Use OpenAI-compatible Chat Completions API to refine merged text.

    Set OPENAI_API_KEY or pass api_key.
    """
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        # No key: return original text unchanged
        return text

    try:
        from openai import OpenAI
    except Exception as e:
        # SDK missing; return original
        return text

    client = OpenAI(api_key=key)
    messages = [
        {"role": "system", "content": system_prompt or DEFAULT_SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]
    try:
        resp = client.chat.completions.create(model=model, messages=messages, temperature=0.2)
        return resp.choices[0].message.content or text
    except Exception:
        # Network or API failure: fall back gracefully
        return text

