from __future__ import annotations

from typing import Any

from .guidance import select_next_question
from .knowledge import PATTERNS, RED_FLAG_KEYWORDS, SYMPTOM_KEYWORDS

MEDICAL_DISCLAIMER = "本結果僅供健康參考，不能取代醫師診斷。如有不適或症狀持續，請先諮詢醫師。"

RED_FLAGS = set(RED_FLAG_KEYWORDS)


def infer_symptoms(symptoms: list[str], qa_history: list[dict[str, str]]) -> list[str]:
    found = {str(symptom) for symptom in symptoms if symptom}
    text = " ".join(str(item.get("answer", "")) for item in qa_history or [])
    text += " " + " ".join(str(symptom) for symptom in symptoms or [])
    text_lower = text.lower()
    for canonical, keywords in SYMPTOM_KEYWORDS.items():
        if any(_keyword_present(text_lower, keyword.lower()) for keyword in keywords):
            found.add(canonical)
    return sorted(found)


def build_rule_trace(symptoms: list[str], face_delta: dict[str, Any] | None) -> dict[str, Any]:
    face_delta = face_delta or {}
    trace = {
        "baseline_ready": int(face_delta.get("baseline_days", 0) or 0) >= 15,
        "camera_confidence_ok": float(face_delta.get("confidence", 0) or 0) >= 0.7,
        "mouth_dry_delta_flag": float(face_delta.get("mouth_delta", 0) or 0) <= -0.8,
        "eye_fatigue_delta_flag": float(face_delta.get("eye_fatigue_delta", 0) or 0) >= 0.25,
        "cheek_delta_flag": abs(float(face_delta.get("cheek_delta", 0) or 0)) >= 0.7,
    }
    for symptom in SYMPTOM_KEYWORDS:
        trace[f"has_{symptom}"] = symptom in symptoms
    trace["has_dry_mouth"] = trace["has_dry_mouth"] or "dry mouth" in symptoms
    return trace


def rank_patterns(symptoms: list[str], trace: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    for pattern in PATTERNS:
        evidence = []
        score = 0
        for key, label, weight in pattern["rules"]:
            if trace.get(key):
                evidence.append(label)
                score += weight
        level = _level_from_score(score)
        candidates.append(
            {
                "pattern": pattern["name"],
                "score": score,
                "level": level,
                "evidence": evidence,
                "food": pattern["food"],
            }
        )
    ranked = sorted(candidates, key=lambda item: item["score"], reverse=True)
    visible = [item for item in ranked if item["score"] > 0] or ranked[:1]
    max_score = max((item["score"] for item in visible), default=1) or 1
    for item in visible:
        item["fit_percent"] = min(96, max(28, round((item["score"] / max_score) * 86))) if item["score"] else 28
        item["tcm_explanation"] = _tcm_explanation(item["pattern"])
        item["plain_explanation"] = _plain_explanation(item["pattern"])
        item["lifestyle_suggestion"] = _lifestyle_suggestion(item["pattern"])
        item["care_plan"] = _care_plan(item["pattern"])
        item["watch_items"] = _watch_items(item["pattern"])
        item["self_check_questions"] = _self_check_questions(item["pattern"])
    return visible


def build_public_context(symptoms: list[str], trace: dict[str, Any], ranked: list[dict[str, Any]]) -> dict[str, Any]:
    top = ranked[0] if ranked else {}
    return {
        "symptoms": symptoms,
        "candidate_patterns": [
            {
                "pattern": item["pattern"],
                "level": item["level"],
                "evidence": item["evidence"],
            }
            for item in ranked[:3]
        ],
        "top_pattern": top.get("pattern", "需要更多資料"),
        "top_evidence": top.get("evidence", []),
        "recommended_next_question": select_next_question(symptoms, top.get("pattern")),
        "face_observation_used": bool(
            trace.get("mouth_dry_delta_flag")
            or trace.get("eye_fatigue_delta_flag")
            or trace.get("cheek_delta_flag")
        ),
    }


def contains_red_flags(symptoms: list[str], qa_history: list[dict[str, str]]) -> bool:
    inferred = set(infer_symptoms(symptoms, qa_history))
    return bool(inferred & RED_FLAGS)


def _level_from_score(score: int) -> str:
    if score >= 4:
        return "高"
    if score >= 2:
        return "中"
    return "低"


def _keyword_present(text: str, keyword: str) -> bool:
    start = 0
    while True:
        index = text.find(keyword, start)
        if index == -1:
            return False
        if not _is_negated(text, index):
            return True
        start = index + len(keyword)


def _is_negated(text: str, keyword_index: int) -> bool:
    prefix = text[max(0, keyword_index - 6) : keyword_index]
    negations = ["沒有", "無", "未", "否認", "不會", "不是", "沒有明顯"]
    return any(term in prefix for term in negations)


def _tcm_explanation(pattern: str) -> str:
    mapping = {
        "氣虛傾向": "多與氣的推動、固攝與運化功能偏弱相關。",
        "陰虛燥熱傾向": "多與陰液不足、虛熱偏明顯相關。",
        "肝血不足傾向": "多與血液濡養不足、眼目與睡眠受影響相關。",
        "濕困脾胃傾向": "多與脾胃運化受困、濕重阻滯相關。",
        "腸胃燥結傾向": "多與津液不足或燥熱影響腸道通降相關。",
        "肝鬱氣滯傾向": "多與情志壓力、氣機疏泄不暢，影響胸脅、胃氣與睡眠相關。",
        "食積胃腸傾向": "多與飲食過量、油膩甜食或消化負擔偏重，使胃腸通降受影響相關。",
        "外感風寒傾向": "多與外在寒涼刺激後出現畏寒、鼻塞、咳嗽等表層不適相關。",
        "外感風熱傾向": "多與發熱、咽喉不適、咳嗽與燥熱表現較明顯相關。",
        "心脾兩虛傾向": "多與睡眠、心神安定、食慾與體力恢復互相影響相關。",
    }
    return mapping.get(pattern, "目前資料仍不足，需要更多問答內容確認。")


def _plain_explanation(pattern: str) -> str:
    mapping = {
        "氣虛傾向": "可理解為體力、消化與恢復狀態偏弱，需要確認疲倦、食慾與出汗情況。",
        "陰虛燥熱傾向": "可理解為乾燥、睡眠與燥熱感較明顯，需要確認口乾、盜汗與排便。",
        "肝血不足傾向": "可理解為熬夜、眼睛疲勞、頭暈與睡眠品質互相影響。",
        "濕困脾胃傾向": "可理解為消化負擔、腹脹、身體沉重與大便偏軟較突出。",
        "腸胃燥結傾向": "可理解為排便乾硬、口乾或燥熱感較突出。",
        "肝鬱氣滯傾向": "可理解為壓力與情緒緊繃使胸悶、肋旁脹、胃脹或睡眠受影響。",
        "食積胃腸傾向": "可理解為近期飲食負擔偏重，飯後腹脹、噯氣、反酸或口氣較明顯。",
        "外感風寒傾向": "可理解為像剛受寒或感冒初期的狀態，怕冷、鼻塞、流鼻水或咳嗽較突出。",
        "外感風熱傾向": "可理解為喉嚨痛、發熱、口乾或咳嗽較明顯的外感狀態。",
        "心脾兩虛傾向": "可理解為睡不好、心悸、疲倦與食慾較差互相牽連。",
    }
    return mapping.get(pattern, "目前線索較分散，建議補充主要不適、時間與嚴重程度。")


def _lifestyle_suggestion(pattern: str) -> str:
    mapping = {
        "氣虛傾向": "先規律作息、避免過度勞累，飲食以溫和易消化為主。",
        "陰虛燥熱傾向": "先減少熬夜、辛辣油炸與過度燥熱飲食，補充溫水。",
        "肝血不足傾向": "先減少熬夜與長時間用眼，保持規律睡眠。",
        "濕困脾胃傾向": "先減少冰冷、甜食與油膩，規律少量進食。",
        "腸胃燥結傾向": "先增加溫水、蔬果與活動量，避免久坐與辛辣油炸。",
        "肝鬱氣滯傾向": "先固定作息、安排短時間放鬆呼吸或散步，減少刺激性飲食與過度壓力累積。",
        "食積胃腸傾向": "先減少過飽、宵夜、油炸甜食與酒精，改為少量規律進食。",
        "外感風寒傾向": "先注意保暖、休息與溫水補充，避免再受寒。",
        "外感風熱傾向": "先補充溫水、避免辛辣油炸與熬夜，觀察發熱與喉嚨變化。",
        "心脾兩虛傾向": "先穩定睡眠時間，晚間減少螢幕刺激與過晚進食。",
    }
    return mapping.get(pattern, "先保持清淡、規律、易消化飲食與穩定作息。")


def _care_plan(pattern: str) -> list[str]:
    mapping = {
        "氣虛傾向": [
            "接下來 3-7 天先固定睡眠與用餐時間，避免連續熬夜或過度勞累。",
            "餐食以溫和、易消化、少油膩為主，觀察飯後精神是否改善。",
            "活動量先採輕量散步或伸展，不建議突然增加高強度運動。",
        ],
        "陰虛燥熱傾向": [
            "先降低熬夜、辛辣油炸與過度燥熱飲食，觀察口乾與睡眠是否減輕。",
            "白天分次補充溫水，避免一次大量冰飲。",
            "睡前減少螢幕刺激與過晚進食，記錄夜醒、盜汗或燥熱時段。",
        ],
        "肝血不足傾向": [
            "先把睡眠與用眼時間列為觀察重點，避免長時間連續看螢幕。",
            "每 40-50 分鐘讓眼睛休息，觀察頭暈、眼酸與黑眼圈變化。",
            "飲食保持均衡蛋白質與深色蔬菜，不以單一食物取代正餐。",
        ],
        "濕困脾胃傾向": [
            "接下來幾天先減少冰冷、甜食、油膩與過飽，觀察腹脹與大便型態。",
            "用餐放慢速度，晚餐避免太晚或太多。",
            "若身體沉重明顯，可增加溫和步行，避免久坐不動。",
        ],
        "腸胃燥結傾向": [
            "先增加溫水、蔬菜、水果與全穀類等日常纖維來源。",
            "每天保留固定排便時間，不長時間忍便。",
            "避免連續辛辣油炸、久坐與睡眠不足，觀察排便困難是否改善。",
        ],
        "肝鬱氣滯傾向": [
            "先記錄壓力、情緒與胸悶或腹脹出現的時間，觀察是否和熬夜、緊張或用餐速度有關。",
            "每天安排 10-15 分鐘溫和散步或放鬆呼吸，避免一直憋著情緒與久坐不動。",
            "飲食先減少酒精、過量咖啡、辛辣油炸與暴飲暴食，觀察噯氣或反酸是否下降。",
        ],
        "食積胃腸傾向": [
            "接下來 2-3 天先避免吃太飽、宵夜、油炸甜食與刺激性飲食。",
            "改成少量、慢食、規律用餐，觀察飯後腹脹、反酸與口氣是否改善。",
            "飯後可做溫和步行，避免立刻躺下或長時間久坐。",
        ],
        "外感風寒傾向": [
            "先注意保暖與休息，避免吹風受寒或大量冰冷飲食。",
            "補充溫水並觀察鼻塞、流鼻水、咳嗽與體溫變化。",
            "若發燒持續、喘、胸悶或精神明顯變差，請儘快就醫。",
        ],
        "外感風熱傾向": [
            "先補充溫水、休息，避免熬夜與辛辣油炸刺激。",
            "觀察喉嚨痛、咳嗽、痰色、體溫與精神狀態是否加重。",
            "若高燒不退、呼吸困難、胸痛或症狀快速惡化，請立即就醫。",
        ],
        "心脾兩虛傾向": [
            "先固定睡眠與用餐時間，避免晚間過度用腦、滑手機或過晚進食。",
            "白天活動量以溫和散步與伸展為主，觀察心悸與疲倦是否下降。",
            "飲食保持均衡蛋白質與蔬菜，不以甜食、咖啡或提神飲取代正餐。",
        ],
    }
    return mapping.get(pattern, ["先規律作息、清淡飲食，並記錄症狀變化。"])


def _watch_items(pattern: str) -> list[str]:
    mapping = {
        "氣虛傾向": ["疲倦是否休息後改善", "食慾與飯後精神", "是否容易出汗或頭暈"],
        "陰虛燥熱傾向": ["口乾程度", "夜醒或盜汗", "大便是否偏乾", "燥熱出現時段"],
        "肝血不足傾向": ["眼睛疲勞", "頭暈頻率", "睡眠品質", "心悸或心慌"],
        "濕困脾胃傾向": ["腹脹程度", "大便是否成形", "身體沉重", "飯後不適"],
        "腸胃燥結傾向": ["排便間隔", "大便乾硬程度", "口乾", "腹部不適程度"],
        "肝鬱氣滯傾向": ["胸悶或脅肋脹", "壓力與情緒波動", "噯氣或反酸", "睡眠是否受影響"],
        "食積胃腸傾向": ["飯後腹脹", "噯氣反酸", "口氣或口苦", "是否吃太飽或宵夜"],
        "外感風寒傾向": ["怕冷程度", "鼻塞流鼻水", "咳嗽變化", "體溫與精神狀態"],
        "外感風熱傾向": ["喉嚨痛", "發熱或發燒", "咳嗽與痰", "口乾與精神狀態"],
        "心脾兩虛傾向": ["入睡與夜醒", "心悸或心慌", "疲倦程度", "食慾與飯後精神"],
    }
    return mapping.get(pattern, ["主要不適是否變化", "持續時間", "嚴重程度"])


def _self_check_questions(pattern: str) -> list[str]:
    mapping = {
        "氣虛傾向": ["這種疲倦是否已持續超過兩週？", "是否伴隨明顯頭暈、心悸或體重變化？"],
        "陰虛燥熱傾向": ["口乾是否夜間更明顯？", "是否同時有盜汗、便秘或睡眠惡化？"],
        "肝血不足傾向": ["頭暈是否和熬夜、用眼或月經週期有關？", "是否出現視力突然變化？"],
        "濕困脾胃傾向": ["腹脹是否在飯後或吃冰冷甜食後加重？", "大便不成形是否已持續多日？"],
        "腸胃燥結傾向": ["便秘是否伴隨劇烈腹痛、嘔吐或血便？", "是否已多日無法順利排便？"],
        "肝鬱氣滯傾向": ["胸悶或胃脹是否在壓力大、情緒緊繃或飯後更明顯？", "是否同時有胸痛、呼吸困難或症狀快速惡化？"],
        "食積胃腸傾向": ["腹脹是否和吃太飽、油膩、宵夜或刺激性食物有關？", "是否伴隨持續嘔吐、黑便、血便或劇烈腹痛？"],
        "外感風寒傾向": ["是否有發燒持續、喘、胸悶或精神明顯變差？", "鼻塞流鼻水或咳嗽是否快速加重？"],
        "外感風熱傾向": ["是否高燒不退、呼吸困難、胸痛或意識不清？", "喉嚨痛與咳嗽是否快速惡化？"],
        "心脾兩虛傾向": ["心悸是否伴隨胸痛、呼吸困難或昏厥感？", "睡眠與疲倦是否已影響日常工作或學習？"],
    }
    return mapping.get(pattern, ["症狀是否持續加重？", "是否有任何和平常不同的異常變化？"])
