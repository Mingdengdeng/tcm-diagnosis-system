from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class UserProfile:
    user_id: str
    display_name: str = ""
    age: int | None = None
    sex: str = "unspecified"
    height_cm: float | None = None
    weight_kg: float | None = None
    lifestyle: dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "UserProfile":
        return cls(
            user_id=str(payload.get("user_id") or ""),
            display_name=str(payload.get("display_name") or ""),
            age=_optional_int(payload.get("age")),
            sex=str(payload.get("sex") or "unspecified"),
            height_cm=_optional_float(payload.get("height_cm")),
            weight_kg=_optional_float(payload.get("weight_kg")),
            lifestyle=payload.get("lifestyle") if isinstance(payload.get("lifestyle"), dict) else {},
            created_at=str(payload.get("created_at") or now_iso()),
            updated_at=now_iso(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Baseline:
    user_id: str
    baseline_id: str = ""
    baseline_days: int = 0
    status: str = "none"
    face_summary: dict[str, Any] = field(default_factory=dict)
    symptom_baseline: dict[str, Any] = field(default_factory=dict)
    last_updated: str = field(default_factory=now_iso)

    @classmethod
    def from_payload(cls, payload: dict[str, Any], user_id: str = "") -> "Baseline":
        days = int(payload.get("baseline_days", 0) or 0)
        status = str(payload.get("status") or ("ready" if days >= 15 else "building" if days else "none"))
        return cls(
            user_id=str(payload.get("user_id") or user_id),
            baseline_id=str(payload.get("baseline_id") or ""),
            baseline_days=days,
            status=status,
            face_summary=payload.get("face_summary") if isinstance(payload.get("face_summary"), dict) else {},
            symptom_baseline=payload.get("symptom_baseline") if isinstance(payload.get("symptom_baseline"), dict) else {},
            last_updated=str(payload.get("last_updated") or now_iso()),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FaceRoiSignal:
    roi_id: str
    label: str = ""
    today_redness: float | None = None
    baseline_redness: float | None = None
    shift: float | None = None
    brightness: float | None = None
    red_area_ratio: float | None = None
    status: str = "normal"

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "FaceRoiSignal":
        return cls(
            roi_id=str(payload.get("roi_id") or payload.get("id") or ""),
            label=str(payload.get("label") or payload.get("name") or ""),
            today_redness=_optional_float(payload.get("today_redness")),
            baseline_redness=_optional_float(payload.get("baseline_redness")),
            shift=_optional_float(payload.get("shift")),
            brightness=_optional_float(payload.get("brightness")),
            red_area_ratio=_optional_float(payload.get("red_area_ratio")),
            status=str(payload.get("status") or "normal"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FaceObservationResult:
    status: str = "skipped"
    baseline_used: bool = False
    quality: dict[str, str] = field(default_factory=lambda: {"distance": "ok", "lighting": "ok", "alignment": "centered"})
    progress: int = 0
    observation_summary: str = ""
    raw_image_stored: bool = False
    features: dict[str, Any] = field(default_factory=dict)
    roi_signals: list[dict[str, Any]] = field(default_factory=list)
    routing_hints: list[str] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "FaceObservationResult":
        payload = payload or {}
        roi_signals = _parse_roi_signals(payload.get("roi_signals"))
        return cls(
            status=str(payload.get("status") or "skipped"),
            baseline_used=bool(payload.get("baseline_used", False)),
            quality=payload.get("quality") if isinstance(payload.get("quality"), dict) else {"distance": "ok", "lighting": "ok", "alignment": "centered"},
            progress=int(payload.get("progress", 0) or 0),
            observation_summary=str(payload.get("observation_summary") or ""),
            raw_image_stored=bool(payload.get("raw_image_stored", False)),
            features=payload.get("features") if isinstance(payload.get("features"), dict) else {},
            roi_signals=[item.to_dict() for item in roi_signals],
            routing_hints=_list_of_str(payload.get("routing_hints")) or _routing_hints_from_roi(roi_signals),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SymptomInput:
    text: str
    input_method: str = "text"
    started_at: str = field(default_factory=now_iso)
    duration: str = ""
    location: str = ""
    severity_1_10: int | None = None
    pain_quality: str = ""
    aggravating_factors: list[str] = field(default_factory=list)
    relieving_factors: list[str] = field(default_factory=list)
    associated_symptoms: list[str] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "SymptomInput":
        return cls(
            text=str(payload.get("text") or payload.get("chief_complaint") or ""),
            input_method=str(payload.get("input_method") or "text"),
            duration=str(payload.get("duration") or ""),
            location=str(payload.get("location") or ""),
            severity_1_10=_optional_int(payload.get("severity_1_10")),
            pain_quality=str(payload.get("pain_quality") or ""),
            aggravating_factors=_list_of_str(payload.get("aggravating_factors")),
            relieving_factors=_list_of_str(payload.get("relieving_factors")),
            associated_symptoms=_list_of_str(payload.get("associated_symptoms")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TenQuestionsAnswer:
    question_id: str
    category: str
    question: str
    answer_type: str
    selected_options: list[str] = field(default_factory=list)
    free_text: str = ""
    input_method: str = "text"
    derived_symptoms: list[str] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "TenQuestionsAnswer":
        return cls(
            question_id=str(payload.get("question_id") or ""),
            category=str(payload.get("category") or ""),
            question=str(payload.get("question") or ""),
            answer_type=str(payload.get("answer_type") or "free_text"),
            selected_options=_list_of_str(payload.get("selected_options")),
            free_text=str(payload.get("free_text") or payload.get("answer_text") or ""),
            input_method=str(payload.get("input_method") or "text"),
            derived_symptoms=_list_of_str(payload.get("derived_symptoms")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _list_of_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _parse_roi_signals(value: Any) -> list[FaceRoiSignal]:
    if not isinstance(value, list):
        return []
    signals: list[FaceRoiSignal] = []
    for item in value:
        if isinstance(item, dict):
            signal = FaceRoiSignal.from_payload(item)
            if signal.roi_id:
                signals.append(signal)
    return signals


def _routing_hints_from_roi(signals: list[FaceRoiSignal]) -> list[str]:
    hints: list[str] = []
    for signal in signals:
        if signal.status not in {"slight_redness", "obvious_redness"}:
            continue
        roi_id = signal.roi_id.lower()
        ratio = signal.red_area_ratio or 0
        if ("st" in roi_id or "stomach" in roi_id or "胃" in signal.label) and ratio >= 0.08:
            hints.extend(["digestive", "mouth", "diet_stimulation", "sleep_stress"])
        if ("cv" in roi_id or "conception" in roi_id or "任脈" in signal.label) and ratio >= 0.08:
            hints.extend(["mouth_chin", "sleep_stress", "fatigue"])
    return list(dict.fromkeys(hints))
