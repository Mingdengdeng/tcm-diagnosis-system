from tcm_demo.question_flow import select_question


def test_digestive_chief_complaint_prioritizes_digestive_questions_after_basics():
    profile = {"sex": "male", "age": 40}
    chief = "肚子脹，胃口差，大便不成形。"
    answers = [
        {"question_id": "red_flag"},
        {"question_id": "duration"},
        {"question_id": "severity"},
    ]

    question = select_question(profile, chief, answers, ["bloating", "poor_appetite"], "new_user", {})

    assert question is not None
    assert question["id"] in {"digestive_detail", "cold_heat", "head_body", "appetite", "bowel_urine"}
    assert question["track"] == "digestive"
    assert question["reason_label"]


def test_female_relevant_age_can_receive_menstruation_question():
    profile = {"sex": "female", "age": 32}
    chief = "睡不好，頭暈，最近容易疲倦。"
    answered = [{"question_id": item} for item in [
        "red_flag",
        "duration",
        "severity",
        "cold_heat",
        "sweat",
        "head_body",
    ]]

    question = select_question(profile, chief, answered, ["fatigue", "insomnia"], "new_user", {})

    assert question["id"] == "menstruation"


def test_face_roi_stomach_redness_prioritizes_digestive_follow_up():
    profile = {"sex": "male", "age": 36}
    chief = "最近有點疲倦，但說不太清楚哪裡不舒服。"
    answers = [
        {"question_id": "red_flag"},
        {"question_id": "duration"},
        {"question_id": "severity"},
    ]
    face_observation = {
        "status": "complete",
        "baseline_used": True,
        "roi_signals": [
            {
                "roi_id": "ST_stomach",
                "label": "足陽明胃經參考 ROI",
                "shift": -2.51,
                "red_area_ratio": 0.1758,
                "status": "obvious_redness",
            }
        ],
    }

    question = select_question(profile, chief, answers, ["fatigue"], "new_user", {}, face_observation)

    assert question is not None
    assert question["id"] == "appetite"


def test_question_flow_does_not_end_before_minimum_questions():
    profile = {"sex": "male", "age": 36}
    chief = "我覺得頭有點痛。"
    answered = [{"question_id": item} for item in [
        "red_flag",
        "duration",
        "severity",
        "pain_detail",
        "cold_heat",
        "sweat",
    ]]

    question = select_question(profile, chief, answered, ["pain"], "new_user", {})

    assert question is not None


def test_new_user_question_flow_stops_at_seven_questions():
    profile = {"sex": "male", "age": 36}
    chief = "我覺得頭有點痛。"
    answered = [{"question_id": item} for item in [
        "red_flag",
        "duration",
        "severity",
        "pain_detail",
        "cold_heat",
        "sweat",
        "head_body",
    ]]

    question = select_question(profile, chief, answered, ["pain"], "new_user", {})

    assert question is None


def test_returning_user_question_flow_stops_at_five_questions():
    profile = {"sex": "male", "age": 36}
    chief = "最近胃口差，肚子脹。"
    answered = [{"question_id": item} for item in [
        "red_flag",
        "duration",
        "severity",
        "appetite",
        "bowel_urine",
    ]]

    question = select_question(profile, chief, answered, ["bloating"], "returning_user_baseline_ready", {})

    assert question is None


def test_red_flag_symptoms_show_banner_but_question_flow_can_continue():
    profile = {"sex": "male", "age": 36}
    chief = "我胸痛，而且有點喘。"
    answered = [{"question_id": "red_flag"}]

    question = select_question(profile, chief, answered, ["chest_pain"], "new_user", {})

    assert question is not None
    assert question["id"] != "red_flag"
