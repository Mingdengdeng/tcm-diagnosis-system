from __future__ import annotations

import json
import os
from typing import Any

import requests

from .guidance import is_weak_next_question, select_next_question
from .rules import (
    MEDICAL_DISCLAIMER,
    build_public_context,
    build_rule_trace,
    contains_red_flags,
    infer_symptoms,
    rank_patterns,
)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "12"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "180"))


def diagnose(payload: dict[str, Any]) -> dict[str, Any]:
    mode = payload.get("mode") or "qa_only"
    qa_history = _qa_history_from_payload(payload)
    symptoms = infer_symptoms(payload.get("symptoms", []), qa_history)
    face_delta = _face_delta_from_payload(payload) if mode == "multimodal" or payload.get("face_observation") else None
    rule_trace = build_rule_trace(symptoms, face_delta)
    ranked = rank_patterns(symptoms, rule_trace)
    red_flags = contains_red_flags(symptoms, qa_history)
    rule_result = _fallback_result(mode, ranked, symptoms, rule_trace)

    if red_flags:
        return _finalize_public_result(_urgent_result(mode, symptoms, rule_trace))

    public_context = build_public_context(symptoms, rule_trace, ranked)
    llm_result = _ask_ollama(mode, qa_history, public_context)
    if llm_result:
        llm_result = _merge_with_rule_result(llm_result, rule_result, ranked)
        llm_result["mode"] = mode
        llm_result["rule_trace"] = rule_trace
        llm_result["medical_disclaimer"] = MEDICAL_DISCLAIMER
        return _finalize_public_result(_sanitize_result(llm_result))

    return _finalize_public_result(rule_result)


def _ask_ollama(
    mode: str,
    qa_history: list[dict[str, str]],
    public_context: dict[str, Any],
) -> dict[str, Any] | None:
    compact_context = {
        "symptoms": public_context.get("symptoms", [])[:12],
        "top_candidates": public_context.get("candidate_patterns", [])[:3],
        "recommended_next_question": public_context.get("recommended_next_question", ""),
    }
    prompt = f"""
你是中醫健康評估助理。用繁體中文，把規則引擎結果改寫成簡短好懂的文字。
限制：只可初步參考；不可藥物、處方、劑量、治癒承諾；不可輸出內部欄位或原始 JSON；不要自行改變候選排序。
模式：{mode}
問答：{json.dumps(qa_history[-8:], ensure_ascii=False)}
候選：{json.dumps(compact_context, ensure_ascii=False)}
只輸出 JSON：
{{
  "preliminary_assessment": "",
  "possibility_level": "高/中/低",
  "supporting_evidence": "",
  "next_question": "",
  "dietary_suggestion": ""
}}
"""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "keep_alive": "10m",
                "options": {
                    "temperature": 0.1,
                    "num_predict": OLLAMA_NUM_PREDICT,
                    "num_ctx": 2048,
                },
            },
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        raw = response.json().get("response", "")
        return _parse_json(raw)
    except (requests.RequestException, ValueError, KeyError):
        return None


def _parse_json(raw: str) -> dict[str, Any] | None:
    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _fallback_result(
    mode: str,
    ranked: list[dict[str, Any]],
    symptoms: list[str],
    rule_trace: dict[str, Any],
) -> dict[str, Any]:
    top = ranked[0] if ranked else {"pattern": "需要更多資料", "level": "低", "evidence": []}
    food = top.get("food") or _food_suggestion(top["pattern"])
    next_question = select_next_question(symptoms, top.get("pattern"))
    possibilities = [_public_possibility(item) for item in ranked[:3]]
    return {
        "mode": mode,
        "preliminary_assessment": f"初步判斷偏向「{top['pattern']}」，仍需結合更多症狀確認。",
        "possibility_level": top["level"],
        "possibilities": possibilities,
        "report_summary": _build_report_summary(top, symptoms, rule_trace),
        "care_plan": top.get("care_plan", []),
        "watch_items": top.get("watch_items", []),
        "self_check_questions": top.get("self_check_questions", []),
        "seek_care_if": _seek_care_if(),
        "red_flag": False,
        "supporting_evidence": "、".join(top["evidence"]) or "目前資料不足，建議補充主要不適與持續時間。",
        "next_question": next_question,
        "next_recommended_action": next_question,
        "dietary_suggestion": food,
        "rule_trace": rule_trace,
        "medical_disclaimer": MEDICAL_DISCLAIMER,
    }


def _merge_with_rule_result(
    llm_result: dict[str, Any],
    rule_result: dict[str, Any],
    ranked: list[dict[str, Any]],
) -> dict[str, Any]:
    top_pattern = ranked[0]["pattern"] if ranked else ""
    top_evidence = ranked[0].get("evidence", []) if ranked else []
    assessment = str(llm_result.get("preliminary_assessment", ""))
    weak_assessment = not assessment or "資料不足" in assessment or (top_pattern and top_pattern not in assessment)
    if weak_assessment:
        llm_result["preliminary_assessment"] = rule_result["preliminary_assessment"]
    llm_result["possibility_level"] = rule_result["possibility_level"]
    if top_evidence:
        llm_result["supporting_evidence"] = rule_result["supporting_evidence"]
    llm_result["possibilities"] = rule_result.get("possibilities", [])
    llm_result["report_summary"] = rule_result.get("report_summary", "")
    llm_result["care_plan"] = rule_result.get("care_plan", [])
    llm_result["watch_items"] = rule_result.get("watch_items", [])
    llm_result["self_check_questions"] = rule_result.get("self_check_questions", [])
    llm_result["seek_care_if"] = rule_result.get("seek_care_if", [])
    llm_result["red_flag"] = False
    llm_result["next_recommended_action"] = rule_result.get("next_recommended_action", rule_result["next_question"])
    if not str(llm_result.get("dietary_suggestion", "")).strip():
        llm_result["dietary_suggestion"] = rule_result["dietary_suggestion"]
    if is_weak_next_question(str(llm_result.get("next_question", ""))):
        llm_result["next_question"] = rule_result["next_question"]
    return llm_result


def _urgent_result(mode: str, symptoms: list[str], rule_trace: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": mode,
        "preliminary_assessment": "偵測到可能需要醫療評估的警訊，暫不做一般體質判斷。",
        "possibility_level": "高",
        "possibilities": [],
        "report_summary": "目前描述包含警訊，建議優先接受醫療評估，本系統暫不做一般中醫傾向整理。",
        "care_plan": [],
        "watch_items": [],
        "self_check_questions": [],
        "seek_care_if": ["正在出現胸痛、呼吸困難、意識不清、半邊無力、高燒持續或劇烈疼痛時，請立即就醫或尋求急診協助。"],
        "red_flag": True,
        "supporting_evidence": "使用者描述包含胸痛、呼吸困難、昏厥、高燒持續或劇烈疼痛等警訊之一。",
        "next_question": "請問是否正在出現胸痛、呼吸困難、意識不清或症狀快速惡化？若是，請立即就醫。",
        "dietary_suggestion": "此情況不應以飲食建議取代醫療評估，請先諮詢醫師。",
        "rule_trace": rule_trace,
        "medical_disclaimer": MEDICAL_DISCLAIMER,
    }


def _food_suggestion(pattern: str) -> str:
    suggestions = {
        "氣虛傾向": "可參考溫和、易消化的日常食物，例如白粥、雞蛋、南瓜、山藥類食材與充足水分，避免過度油膩。",
        "陰虛燥熱傾向": "可參考水分較足且清淡的日常食物，例如梨、百合類食材、銀耳、豆腐與溫水，避免辛辣油炸。",
        "肝血不足傾向": "可參考均衡蛋白質與深色蔬菜，例如雞蛋、菠菜、黑芝麻、紅棗作為食材點綴，避免熬夜。",
        "濕困傾向": "可參考清淡、少油、易消化飲食，例如薏仁作為日常食材、冬瓜、青菜，減少甜食與冰飲。",
    }
    return suggestions.get(pattern, "建議先維持清淡、規律、易消化飲食，避免辛辣、油炸與過量冰冷食物。")


def _next_question(symptoms: list[str]) -> str:
    return select_next_question(symptoms)


def _sanitize_result(result: dict[str, Any]) -> dict[str, Any]:
    blocked_terms = ["藥", "處方", "劑量", "治癒", "服用"]
    internal_terms = [
        "rule_trace",
        "Python",
        "baseline 差異資料",
        "mouth_dry_delta",
        "eye_fatigue_delta",
        "cheek_delta",
        "face_delta",
        "null",
        "False",
        "True",
        "{",
        "}",
    ]
    visible_fields = [
        "preliminary_assessment",
        "supporting_evidence",
        "next_question",
        "dietary_suggestion",
    ]
    if any(
        term in str(result.get(field, ""))
        for field in visible_fields
        for term in blocked_terms
    ):
        result["preliminary_assessment"] = "目前僅能提供初步健康參考，不能作為醫療處置建議。"
        result["supporting_evidence"] = "系統偵測到回覆內容可能超出安全範圍，已改以保守說明呈現。"
        result["next_question"] = "如症狀持續或加重，請先諮詢醫師，再補充主要不適與持續時間。"
        result["dietary_suggestion"] = "建議以清淡、規律、易消化的日常飲食為主；任何健康處置決定請先諮詢醫師。"
    for field in visible_fields:
        if any(term in str(result.get(field, "")) for term in internal_terms):
            result[field] = _public_replacement_for(field, result.get("rule_trace", {}))
    result.setdefault("preliminary_assessment", "目前資料不足，僅能提供初步參考。")
    result.setdefault("possibility_level", "低")
    result.setdefault("supporting_evidence", "需要更多症狀資料確認。")
    result.setdefault("next_question", "請補充主要不適、持續時間與嚴重程度。")
    result.setdefault("dietary_suggestion", "建議先維持清淡、規律、易消化飲食。")
    return result


def _finalize_public_result(result: dict[str, Any]) -> dict[str, Any]:
    result.pop("rule_trace", None)
    for field in ["preliminary_assessment", "supporting_evidence", "next_question", "dietary_suggestion"]:
        value = result.get(field, "")
        if isinstance(value, list):
            value = "、".join(str(item) for item in value if item)
        value = str(value or "")
        value = value.replace("初步診斷", "初步判斷")
        value = value.replace("診斷為", "初步偏向")
        value = value.replace("治療計劃", "健康處置")
        result[field] = value
    return result


def _qa_history_from_payload(payload: dict[str, Any]) -> list[dict[str, str]]:
    if payload.get("qa_history"):
        return payload.get("qa_history", [])
    qa_history = []
    chief = payload.get("chief_complaint") or {}
    if isinstance(chief, dict) and chief.get("text"):
        qa_history.append({"question": "主要不適", "answer": str(chief.get("text"))})
    for item in payload.get("ten_questions", []) or []:
        if not isinstance(item, dict):
            continue
        answer = "、".join(str(opt) for opt in item.get("selected_options", []) if opt)
        free_text = str(item.get("free_text", "") or "")
        if free_text:
            answer = f"{answer} {free_text}".strip()
        qa_history.append({"question": str(item.get("question", "")), "answer": answer})
    return qa_history


def _face_delta_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("face_delta"):
        return payload.get("face_delta")
    observation = payload.get("face_observation") or {}
    if not isinstance(observation, dict):
        return None
    features = observation.get("features") if isinstance(observation.get("features"), dict) else {}
    return {
        "baseline_days": payload.get("baseline", {}).get("baseline_days", 0) if isinstance(payload.get("baseline"), dict) else 0,
        "confidence": 0.8 if observation.get("status") == "complete" else 0,
        "mouth_delta": features.get("mouth_delta", 0),
        "eye_fatigue_delta": features.get("eye_fatigue_delta", 0),
        "cheek_delta": features.get("cheek_delta", 0),
    }


def _public_possibility(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "pattern": item.get("pattern", "需要更多資料"),
        "fit_percent": item.get("fit_percent", 28),
        "level": item.get("level", "低"),
        "tcm_explanation": item.get("tcm_explanation", ""),
        "plain_explanation": item.get("plain_explanation", ""),
        "evidence": item.get("evidence", []),
        "lifestyle_suggestion": item.get("lifestyle_suggestion", ""),
        "dietary_suggestion": item.get("food", ""),
        "care_plan": item.get("care_plan", []),
        "watch_items": item.get("watch_items", []),
        "self_check_questions": item.get("self_check_questions", []),
    }


def _build_report_summary(top: dict[str, Any], symptoms: list[str], trace: dict[str, Any]) -> str:
    pattern = top.get("pattern", "需要更多資料")
    evidence = top.get("evidence", [])
    if evidence:
        evidence_text = "、".join(evidence[:4])
        return f"本次資料最符合「{pattern}」的方向，主要依據包括：{evidence_text}。這代表目前可先從相關生活型態、飲食與症狀變化觀察，但仍不能作為正式診斷。"
    if symptoms:
        return "本次資料已有部分症狀線索，但仍不足以形成穩定傾向，建議補充持續時間、嚴重程度與伴隨症狀。"
    return "目前資料不足，建議先補充主要不適、持續時間、嚴重程度與近期生活變化。"


def _seek_care_if() -> list[str]:
    return [
        "症狀快速加重、持續不退，或明顯影響日常生活。",
        "出現胸痛、呼吸困難、意識不清、半邊無力、劇烈疼痛、高燒持續等警訊。",
        "便血、黑便、持續嘔吐、明顯脫水，或腹痛劇烈。",
        "已有慢性病、懷孕、年長者或正在接受醫療處置時，請優先諮詢醫師。",
    ]


def _public_replacement_for(field: str, trace: dict[str, Any]) -> str:
    if field == "supporting_evidence":
        evidence = []
        if trace.get("has_fatigue"):
            evidence.append("有疲倦或精神不足的描述")
        if trace.get("has_dry_mouth") or trace.get("mouth_dry_delta_flag"):
            evidence.append("有口乾或唇周偏乾的觀察")
        if trace.get("has_insomnia"):
            evidence.append("睡眠品質不佳")
        if trace.get("has_dizziness"):
            evidence.append("有頭暈相關描述")
        if trace.get("eye_fatigue_delta_flag"):
            evidence.append("眼周疲勞感較基準明顯")
        if trace.get("cheek_delta_flag"):
            evidence.append("臉部氣色或暗沉變化較明顯")
        return "、".join(evidence) or "目前主要依據使用者問答內容進行初步整理，仍需要更多症狀細節確認。"
    if field == "next_question":
        return "請補充主要不適持續多久、嚴重程度，以及是否有睡眠、食慾或大便狀況改變。"
    if field == "dietary_suggestion":
        return "建議先維持清淡、規律、易消化的日常飲食，避免辛辣、油炸與過量冰冷食物。"
    return "目前僅能提供初步健康參考，建議結合更多問答內容並諮詢專業醫療人員。"
