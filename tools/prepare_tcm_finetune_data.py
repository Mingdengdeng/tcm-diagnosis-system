from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tcm_demo.knowledge_sources import (
    commercial_safe_source_summary,
    get_source_policy,
    is_commercial_safe_source,
)


SYSTEM_PROMPT = """你是中醫健康問答助理。請使用繁體中文。只提供初步健康參考，不取代醫師診斷。不可提供藥物、處方、劑量、方劑、針灸或治療保證。若有胸痛、呼吸困難、高燒持續、昏厥、意識不清或劇烈疼痛，應優先建議儘快就醫。請只輸出指定 JSON。"""

FORBIDDEN_PATTERNS = [
    r"服用",
    r"用藥",
    r"藥物",
    r"中藥",
    r"方劑",
    r"處方",
    r"劑量",
    r"每日\d",
    r"針灸",
    r"治療",
    r"治癒",
    r"痊癒",
]

RED_FLAG_PATTERNS = [
    r"胸痛",
    r"呼吸困難",
    r"喘不過氣",
    r"高燒",
    r"昏厥",
    r"昏倒",
    r"意識不清",
    r"劇烈疼痛",
]

KEYWORD_TO_PATTERN = [
    (["口乾", "燥熱", "睡不好", "失眠", "盜汗"], "陰虛燥熱傾向"),
    (["疲倦", "沒力", "無力", "食慾差", "頭暈"], "氣虛傾向"),
    (["腹脹", "脹氣", "身體沉重", "胃口差"], "濕困傾向"),
    (["眼睛疲勞", "頭暈", "睡眠不好"], "肝血不足傾向"),
    (["怕冷", "手腳冷"], "陽氣不足傾向"),
]

SIMPLIFIED_TO_TRADITIONAL = str.maketrans(
    {
        "诊": "診",
        "断": "斷",
        "药": "藥",
        "处": "處",
        "剂": "劑",
        "疗": "療",
        "气": "氣",
        "虚": "虛",
        "湿": "濕",
        "热": "熱",
        "阴": "陰",
        "阳": "陽",
        "脏": "臟",
        "问": "問",
        "答": "答",
        "饮": "飲",
        "医": "醫",
        "师": "師",
        "脸": "臉",
        "数": "數",
        "据": "據",
        "觉": "覺",
        "轻": "輕",
        "严": "嚴",
        "续": "續",
        "质": "質",
        "议": "議",
        "议": "議",
        "说": "說",
        "这": "這",
        "个": "個",
        "为": "為",
        "与": "與",
        "体": "體",
        "会": "會",
        "应": "應",
        "尽": "儘",
        "见": "見",
        "议": "議",
    }
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize TCM instruction data for safe JSON-only fine-tuning.")
    parser.add_argument("--input", required=True, help="Input JSON/JSONL file from raw dataset.")
    parser.add_argument("--output", required=True, help="Output JSONL file for chat fine-tuning.")
    parser.add_argument("--source", default="chatmed_tcm", help="Dataset source label.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max records to write.")
    parser.add_argument("--allow-risky-source", action="store_true", help="Mark non-commercial/research source as intentionally accepted.")
    parser.add_argument("--list-commercial-safe-sources", action="store_true", help="Print approved free commercial-use sources and exit.")
    args = parser.parse_args()

    if args.list_commercial_safe_sources:
        print(json.dumps(commercial_safe_source_summary(), ensure_ascii=False, indent=2))
        return

    if not args.allow_risky_source and not is_commercial_safe_source(args.source):
        policy = get_source_policy(args.source)
        known = ", ".join(item["key"] for item in commercial_safe_source_summary())
        detail = f"{policy.license} / {policy.notes}" if policy else "unknown source"
        raise SystemExit(
            f"Source '{args.source}' is not approved for free commercial use by default: {detail}. "
            f"Use one of: {known}. Or pass --allow-risky-source for internal research only."
        )

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    raw_records = load_records(input_path)
    stats = {"read": 0, "written": 0, "filtered": 0}

    with output_path.open("w", encoding="utf-8") as writer:
        for record in raw_records:
            stats["read"] += 1
            example = normalize_record(record, args.source, args.allow_risky_source)
            if not example:
                stats["filtered"] += 1
                continue
            writer.write(json.dumps(example, ensure_ascii=False) + "\n")
            stats["written"] += 1
            if args.limit and stats["written"] >= args.limit:
                break

    print(json.dumps({"output": str(output_path), **stats}, ensure_ascii=False, indent=2))


def load_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "train", "examples"):
            if isinstance(data.get(key), list):
                return data[key]
    raise ValueError(f"Unsupported dataset shape: {path}")


def normalize_record(record: dict[str, Any], source: str, risky_source: bool) -> dict[str, Any] | None:
    if not risky_source and not is_commercial_safe_source(source):
        return None
    user_text = extract_user_text(record)
    assistant_text = extract_assistant_text(record)
    combined = to_traditional(f"{user_text}\n{assistant_text}")
    if not user_text or not assistant_text:
        return None
    if contains_forbidden(combined):
        return None

    user_text = to_traditional(user_text)
    assistant_text = to_traditional(assistant_text)
    target = build_safe_target(user_text, assistant_text)
    target_json = json.dumps(target, ensure_ascii=False)
    if contains_forbidden(target_json):
        return None

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": target_json},
        ],
        "metadata": {
            "source": source,
            "source_license": get_source_policy(source).license if get_source_policy(source) else "unknown",
            "policy": "no_medicine_no_prescription",
            "commercial_risk": risky_source,
        },
    }


def extract_user_text(record: dict[str, Any]) -> str:
    for key in ("instruction", "input", "question", "query", "prompt", "user"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    conversations = record.get("conversations") or record.get("messages")
    if isinstance(conversations, list):
        parts = []
        for item in conversations:
            if not isinstance(item, dict):
                continue
            role = item.get("role") or item.get("from")
            value = item.get("content") or item.get("value")
            if role in {"user", "human"} and isinstance(value, str):
                parts.append(value.strip())
        return "\n".join(parts)
    return ""


def extract_assistant_text(record: dict[str, Any]) -> str:
    for key in ("output", "answer", "response", "assistant"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    conversations = record.get("conversations") or record.get("messages")
    if isinstance(conversations, list):
        parts = []
        for item in conversations:
            if not isinstance(item, dict):
                continue
            role = item.get("role") or item.get("from")
            value = item.get("content") or item.get("value")
            if role in {"assistant", "gpt"} and isinstance(value, str):
                parts.append(value.strip())
        return "\n".join(parts)
    return ""


def build_safe_target(user_text: str, assistant_text: str) -> dict[str, str]:
    if is_red_flag(user_text):
        return {
            "preliminary_assessment": "目前描述包含可能需要醫療評估的警訊，建議優先儘快就醫或諮詢醫師。",
            "possibility_level": "高",
            "supporting_evidence": "使用者描述中出現胸痛、呼吸困難、高燒持續、昏厥、意識不清或劇烈疼痛等警訊。",
            "next_question": "請確認是否正在出現胸痛、呼吸困難、意識不清或症狀快速惡化；若是，請立即就醫。",
            "dietary_suggestion": "此情況不應以飲食建議取代醫療評估，請先諮詢醫師。",
        }

    pattern = infer_pattern(user_text + "\n" + assistant_text)
    evidence = summarize_evidence(user_text + "\n" + assistant_text)
    return {
        "preliminary_assessment": f"初步整理較偏向「{pattern}」，仍需要結合更多問答內容確認。",
        "possibility_level": "中",
        "supporting_evidence": evidence,
        "next_question": "請補充症狀持續多久、嚴重程度，以及睡眠、食慾與大便狀況是否改變。",
        "dietary_suggestion": "建議先維持清淡、規律、易消化的日常飲食，避免辛辣、油炸與過量冰冷食物。",
    }


def to_traditional(text: str) -> str:
    return text.translate(SIMPLIFIED_TO_TRADITIONAL)


def contains_forbidden(text: str) -> bool:
    return any(re.search(pattern, text) for pattern in FORBIDDEN_PATTERNS)


def is_red_flag(text: str) -> bool:
    return any(re.search(pattern, text) for pattern in RED_FLAG_PATTERNS)


def infer_pattern(text: str) -> str:
    for keywords, pattern in KEYWORD_TO_PATTERN:
        if sum(keyword in text for keyword in keywords) >= 1:
            return pattern
    return "需要更多資料"


def summarize_evidence(text: str) -> str:
    evidence = []
    for keyword in ["疲倦", "口乾", "失眠", "睡不好", "頭暈", "腹脹", "怕冷", "手腳冷", "眼睛疲勞"]:
        if keyword in text:
            evidence.append(f"提到{keyword}")
    return "、".join(evidence[:4]) or "目前描述較模糊，主要依據使用者問答內容做初步整理。"


if __name__ == "__main__":
    main()
