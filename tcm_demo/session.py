from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from .models import Baseline, FaceObservationResult, SymptomInput, TenQuestionsAnswer, UserProfile, now_iso
from .knowledge import QUESTION_BANK
from .question_flow import progress_label, select_question
from .rules import infer_symptoms
from .guidance import select_next_question

CAMERA_CONFIDENCE_MIN = 0.7
BASELINE_DAYS_REQUIRED = 15

QUESTION_FLOW = [question for _, question in QUESTION_BANK]


@dataclass
class Session:
    mode: str
    questions: list[str] = field(default_factory=lambda: QUESTION_FLOW.copy())
    qa_history: list[dict[str, str]] = field(default_factory=list)
    user_id: str = ""
    user_type: str = "new"
    current_step: str = "profile"
    profile: dict = field(default_factory=dict)
    baseline_snapshot: dict = field(default_factory=dict)
    face_observation: dict = field(default_factory=dict)
    chief_complaint: dict = field(default_factory=dict)
    ten_questions: list[dict] = field(default_factory=list)
    symptoms: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    status: str = "collecting"


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create(self, mode: str) -> tuple[str, Session]:
        session_id = uuid4().hex
        session = Session(mode=mode)
        self._sessions[session_id] = session
        return session_id, session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)


def start_session(payload: dict, store: SessionStore) -> dict:
    if "profile" in payload or "baseline" in payload:
        return start_diagnosis_session(payload, store)
    preferred_mode = payload.get("preferred_mode", "auto")
    baseline_days = int(payload.get("baseline_days", 0) or 0)
    camera_confidence = float(payload.get("camera_confidence", 0) or 0)
    mode, reason = select_mode(preferred_mode, baseline_days, camera_confidence)
    session_id, session = store.create(mode)
    return {
        "session_id": session_id,
        "mode": session.mode,
        "reason": reason,
        "first_question": session.questions[0],
    }


def start_diagnosis_session(payload: dict, store: SessionStore) -> dict:
    profile = UserProfile.from_payload(payload.get("profile") or {})
    baseline = Baseline.from_payload(payload.get("baseline") or {}, profile.user_id)
    preferred_mode = payload.get("preferred_mode", "auto")
    camera_confidence = float(payload.get("camera_confidence", 0) or 0)
    mode, reason = select_mode(preferred_mode, baseline.baseline_days, camera_confidence)
    session_id, session = store.create(mode)
    session.user_id = profile.user_id
    session.user_type = _user_type_from_payload(payload, baseline)
    session.profile = profile.to_dict()
    session.baseline_snapshot = baseline.to_dict()
    session.current_step = "face"
    return {
        "session_id": session_id,
        "mode": mode,
        "reason": reason,
        "user_type": session.user_type,
        "baseline_status": baseline.status,
        "profile": session.profile,
        "baseline": session.baseline_snapshot,
        "current_step": session.current_step,
    }


def save_face_observation(payload: dict, store: SessionStore) -> tuple[dict, int]:
    session = store.get(str(payload.get("session_id", "")))
    if not session:
        return {"error": "找不到問答 session，請重新開始。"}, 404
    face = FaceObservationResult.from_payload(payload.get("face_observation"))
    session.face_observation = face.to_dict()
    session.current_step = "chief_complaint"
    return {"next_action": "chief_complaint", "face_observation": session.face_observation}, 200


def save_chief_complaint(payload: dict, store: SessionStore) -> tuple[dict, int]:
    session = store.get(str(payload.get("session_id", "")))
    if not session:
        return {"error": "找不到問答 session，請重新開始。"}, 404
    chief = SymptomInput.from_payload(payload.get("chief_complaint") or {})
    if not chief.text.strip():
        return {"error": "請先描述主要不適。"}, 400
    session.chief_complaint = chief.to_dict()
    session.qa_history = [{"question": "主要不適", "answer": chief.text}]
    session.symptoms = infer_symptoms([], session.qa_history)
    question = select_question(session.profile, chief.text, session.ten_questions, session.symptoms, session.user_type, session.baseline_snapshot, session.face_observation)
    session.current_step = "ten_questions" if question else "result"
    return {
        "next_action": "ask_more" if question else "ready_to_diagnose",
        "current_symptoms": session.symptoms,
        "chief_complaint": session.chief_complaint,
        "question": question,
        "progress": progress_label(session.ten_questions, session.user_type),
    }, 200


def answer_ten_question(payload: dict, store: SessionStore) -> tuple[dict, int]:
    session = store.get(str(payload.get("session_id", "")))
    if not session:
        return {"error": "找不到問答 session，請重新開始。"}, 404
    answer = TenQuestionsAnswer.from_payload(payload.get("answer") or payload)
    if not answer.question_id:
        return {"error": "缺少問題代碼。"}, 400
    if any(item.get("question_id") == answer.question_id for item in session.ten_questions):
        question = select_question(
            session.profile,
            session.chief_complaint.get("text", ""),
            session.ten_questions,
            session.symptoms,
            session.user_type,
            session.baseline_snapshot,
            session.face_observation,
        )
        return {
            "next_action": "ask_more" if question else "ready_to_diagnose",
            "question": question,
            "current_symptoms": session.symptoms,
            "progress": progress_label(session.ten_questions, session.user_type),
            "duplicate_ignored": True,
        }, 200
    session.ten_questions.append(answer.to_dict())
    answer_text = "、".join(answer.selected_options + ([answer.free_text] if answer.free_text else []))
    session.qa_history.append({"question": answer.question, "answer": answer_text})
    session.symptoms = infer_symptoms([], session.qa_history)
    question = select_question(
        session.profile,
        session.chief_complaint.get("text", ""),
        session.ten_questions,
        session.symptoms,
        session.user_type,
        session.baseline_snapshot,
        session.face_observation,
    )
    if question:
        session.current_step = "ten_questions"
        return {
            "next_action": "ask_more",
            "question": question,
            "current_symptoms": session.symptoms,
            "progress": progress_label(session.ten_questions, session.user_type),
        }, 200
    session.current_step = "result"
    session.status = "ready"
    return {
        "next_action": "ready_to_diagnose",
        "current_symptoms": session.symptoms,
        "qa_history": session.qa_history,
        "ten_questions": session.ten_questions,
        "mode": session.mode,
    }, 200


def get_session_payload(payload: dict, store: SessionStore) -> tuple[dict, int]:
    session = store.get(str(payload.get("session_id", "")))
    if not session:
        return {"error": "找不到問答 session，請重新開始。"}, 404
    return {
        "session_id": payload.get("session_id"),
        "mode": session.mode,
        "profile": session.profile,
        "baseline": session.baseline_snapshot,
        "face_observation": session.face_observation,
        "chief_complaint": session.chief_complaint,
        "ten_questions": session.ten_questions,
        "symptoms": session.symptoms,
        "qa_history": session.qa_history,
        "user_type": session.user_type,
        "current_step": session.current_step,
    }, 200


def answer_session(payload: dict, store: SessionStore) -> tuple[dict, int]:
    session = store.get(str(payload.get("session_id", "")))
    if not session:
        return {"error": "找不到問答 session，請重新開始。"}, 404

    current_question = session.questions[min(len(session.qa_history), len(session.questions) - 1)]
    answer_text = str(payload.get("answer_text", "")).strip()
    if not answer_text:
        return {"error": "請輸入回答內容。"}, 400

    session.qa_history.append({"question": current_question, "answer": answer_text})
    symptoms = infer_symptoms([], session.qa_history)

    if len(session.qa_history) >= 5 and _has_minimum_signal(symptoms):
        return {
            "next_action": "ready_to_diagnose",
            "current_symptoms": symptoms,
            "qa_history": session.qa_history,
            "mode": session.mode,
        }, 200

    if len(session.qa_history) >= len(session.questions):
        return {
            "next_action": "ready_to_diagnose",
            "current_symptoms": symptoms,
            "qa_history": session.qa_history,
            "mode": session.mode,
        }, 200

    return {
        "next_action": "ask_more",
        "next_question": _next_session_question(session.qa_history, symptoms),
        "current_symptoms": symptoms,
    }, 200


def select_mode(preferred_mode: str, baseline_days: int, camera_confidence: float) -> tuple[str, str]:
    if preferred_mode == "qa_only":
        return "qa_only", "已依使用者選擇使用僅問答模式。"
    if baseline_days >= BASELINE_DAYS_REQUIRED and camera_confidence >= CAMERA_CONFIDENCE_MIN:
        return "multimodal", "臉部基準資料已滿 15 天且信心度足夠，將使用臉部差異與問答綜合模式。"
    return "qa_only", "臉部基準資料尚未滿 15 天或信心度不足，將使用深度問答模式。"


def _has_minimum_signal(symptoms: list[str]) -> bool:
    clinical_signals = set(symptoms) - {"duration", "sleep", "bowel"}
    return len(clinical_signals) >= 2


def _user_type_from_payload(payload: dict, baseline: Baseline) -> str:
    if payload.get("anonymous"):
        return "anonymous_session"
    if baseline.status == "ready":
        return "returning_user_baseline_ready"
    if baseline.status in {"building", "none"} and payload.get("known_user"):
        return "returning_user_no_baseline"
    return "new_user"


def _next_session_question(qa_history: list[dict[str, str]], symptoms: list[str]) -> str:
    asked = " ".join(item.get("question", "") for item in qa_history)
    missing_by_key = {
        "red_flag": not any(symptom in symptoms for symptom in ["chest_pain", "breath_shortness", "fainting", "high_fever", "severe_pain", "neurologic"]),
        "duration": "duration" not in symptoms,
        "sleep": "sleep" not in symptoms and "insomnia" not in symptoms,
        "bowel": "bowel" not in symptoms and "constipation" not in symptoms and "loose_stool" not in symptoms,
        "temperature": "cold" not in symptoms and "heat" not in symptoms and "dry_mouth" not in symptoms,
        "appetite": "poor_appetite" not in symptoms and "bloating" not in symptoms,
    }
    for key, question in QUESTION_BANK:
        if missing_by_key.get(key, True) and question not in asked:
            return question
    for _, question in QUESTION_BANK:
        if question not in asked:
            return question
    return select_next_question(symptoms)
