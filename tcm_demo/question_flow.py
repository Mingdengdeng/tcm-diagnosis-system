from __future__ import annotations

from typing import Any

RED_FLAG_OPTIONS = ["沒有上述情況", "胸痛", "呼吸困難", "高燒持續", "昏厥/意識不清", "半邊無力/說話不清", "劇烈疼痛"]

REASON_LABELS = {
    "red_flag": "先確認是否有需要立即就醫的警訊",
    "digestive_detail": "正在確認腸胃位置、飯前飯後與排便關係",
    "duration": "正在確認症狀出現時間與變化速度",
    "severity": "正在確認不舒服的程度",
    "cold_heat": "正在確認寒熱、口乾與夜間出汗",
    "sweat": "正在確認出汗狀態",
    "head_body": "正在確認頭身沉重、痠痛與疲勞",
    "fatigue_detail": "正在確認疲倦型態與活動後變化",
    "appetite": "正在確認食慾、消化與飯後脹氣",
    "diet_trigger": "正在確認飲食刺激是否加重不適",
    "mouth_throat": "正在確認口腔、咽喉與嘴周狀態",
    "bowel_urine": "正在確認大便與小便變化",
    "sleep": "正在確認睡眠品質",
    "emotion": "正在確認壓力與情緒狀態",
    "external_detail": "正在確認外感、鼻喉與咳嗽變化",
    "chest_emotion_detail": "正在確認胸悶、壓力與胃氣變化",
    "pain_detail": "正在確認疼痛位置、性質與加重緩解",
    "menstruation": "依年齡與性別確認月經相關變化",
    "history": "正在確認既往病史與近期用藥",
}

TEN_QUESTIONS = [
    {
        "id": "red_flag",
        "category": "red_flag",
        "question": "目前是否有胸痛、呼吸困難、高燒持續、昏厥、意識不清、半邊無力或劇烈疼痛？",
        "answer_type": "multi_choice",
        "options": RED_FLAG_OPTIONS,
        "targets": ["all"],
    },
    {
        "id": "digestive_detail",
        "category": "appetite",
        "question": "腹脹、腹痛或胃部不適主要在哪裡？和飯前飯後、壓力或排便有關嗎？",
        "answer_type": "free_text",
        "options": [],
        "targets": ["digestive"],
    },
    {
        "id": "duration",
        "category": "duration",
        "question": "主要不適大約持續多久？是突然出現，還是慢慢變明顯？",
        "answer_type": "single_choice",
        "options": ["今天突然", "1-3 天", "一週內", "1-2 週", "超過一個月", "逐漸變明顯"],
        "targets": ["all"],
    },
    {
        "id": "severity",
        "category": "pain",
        "question": "目前不適程度若以 1 到 10 分表示，大約是幾分？",
        "answer_type": "scale",
        "options": [str(i) for i in range(1, 11)],
        "targets": ["pain", "digestive", "all"],
    },
    {
        "id": "cold_heat",
        "category": "cold_heat",
        "question": "最近比較怕冷、怕熱、口乾，或有夜間出汗嗎？",
        "answer_type": "multi_choice",
        "options": ["怕冷", "怕熱/燥熱", "口乾", "夜間出汗", "沒有明顯"],
        "targets": ["dry", "sleep", "fatigue", "digestive", "all"],
    },
    {
        "id": "sweat",
        "category": "sweat",
        "question": "最近出汗情況如何？",
        "answer_type": "single_choice",
        "options": ["正常", "容易出汗", "夜間出汗", "幾乎不出汗", "不確定"],
        "targets": ["fatigue", "dry", "all"],
    },
    {
        "id": "head_body",
        "category": "head_body",
        "question": "是否有頭暈、頭重、身體沉重、眼睛疲勞或肢體痠痛？",
        "answer_type": "multi_choice",
        "options": ["頭暈", "頭重", "身體沉重", "眼睛疲勞", "痠痛", "沒有明顯"],
        "targets": ["fatigue", "sleep", "digestive", "pain", "all"],
    },
    {
        "id": "fatigue_detail",
        "category": "head_body",
        "question": "疲倦比較像整天沒力、醒來仍累、活動後加重，還是伴隨頭暈或心悸？",
        "answer_type": "multi_choice",
        "options": ["整天沒力", "醒來仍累", "活動後加重", "頭暈", "心悸", "沒有明顯"],
        "targets": ["fatigue"],
    },
    {
        "id": "appetite",
        "category": "appetite",
        "question": "最近食慾、飯後脹氣或消化狀況如何？",
        "answer_type": "multi_choice",
        "options": ["胃口正常", "胃口差", "飯後脹", "吃不下", "油膩後加重"],
        "targets": ["digestive", "fatigue", "all"],
    },
    {
        "id": "diet_trigger",
        "category": "appetite",
        "question": "最近是否常吃辛辣、油炸、燒烤、甜食、冰飲或酒類？吃完後不適是否加重？",
        "answer_type": "multi_choice",
        "options": ["辛辣", "油炸/燒烤", "甜食", "冰飲", "酒類", "吃完會加重", "沒有明顯"],
        "targets": ["digestive", "dry", "all"],
    },
    {
        "id": "mouth_throat",
        "category": "mouth",
        "question": "嘴唇、口腔、牙齦、喉嚨或下巴附近最近是否有紅、乾、痛、破、痘痘或不適？",
        "answer_type": "multi_choice",
        "options": ["嘴唇乾裂", "口腔破/痛", "牙齦不適", "喉嚨不適", "下巴痘痘/紅痕", "沒有明顯"],
        "targets": ["digestive", "dry", "sleep", "all"],
    },
    {
        "id": "external_detail",
        "category": "external",
        "question": "最近是否有鼻塞、流鼻水、喉嚨痛、咳嗽、發冷或發熱？哪一個最明顯？",
        "answer_type": "multi_choice",
        "options": ["鼻塞/流鼻水", "喉嚨痛", "咳嗽", "發冷/畏寒", "發熱/發燒", "沒有明顯"],
        "targets": ["external", "all"],
    },
    {
        "id": "bowel_urine",
        "category": "bowel_urine",
        "question": "最近大便與小便情況如何？",
        "answer_type": "multi_choice",
        "options": ["大便正常", "便秘/偏乾", "偏軟不成形", "腹瀉", "小便偏黃", "夜尿變多"],
        "targets": ["digestive", "dry", "all"],
    },
    {
        "id": "sleep",
        "category": "sleep",
        "question": "最近睡眠品質如何？",
        "answer_type": "multi_choice",
        "options": ["睡眠正常", "難入睡", "夜醒", "多夢", "醒後疲倦"],
        "targets": ["sleep", "dry", "fatigue", "all"],
    },
    {
        "id": "emotion",
        "category": "emotion",
        "question": "最近精神、壓力與情緒狀態如何？",
        "answer_type": "multi_choice",
        "options": ["精神尚可", "壓力大", "焦慮", "煩躁易怒", "情緒低落"],
        "targets": ["sleep", "pain", "fatigue", "digestive", "all"],
    },
    {
        "id": "chest_emotion_detail",
        "category": "emotion",
        "question": "胸悶、胃脹或不舒服是否會在壓力大、情緒緊繃、吃太快或飯後更明顯？",
        "answer_type": "multi_choice",
        "options": ["壓力大時明顯", "飯後明顯", "吃太快會加重", "常噯氣/反酸", "和情緒無關", "不確定"],
        "targets": ["emotion", "digestive", "all"],
    },
    {
        "id": "pain_detail",
        "category": "pain",
        "question": "如果有疼痛，位置、性質與加重/緩解因素比較接近哪一種？",
        "answer_type": "multi_choice",
        "options": ["沒有疼痛", "固定位置痛", "腹痛", "刺痛", "隱隱作痛", "活動後加重", "休息後緩解"],
        "targets": ["pain", "digestive", "all"],
    },
    {
        "id": "menstruation",
        "category": "menstruation",
        "question": "近期月經週期、經量或經痛是否和平常不同？",
        "answer_type": "single_choice",
        "options": ["無明顯不同", "週期不規律", "經量改變", "經痛明顯", "不適用"],
        "targets": ["female"],
    },
    {
        "id": "history",
        "category": "history",
        "question": "是否有已知慢性病、近期就醫，或正在使用藥物？若有，請簡單說明。",
        "answer_type": "free_text",
        "options": [],
        "targets": ["all"],
    },
]


TRACK_ORDERS = {
    "digestive": ["digestive_detail", "appetite", "bowel_urine", "diet_trigger", "cold_heat", "mouth_throat", "sleep", "emotion", "severity", "duration", "history"],
    "pain": ["pain_detail", "severity", "head_body", "duration", "cold_heat", "emotion", "sleep", "history"],
    "sleep": ["sleep", "cold_heat", "emotion", "head_body", "mouth_throat", "bowel_urine", "duration", "history"],
    "fatigue": ["fatigue_detail", "head_body", "appetite", "sleep", "sweat", "cold_heat", "emotion", "duration", "history"],
    "dry": ["cold_heat", "mouth_throat", "bowel_urine", "sleep", "diet_trigger", "sweat", "emotion", "duration", "history"],
    "external": ["external_detail", "cold_heat", "mouth_throat", "head_body", "duration", "severity", "history"],
    "emotion": ["chest_emotion_detail", "emotion", "sleep", "appetite", "digestive_detail", "cold_heat", "duration", "history"],
    "all": ["duration", "severity", "cold_heat", "head_body", "appetite", "bowel_urine", "sleep", "emotion", "history"],
}


def initial_question_context(profile: dict[str, Any], chief_text: str, user_type: str, baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        "track": _track_from_text(chief_text),
        "user_type": user_type,
        "sex": str(profile.get("sex") or "unspecified"),
        "age": profile.get("age"),
        "baseline_ready": baseline.get("status") == "ready" or int(baseline.get("baseline_days", 0) or 0) >= 15,
        "face_hints": [],
    }


def select_question(
    profile: dict[str, Any],
    chief_text: str,
    answers: list[dict[str, Any]],
    symptoms: list[str],
    user_type: str = "new",
    baseline: dict[str, Any] | None = None,
    face_observation: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    baseline = baseline or {}
    face_observation = face_observation or {}
    answered = {item.get("question_id") for item in answers}
    context = initial_question_context(profile, chief_text, user_type, baseline)
    context["face_hints"] = _face_hints(face_observation)
    target_questions = _target_question_count(user_type)
    if len(answers) >= target_questions:
        return None

    red_flag = _question_by_id("red_flag")
    if red_flag and "red_flag" not in answered:
        return _decorate_question(_contextual_red_flag(red_flag, context["track"]), context)

    if len(answers) >= 5 and "menstruation" not in answered:
        question = _question_by_id("menstruation")
        if question and _question_applies(question, context):
            return _decorate_question(question, context)

    ordered_ids = _question_order(context)
    for question_id in ordered_ids:
        question = _question_by_id(question_id)
        if question and question["id"] not in answered and _question_applies(question, context):
            return _decorate_question(question, context)

    fallback = _fallback_unanswered_question(answered, context) if len(answers) < target_questions else None
    return _decorate_question(fallback, context) if fallback else None


def progress_label(answers: list[dict[str, Any]], user_type: str) -> str:
    total = _target_question_count(user_type)
    return f"已完成 {min(len(answers), total)} / 約 {total} 題"


def _target_question_count(user_type: str) -> int:
    return 5 if user_type.startswith("returning") else 7


def _contextual_red_flag(question: dict[str, Any], track: str) -> dict[str, Any]:
    variants = {
        "digestive": "目前腹痛或腸胃不適是否伴隨劇烈疼痛、持續嘔吐、黑便/血便、高燒、脫水或意識不清？",
        "pain": "目前疼痛是否突然劇烈，或伴隨胸痛、呼吸困難、半邊無力、說話不清、昏厥或意識不清？",
        "sleep": "目前是否有胸痛、呼吸困難、昏厥、意識不清、持續高燒，或症狀快速惡化？",
        "fatigue": "目前疲倦無力是否伴隨胸痛、呼吸困難、昏厥、半邊無力、說話不清或高燒持續？",
        "dry": "目前口乾燥熱是否伴隨高燒持續、意識不清、呼吸困難、胸痛或症狀快速惡化？",
        "external": "目前是否有高燒持續、呼吸困難、胸痛、意識不清、症狀快速惡化，或精神狀態明顯變差？",
        "emotion": "目前胸悶或不舒服是否伴隨胸痛、呼吸困難、昏厥、半邊無力、說話不清或症狀快速惡化？",
    }
    contextual = dict(question)
    contextual["question"] = variants.get(track, question["question"])
    return contextual


def _decorate_question(question: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    decorated = dict(question)
    decorated["track"] = context.get("track", "all")
    decorated["reason_label"] = REASON_LABELS.get(decorated.get("id"), "正在依照目前描述選擇下一個確認方向")
    return decorated


def _question_order(context: dict[str, Any]) -> list[str]:
    priorities: list[str] = []
    priorities.extend(_priority_question_ids(context["face_hints"]))
    priorities.extend(TRACK_ORDERS.get(context["track"], TRACK_ORDERS["all"]))
    if context.get("baseline_ready"):
        priorities.insert(0, "duration")
    return list(dict.fromkeys(item for item in priorities if item != "red_flag"))


def _question_applies(question: dict[str, Any], context: dict[str, Any]) -> bool:
    targets = question.get("targets", [])
    if "female" in targets:
        return context["sex"] in {"female", "女"} and _age_in_menstrual_range(context.get("age"))
    return "all" in targets or context["track"] in targets


def _track_from_text(text: str) -> str:
    if any(term in text for term in ["腹", "胃", "大便", "腹瀉", "腹泻", "便秘", "脹", "胀", "食慾", "食欲", "胃口", "肚子"]):
        return "digestive"
    if any(term in text for term in ["睡", "失眠", "夜醒", "多夢", "多梦"]):
        return "sleep"
    if any(term in text for term in ["口乾", "口干", "燥熱", "燥热", "盜汗", "盗汗", "上火"]):
        return "dry"
    if any(term in text for term in ["咳", "咳嗽", "喉嚨", "喉咙", "鼻塞", "流鼻水", "鼻涕", "發燒", "发烧", "發熱", "发热", "畏寒", "發冷", "发冷"]):
        return "external"
    if any(term in text for term in ["壓力", "压力", "焦慮", "焦虑", "煩躁", "烦躁", "易怒", "胸悶", "胸闷", "常嘆氣", "叹气", "情緒", "情绪"]):
        return "emotion"
    if any(term in text for term in ["痛", "痠", "酸", "疼", "頭痛", "头痛"]):
        return "pain"
    if any(term in text for term in ["累", "疲", "沒力", "没力", "無力", "无力", "頭暈", "头晕", "沉重"]):
        return "fatigue"
    return "all"


def _face_hints(face_observation: dict[str, Any]) -> list[str]:
    hints = face_observation.get("routing_hints")
    if isinstance(hints, list) and hints:
        return [str(item) for item in hints if str(item).strip()]
    derived: list[str] = []
    roi_signals = face_observation.get("roi_signals")
    if not isinstance(roi_signals, list):
        return []
    for signal in roi_signals:
        if not isinstance(signal, dict):
            continue
        status = str(signal.get("status") or "")
        if status not in {"slight_redness", "obvious_redness"}:
            continue
        ratio = _safe_float(signal.get("red_area_ratio"))
        if ratio < 0.08:
            continue
        roi_id = str(signal.get("roi_id") or "").lower()
        label = str(signal.get("label") or "")
        if "st" in roi_id or "stomach" in roi_id or "胃" in label:
            derived.extend(["digestive", "mouth", "diet_stimulation", "sleep_stress"])
        if "cv" in roi_id or "conception" in roi_id or "任脈" in label:
            derived.extend(["mouth_chin", "sleep_stress", "fatigue"])
    return list(dict.fromkeys(derived))


def _priority_question_ids(hints: list[str]) -> list[str]:
    priorities: list[str] = []
    if any(hint in hints for hint in ["digestive", "diet_stimulation"]):
        priorities.extend(["appetite", "diet_trigger", "mouth_throat", "bowel_urine", "cold_heat"])
    if any(hint in hints for hint in ["mouth", "mouth_chin", "sleep_stress", "fatigue"]):
        priorities.extend(["mouth_throat", "sleep", "emotion", "head_body"])
    return list(dict.fromkeys(priorities))


def _question_by_id(question_id: str) -> dict[str, Any] | None:
    for question in TEN_QUESTIONS:
        if question["id"] == question_id:
            return question
    return None


def _fallback_unanswered_question(answered: set[Any], context: dict[str, Any]) -> dict[str, Any] | None:
    for question in TEN_QUESTIONS:
        if question["id"] in answered:
            continue
        if "female" in question.get("targets", []) and not _question_applies(question, context):
            continue
        if _question_applies(question, context):
            return question
    return None


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _age_in_menstrual_range(age: Any) -> bool:
    try:
        value = int(age)
    except (TypeError, ValueError):
        return False
    return 12 <= value <= 55
