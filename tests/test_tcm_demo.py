from io import BytesIO

from tcm_demo import create_app
from tcm_demo.session import SessionStore, select_mode, start_session


def test_select_mode_uses_multimodal_when_baseline_ready():
    mode, _ = select_mode("auto", 15, 0.8)
    assert mode == "multimodal"


def test_select_mode_falls_back_to_qa_only_when_baseline_short():
    mode, _ = select_mode("auto", 6, 0.9)
    assert mode == "qa_only"


def test_user_can_force_qa_only_even_with_ready_camera():
    mode, _ = select_mode("qa_only", 15, 0.9)
    assert mode == "qa_only"


def test_session_reaches_ready_after_minimum_signal():
    app = create_app()
    client = app.test_client()
    started = client.post("/api/session/start", json={"preferred_mode": "qa_only"}).get_json()
    session_id = started["session_id"]

    answers = [
        "最近很疲倦，口乾。",
        "已經持續兩週。",
        "大約六分。",
        "睡不好，常常夜醒。",
        "胃口還可以。",
    ]
    result = None
    for answer in answers:
        result = client.post(
            "/api/session/answer",
            json={"session_id": session_id, "answer_text": answer},
        ).get_json()

    assert result["next_action"] == "ready_to_diagnose"
    assert "fatigue" in result["current_symptoms"]
    assert "dry_mouth" in result["current_symptoms"]


def test_diagnose_red_flag_prioritizes_medical_care():
    app = create_app()
    client = app.test_client()
    result = client.post(
        "/api/diagnose",
        json={
            "mode": "qa_only",
            "symptoms": [],
            "qa_history": [{"question": "症狀？", "answer": "我胸痛而且呼吸困難。"}],
            "face_delta": None,
        },
    ).get_json()

    assert "醫療評估" in result["preliminary_assessment"]
    assert "飲食建議取代" in result["dietary_suggestion"]


def test_diagnose_returns_traditional_chinese_disclaimer_without_ollama():
    app = create_app()
    client = app.test_client()
    result = client.post(
        "/api/diagnose",
        json={
            "mode": "qa_only",
            "symptoms": ["fatigue", "dry_mouth", "insomnia"],
            "qa_history": [],
            "face_delta": None,
        },
    ).get_json()

    assert result["mode"] == "qa_only"
    assert result["possibility_level"] in ["高", "中", "低"]
    assert "不能取代醫師診斷" in result["medical_disclaimer"]


def test_safety_sanitizes_medication_terms(monkeypatch):
    from tcm_demo import diagnosis

    monkeypatch.setattr(
        diagnosis,
        "_ask_ollama",
        lambda *args, **kwargs: {
            "preliminary_assessment": "可以服用某種藥。",
            "possibility_level": "中",
            "supporting_evidence": "需要處方。",
            "next_question": "是否需要劑量？",
            "dietary_suggestion": "服用藥物。",
        },
    )

    result = diagnosis.diagnose(
        {
            "mode": "qa_only",
            "symptoms": ["fatigue", "dry_mouth"],
            "qa_history": [],
            "face_delta": None,
        }
    )

    for key in ["preliminary_assessment", "supporting_evidence", "next_question", "dietary_suggestion"]:
        assert "處方" not in result[key]
        assert "劑量" not in result[key]
        assert "服用藥物" not in result[key]


def test_safety_sanitizes_internal_trace_terms(monkeypatch):
    from tcm_demo import diagnosis

    monkeypatch.setattr(
        diagnosis,
        "_ask_ollama",
        lambda *args, **kwargs: {
            "preliminary_assessment": "初步判斷可參考。",
            "possibility_level": "中",
            "supporting_evidence": "臉部 baseline 差異資料：null；Python rule_trace：{'has_fatigue': True}",
            "next_question": "請問是否還有其他症狀？",
            "dietary_suggestion": "建議清淡飲食。",
        },
    )

    result = diagnosis.diagnose(
        {
            "mode": "qa_only",
            "symptoms": ["fatigue"],
            "qa_history": [],
            "face_delta": None,
        }
    )

    assert "rule_trace" not in result["supporting_evidence"]
    assert "null" not in result["supporting_evidence"]
    assert "疲倦" in result["supporting_evidence"]


def test_expanded_symptom_dictionary_and_weighted_patterns():
    from tcm_demo.rules import build_rule_trace, infer_symptoms, rank_patterns

    symptoms = infer_symptoms(
        [],
        [{"question": "主要不適？", "answer": "肚子脹，身體沉重，大便不成形，胃口也不好。"}],
    )
    trace = build_rule_trace(symptoms, {"baseline_days": 15, "cheek_delta": -0.9, "confidence": 0.8})
    ranked = rank_patterns(symptoms, trace)

    assert "heavy_body" in symptoms
    assert "loose_stool" in symptoms
    assert ranked[0]["pattern"] == "濕困脾胃傾向"
    assert ranked[0]["level"] == "高"


def test_negated_red_flags_do_not_trigger_urgent_path(monkeypatch):
    from tcm_demo import diagnosis

    monkeypatch.setattr(diagnosis, "_ask_ollama", lambda *args, **kwargs: None)

    app = create_app()
    client = app.test_client()
    result = client.post(
        "/api/diagnose",
        json={
            "mode": "qa_only",
            "symptoms": [],
            "qa_history": [{"question": "主要不適？", "answer": "沒有胸痛也沒有呼吸困難，只是飯後腹脹和胃口差。"}],
            "face_delta": None,
        },
    ).get_json()

    assert "醫療評估的警訊" not in result["preliminary_assessment"]
    assert "濕困脾胃傾向" in result["preliminary_assessment"]


def test_red_flag_question_text_does_not_trigger_by_itself(monkeypatch):
    from tcm_demo import diagnosis

    monkeypatch.setattr(diagnosis, "_ask_ollama", lambda *args, **kwargs: None)

    app = create_app()
    client = app.test_client()
    result = client.post(
        "/api/diagnose",
        json={
            "mode": "qa_only",
            "symptoms": [],
            "qa_history": [{"question": "是否有胸痛、呼吸困難或劇烈疼痛？", "answer": "沒有上述情況，只是最近疲倦。"}],
            "face_delta": None,
        },
    ).get_json()

    assert "醫療評估的警訊" not in result["preliminary_assessment"]


def test_default_model_is_commercial_friendlier_1_5b():
    from tcm_demo import diagnosis

    assert diagnosis.MODEL_NAME == "qwen2.5:1.5b"


def test_public_response_hides_rule_trace_and_normalizes_lists(monkeypatch):
    from tcm_demo import diagnosis

    monkeypatch.setattr(
        diagnosis,
        "_ask_ollama",
        lambda *args, **kwargs: {
            "preliminary_assessment": "初步診斷為濕困脾胃傾向。",
            "possibility_level": "高",
            "supporting_evidence": ["腹脹或脹氣", "身體沉重"],
            "next_question": "大便狀況如何？",
            "dietary_suggestion": "建議清淡飲食。",
        },
    )

    result = diagnosis.diagnose(
        {
            "mode": "qa_only",
            "symptoms": ["bloating", "heavy_body"],
            "qa_history": [],
            "face_delta": None,
        }
    )

    assert "rule_trace" not in result
    assert "腹脹" in result["supporting_evidence"]
    assert "身體沉重" in result["supporting_evidence"]
    assert "初步診斷" not in result["preliminary_assessment"]


def test_rule_result_overrides_weak_llm_assessment(monkeypatch):
    from tcm_demo import diagnosis

    monkeypatch.setattr(
        diagnosis,
        "_ask_ollama",
        lambda *args, **kwargs: {
            "preliminary_assessment": "目前資料不足，僅能提供初步參考。",
            "possibility_level": "低",
            "supporting_evidence": "",
            "next_question": "請補充更多資料。",
            "dietary_suggestion": "",
        },
    )

    result = diagnosis.diagnose(
        {
            "mode": "qa_only",
            "symptoms": [],
            "qa_history": [{"question": "主要不適？", "answer": "肚子脹，身體沉重，大便不成形，胃口也不好。"}],
            "face_delta": None,
        }
    )

    assert "濕困脾胃傾向" in result["preliminary_assessment"]
    assert result["possibility_level"] == "高"
    assert "腹脹" in result["supporting_evidence"]


def test_pattern_aware_next_question_for_damp_digestive_case():
    from tcm_demo import diagnosis

    result = diagnosis.diagnose(
        {
            "mode": "qa_only",
            "symptoms": [],
            "qa_history": [{"question": "主要不適？", "answer": "肚子脹，身體沉重，胃口也不好。"}],
            "face_delta": None,
        }
    )

    assert "濕困脾胃傾向" in result["preliminary_assessment"]
    assert "大便" in result["next_question"] or "飯後" in result["next_question"]


def test_weak_llm_next_question_is_replaced(monkeypatch):
    from tcm_demo import diagnosis

    monkeypatch.setattr(
        diagnosis,
        "_ask_ollama",
        lambda *args, **kwargs: {
            "preliminary_assessment": "初步判斷偏向濕困脾胃傾向。",
            "possibility_level": "中",
            "supporting_evidence": "腹脹、身體沉重",
            "next_question": "請補充更多資料。",
            "dietary_suggestion": "建議清淡飲食。",
        },
    )

    result = diagnosis.diagnose(
        {
            "mode": "qa_only",
            "symptoms": [],
            "qa_history": [{"question": "主要不適？", "answer": "肚子脹，身體沉重，胃口也不好。"}],
            "face_delta": None,
        }
    )

    assert result["next_question"] != "請補充更多資料。"
    assert "大便" in result["next_question"] or "飯後" in result["next_question"]


def test_chat_endpoint_returns_safe_fallback_without_ollama():
    app = create_app()
    client = app.test_client()
    result = client.post(
        "/api/chat",
        json={"message": "最近口乾，睡不好，也有點燥熱。", "history": []},
    ).get_json()

    assert "reply" in result
    assert "follow_up" in result
    assert "不能取代醫師診斷" in result["medical_disclaimer"]
    assert "處方" not in result["reply"]


def test_chat_endpoint_prioritizes_red_flags():
    app = create_app()
    client = app.test_client()
    result = client.post(
        "/api/chat",
        json={"message": "我胸痛而且呼吸困難。", "history": []},
    ).get_json()

    assert result["red_flag"] is True
    assert "立即就醫" in result["reply"] or "急診" in result["reply"]


def test_new_five_step_session_flow_reaches_dynamic_question():
    app = create_app()
    client = app.test_client()
    started = client.post(
        "/api/session/start",
        json={
            "profile": {"user_id": "u1", "display_name": "測試", "age": 35, "sex": "female"},
            "baseline": {"baseline_days": 0},
            "camera_confidence": 0.8,
        },
    ).get_json()
    session_id = started["session_id"]

    face = client.post(
        "/api/session/face",
        json={"session_id": session_id, "face_observation": {"status": "skipped"}},
    ).get_json()
    chief = client.post(
        "/api/session/chief-complaint",
        json={"session_id": session_id, "chief_complaint": {"text": "肚子脹，胃口差，大便不成形。"}},
    ).get_json()

    assert face["next_action"] == "chief_complaint"
    assert chief["next_action"] == "ask_more"
    assert chief["question"]["id"] == "red_flag"


def test_duplicate_ten_question_answer_is_ignored():
    app = create_app()
    client = app.test_client()
    started = client.post(
        "/api/session/start",
        json={
            "profile": {"user_id": "u1", "display_name": "測試", "age": 35, "sex": "male"},
            "baseline": {"baseline_days": 0},
            "camera_confidence": 0.8,
        },
    ).get_json()
    session_id = started["session_id"]
    client.post("/api/session/face", json={"session_id": session_id, "face_observation": {"status": "skipped"}})
    client.post(
        "/api/session/chief-complaint",
        json={"session_id": session_id, "chief_complaint": {"text": "肚子痛。"}},
    )
    answer = {
        "question_id": "red_flag",
        "category": "red_flag",
        "question": "目前是否有胸痛、呼吸困難、高燒持續、昏厥、意識不清、半邊無力或劇烈疼痛？",
        "answer_type": "free_text",
        "selected_options": [],
        "free_text": "沒有上述情況",
        "input_method": "text",
    }

    first = client.post("/api/session/ten-question", json={"session_id": session_id, "answer": answer}).get_json()
    second = client.post("/api/session/ten-question", json={"session_id": session_id, "answer": answer}).get_json()
    session = client.post("/api/session/get", json={"session_id": session_id}).get_json()

    assert first["next_action"] == "ask_more"
    assert second["duplicate_ignored"] is True
    assert len(session["ten_questions"]) == 1


def test_diagnosis_returns_ranked_possibilities_for_new_payload(monkeypatch):
    from tcm_demo import diagnosis

    monkeypatch.setattr(diagnosis, "_ask_ollama", lambda *args, **kwargs: None)

    result = diagnosis.diagnose(
        {
            "mode": "qa_only",
            "chief_complaint": {"text": "肚子脹，身體沉重，大便不成形，胃口也不好。"},
            "ten_questions": [],
            "face_observation": {"status": "skipped"},
        }
    )

    assert result["possibilities"]
    assert result["possibilities"][0]["pattern"] == "濕困脾胃傾向"
    assert "fit_percent" in result["possibilities"][0]
    assert result["report_summary"]
    assert result["care_plan"]
    assert result["watch_items"]
    assert result["seek_care_if"]


def test_sqlite_store_persists_session_and_result(tmp_path, monkeypatch):
    from tcm_demo import diagnosis

    monkeypatch.setattr(diagnosis, "_ask_ollama", lambda *args, **kwargs: None)

    db_path = tmp_path / "tcm_test.sqlite3"
    app = create_app(database_path=db_path)
    client = app.test_client()
    started = client.post(
        "/api/session/start",
        json={
            "profile": {"user_id": "u-db", "display_name": "測試", "age": 35, "sex": "female"},
            "baseline": {"baseline_days": 0},
            "camera_confidence": 0.8,
        },
    ).get_json()
    session_id = started["session_id"]
    client.post("/api/session/face", json={"session_id": session_id, "face_observation": {"status": "skipped"}})
    client.post(
        "/api/session/chief-complaint",
        json={"session_id": session_id, "chief_complaint": {"text": "肚子脹，胃口差。"}},
    )

    result = client.post(
        "/api/diagnose",
        json={
            "session_id": session_id,
            "profile": {"user_id": "u-db"},
            "mode": "qa_only",
            "chief_complaint": {"text": "肚子脹，胃口差。"},
            "ten_questions": [],
            "face_observation": {"status": "skipped"},
        },
    ).get_json()
    history = client.get("/api/history/u-db").get_json()
    stats = client.get("/api/database/stats").get_json()

    assert db_path.exists()
    assert result["possibilities"]
    assert len(history["history"]) == 1
    assert history["history"][0]["session_id"] == session_id
    assert stats["profiles"] == 1
    assert stats["sessions"] == 1
    assert stats["results"] == 1


def test_admin_status_opens_without_pin(tmp_path, monkeypatch):
    monkeypatch.setenv("TCM_ADMIN_PIN", "2468")
    app = create_app(database_path=tmp_path / "tcm_test.sqlite3")
    client = app.test_client()

    accepted = client.post("/api/admin/action", json={"action": "status"})

    assert accepted.status_code == 200
    assert accepted.get_json()["ok"] is True


def test_audio_transcribe_deletes_audio_and_reports_missing_model(tmp_path, monkeypatch):
    monkeypatch.delenv("VOSK_MODEL_PATH", raising=False)
    app = create_app(database_path=tmp_path / "tcm_test.sqlite3")
    client = app.test_client()

    result = client.post(
        "/api/audio/transcribe",
        data={"audio": (BytesIO(b"fake wav bytes"), "voice-input.wav"), "engine": "offline"},
        content_type="multipart/form-data",
    ).get_json()

    assert result["ok"] is False
    assert result["status"] == "missing_model"
    assert result["audio_saved"] is False
    assert result["audio_deleted"] is True


def test_audio_transcribe_online_reports_missing_google_key(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_SPEECH_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_SPEECH_API_KEY", raising=False)
    app = create_app(database_path=tmp_path / "tcm_test.sqlite3")
    client = app.test_client()

    result = client.post(
        "/api/audio/transcribe",
        data={"audio": (BytesIO(b"fake wav bytes"), "voice-input.wav"), "engine": "google"},
        content_type="multipart/form-data",
    ).get_json()

    assert result["ok"] is False
    assert result["status"] == "missing_google_key"
    assert result["engine"] == "google"
    assert result["audio_deleted"] is True


def test_audio_transcript_normalization():
    from tcm_demo.audio import normalize_transcript

    assert normalize_transcript("头 痛 口 干 胃胀") == "頭痛口乾胃脹"
    assert normalize_transcript("哪里不舒服，症状持续多久，胸闷气短吗") == "哪裡不舒服症狀持續多久胸悶氣短嗎"


def test_face_observation_api_returns_routing_hints(tmp_path):
    app = create_app(database_path=tmp_path / "tcm_test.sqlite3")
    client = app.test_client()

    result = client.post(
        "/api/face-observation",
        json={
            "status": "complete",
            "baseline_used": True,
            "roi_signals": [
                {
                    "roi_id": "ST_stomach",
                    "meridian": "足陽明胃經",
                    "red_area_ratio": 0.1758,
                    "status": "obvious_redness",
                }
            ],
        },
    ).get_json()

    assert result["ok"] is True
    assert "digestive" in result["routing_hints"]
    assert result["face_observation"]["raw_image_stored"] is False
