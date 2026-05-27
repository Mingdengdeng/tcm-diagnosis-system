from __future__ import annotations


RED_FLAG_SYMPTOMS = {
    "chest_pain",
    "breath_shortness",
    "fainting",
    "high_fever",
    "severe_pain",
    "neurologic",
}


PATTERN_FOLLOW_UPS = {
    "氣虛傾向": [
        ("duration", "這種疲倦或沒力大約持續多久了？休息後是否會明顯改善？"),
        ("appetite", "最近食慾、飯量與飯後精神狀況如何？"),
        ("sleep", "最近睡眠是否足夠，白天是否仍容易疲倦？"),
    ],
    "陰虛燥熱傾向": [
        ("duration", "口乾或燥熱感大約持續多久？白天或夜間哪個時段較明顯？"),
        ("sleep", "最近是否難入睡、夜醒、多夢，或夜間容易出汗？"),
        ("bowel", "大便是否偏乾，排便是否比平常困難？"),
    ],
    "肝血不足傾向": [
        ("sleep", "最近睡眠品質、熬夜情況與眼睛疲勞程度如何？"),
        ("duration", "頭暈或眼睛疲勞大約持續多久，是否與用眼或熬夜有關？"),
        ("severity", "頭暈或心悸若以 1 到 10 分表示，大約是幾分？"),
    ],
    "濕困脾胃傾向": [
        ("bowel", "最近大便是偏軟、不成形，還是次數變多？"),
        ("appetite", "胃口、飯後脹氣，以及吃冰冷或甜食後的變化如何？"),
        ("duration", "腹脹、身體沉重或胃口差大約持續多久了？"),
    ],
    "腸胃燥結傾向": [
        ("bowel", "便秘大約幾天一次？大便是否乾硬，排便是否費力？"),
        ("temperature", "是否同時有口乾、燥熱感，或最近辛辣油炸吃得較多？"),
        ("severity", "腹部不適若以 1 到 10 分表示，大約是幾分？"),
    ],
}


GENERAL_FOLLOW_UPS = [
    ("red_flag", "是否有胸痛、呼吸困難、高燒持續、昏厥、意識不清或劇烈疼痛？"),
    ("duration", "這些不適大約持續多久了？是突然出現還是慢慢變明顯？"),
    ("severity", "目前不適程度若以 1 到 10 分表示，大約是幾分？"),
    ("sleep", "最近睡眠品質、入睡與夜醒情況如何？"),
    ("bowel", "最近大便型態、頻率與腹脹情況如何？"),
    ("trigger", "是否有讓症狀明顯加重或緩解的因素，例如熬夜、壓力、飲食或活動？"),
]


MISSING_SIGNAL_BY_KEY = {
    "red_flag": RED_FLAG_SYMPTOMS,
    "duration": {"duration"},
    "severity": {"severity"},
    "sleep": {"sleep", "insomnia"},
    "bowel": {"bowel", "constipation", "loose_stool"},
    "temperature": {"cold", "heat", "dry_mouth", "night_sweat"},
    "appetite": {"poor_appetite", "bloating"},
    "trigger": set(),
}


def select_next_question(symptoms: list[str], pattern: str | None = None) -> str:
    symptom_set = set(symptoms)
    if symptom_set & RED_FLAG_SYMPTOMS:
        return "請確認是否正在出現胸痛、呼吸困難、意識不清或症狀快速惡化；若是，請立即就醫。"

    for key, question in PATTERN_FOLLOW_UPS.get(pattern or "", []):
        if _is_missing(key, symptom_set):
            return question

    for key, question in GENERAL_FOLLOW_UPS:
        if _is_missing(key, symptom_set):
            return question
    return GENERAL_FOLLOW_UPS[-1][1]


def _is_missing(key: str, symptom_set: set[str]) -> bool:
    expected = MISSING_SIGNAL_BY_KEY.get(key, set())
    return not expected or not bool(symptom_set & expected)


def is_weak_next_question(question: str) -> bool:
    text = question.strip()
    if len(text) < 8:
        return True
    weak_terms = ["更多資料", "補充資料", "其他症狀", "還有什麼", "請補充"]
    return any(term in text for term in weak_terms)
