from __future__ import annotations

import json
from typing import Any

import requests

from .diagnosis import MODEL_NAME, OLLAMA_URL, _parse_json
from .guidance import select_next_question
from .rules import (
    MEDICAL_DISCLAIMER,
    build_rule_trace,
    contains_red_flags,
    infer_symptoms,
    rank_patterns,
)


CHAT_FIELDS = {"reply", "follow_up"}
BLOCKED_TERMS = ["處方", "劑量", "治癒", "服用", "方劑", "針灸", "治療保證"]
INTERNAL_TERMS = ["rule_trace", "Python", "null", "None", "True", "False", "{", "}"]


def chat_reply(payload: dict[str, Any]) -> dict[str, Any]:
    message = str(payload.get("message", "")).strip()
    history = _normalize_history(payload.get("history", []))
    if not message:
        return {
            "reply": "請先輸入或使用語音說出想詢問的內容。",
            "follow_up": "請描述目前最主要的不適、持續時間與嚴重程度。",
            "red_flag": False,
            "medical_disclaimer": MEDICAL_DISCLAIMER,
        }

    qa_history = _history_to_qa(history, message)
    symptoms = infer_symptoms([], qa_history)
    trace = build_rule_trace(symptoms, None)
    ranked = rank_patterns(symptoms, trace)

    if contains_red_flags(symptoms, qa_history):
        return {
            "reply": "你描述的內容可能包含需要醫療評估的警訊。若正在出現胸痛、呼吸困難、意識不清、半邊無力、高燒持續或劇烈疼痛，請立即就醫或尋求急診協助。",
            "follow_up": "請確認是否正在出現上述警訊；若是，請不要等待線上回覆，請立即就醫。",
            "red_flag": True,
            "medical_disclaimer": MEDICAL_DISCLAIMER,
        }

    top = ranked[0] if ranked else {"pattern": "需要更多資料", "evidence": [], "level": "低"}
    fallback = _fallback_chat(message, symptoms, top)
    llm_result = _ask_chat_ollama(history, message, symptoms, ranked[:3])
    if not llm_result:
        return fallback

    result = {
        "reply": str(llm_result.get("reply") or fallback["reply"]),
        "follow_up": str(llm_result.get("follow_up") or fallback["follow_up"]),
        "red_flag": False,
        "medical_disclaimer": MEDICAL_DISCLAIMER,
    }
    return _sanitize_chat(result, fallback)


def _ask_chat_ollama(
    history: list[dict[str, str]],
    message: str,
    symptoms: list[str],
    ranked: list[dict[str, Any]],
) -> dict[str, Any] | None:
    public_patterns = [
        {
            "pattern": item.get("pattern"),
            "level": item.get("level"),
            "evidence": item.get("evidence", []),
        }
        for item in ranked
    ]
    prompt = f"""
你是中醫健康對話助理。請使用繁體中文回答，語氣清楚、溫和、簡短。

安全規則：
- 只能提供初步健康參考，不能取代醫師診斷。
- 不可提供藥物、處方、劑量、方劑、針灸、治療保證或宣稱治癒。
- 飲食建議只限一般日常食物與生活原則。
- 若資訊不足，應提出下一個需要確認的問題。
- 不可輸出 Python、rule_trace、null、原始 JSON 或內部技術資料。

最近對話：{json.dumps(history[-6:], ensure_ascii=False)}
使用者新問題：{message}
已偵測症狀：{json.dumps(symptoms, ensure_ascii=False)}
候選中醫傾向：{json.dumps(public_patterns, ensure_ascii=False)}

請只輸出 JSON：
{{
  "reply": "",
  "follow_up": ""
}}
"""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": MODEL_NAME, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}},
            timeout=30,
        )
        response.raise_for_status()
        parsed = _parse_json(response.json().get("response", ""))
    except (requests.RequestException, ValueError, KeyError):
        return None
    return parsed if parsed and CHAT_FIELDS <= set(parsed) else None


def _fallback_chat(message: str, symptoms: list[str], top: dict[str, Any]) -> dict[str, Any]:
    pattern = top.get("pattern", "需要更多資料")
    evidence = "、".join(top.get("evidence", []))
    if evidence:
        reply = f"依你目前描述，初步較偏向「{pattern}」，主要線索包括：{evidence}。這只作為健康參考，仍需要更多資料確認。"
    else:
        reply = "目前描述還不夠完整，我可以先協助整理症狀，但不能作為診斷結論。"
    return {
        "reply": reply,
        "follow_up": select_next_question(symptoms, pattern),
        "red_flag": False,
        "medical_disclaimer": MEDICAL_DISCLAIMER,
    }


def _sanitize_chat(result: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    combined = json.dumps(result, ensure_ascii=False)
    if any(term in combined for term in BLOCKED_TERMS + INTERNAL_TERMS):
        return fallback
    if "藥" in combined:
        result["reply"] = "我不能提供藥物、方劑、處方或劑量建議。若症狀持續或加重，請諮詢醫師；日常可先維持規律作息與清淡飲食。"
    result["medical_disclaimer"] = MEDICAL_DISCLAIMER
    result.setdefault("red_flag", False)
    return result


def _normalize_history(history: Any) -> list[dict[str, str]]:
    if not isinstance(history, list):
        return []
    normalized = []
    for item in history[-10:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip()
        content = str(item.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            normalized.append({"role": role, "content": content[:600]})
    return normalized


def _history_to_qa(history: list[dict[str, str]], message: str) -> list[dict[str, str]]:
    qa = [{"question": "使用者語音或文字提問", "answer": item["content"]} for item in history if item["role"] == "user"]
    qa.append({"question": "使用者語音或文字提問", "answer": message})
    return qa
