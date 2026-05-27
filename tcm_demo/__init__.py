import os
import platform
import subprocess
from pathlib import Path


def create_app(database_path=None):
    from flask import Flask, jsonify, redirect, render_template, request, send_from_directory

    from .audio import preload_audio_model, transcribe_audio_upload
    from .chat import chat_reply
    from .database import Database
    from .diagnosis import diagnose
    from .session import (
        SessionStore,
        answer_session,
        answer_ten_question,
        get_session_payload,
        save_chief_complaint,
        save_face_observation,
        start_session,
    )

    root = Path(__file__).resolve().parent.parent
    if os.environ.get("TCM_SKIP_DOTENV") != "1" and "PYTEST_CURRENT_TEST" not in os.environ:
        load_env_file(root / ".env")
    app = Flask(
        __name__,
        template_folder=str(root / "templates"),
        static_folder=str(root / "static"),
    )
    sessions = SessionStore()
    database = Database.from_root(root, database_path)
    if os.environ.get("VOSK_PRELOAD") == "1":
        preload_audio_model()

    def persist_session(session_id):
        session = sessions.get(str(session_id or ""))
        if session:
            database.save_session(str(session_id), session)

    @app.get("/project/static/<path:filename>")
    def project_static(filename):
        return send_from_directory(root / "static", filename)

    @app.get("/project")
    def project_index_redirect():
        return redirect("/project/")

    @app.get("/")
    @app.get("/project/")
    def index():
        return render_template("index.html")

    @app.post("/api/session/start")
    @app.post("/project/api/session/start")
    def api_session_start():
        payload = request.get_json(silent=True) or {}
        result = start_session(payload, sessions)
        persist_session(result.get("session_id"))
        return jsonify(result)

    @app.post("/api/session/answer")
    @app.post("/project/api/session/answer")
    def api_session_answer():
        payload = request.get_json(silent=True) or {}
        result, status = answer_session(payload, sessions)
        persist_session(payload.get("session_id"))
        return jsonify(result), status

    @app.post("/api/session/face")
    @app.post("/project/api/session/face")
    def api_session_face():
        payload = request.get_json(silent=True) or {}
        result, status = save_face_observation(payload, sessions)
        persist_session(payload.get("session_id"))
        return jsonify(result), status

    @app.post("/api/face-observation")
    @app.post("/project/api/face-observation")
    def api_face_observation():
        payload = request.get_json(silent=True) or {}
        observation = normalize_face_observation_payload(payload.get("face_observation") or payload)
        return jsonify({
            "ok": True,
            "face_observation": observation,
            "routing_hints": observation.get("routing_hints", []),
            "message": "已接收面部 ROI 資料；此資料只作為問診追問方向提示，不作為疾病診斷。",
        })

    @app.post("/api/session/chief-complaint")
    @app.post("/project/api/session/chief-complaint")
    def api_session_chief_complaint():
        payload = request.get_json(silent=True) or {}
        result, status = save_chief_complaint(payload, sessions)
        persist_session(payload.get("session_id"))
        return jsonify(result), status

    @app.post("/api/session/ten-question")
    @app.post("/project/api/session/ten-question")
    def api_session_ten_question():
        payload = request.get_json(silent=True) or {}
        result, status = answer_ten_question(payload, sessions)
        persist_session(payload.get("session_id"))
        return jsonify(result), status

    @app.post("/api/session/get")
    @app.post("/project/api/session/get")
    def api_session_get():
        payload = request.get_json(silent=True) or {}
        result, status = get_session_payload(payload, sessions)
        return jsonify(result), status

    @app.post("/api/diagnose")
    @app.post("/project/api/diagnose")
    def api_diagnose():
        payload = request.get_json(silent=True) or {}
        result = diagnose(payload)
        session_id = str(payload.get("session_id") or "")
        if session_id:
            database.save_result(session_id, payload, result)
        return jsonify(result)

    @app.get("/api/history/<user_id>")
    @app.get("/project/api/history/<user_id>")
    def api_history(user_id):
        return jsonify({"user_id": user_id, "history": database.get_user_history(user_id)})

    @app.get("/api/database/stats")
    @app.get("/project/api/database/stats")
    def api_database_stats():
        return jsonify(database.stats())

    @app.post("/api/audio/transcribe")
    @app.post("/project/api/audio/transcribe")
    def api_audio_transcribe():
        result = transcribe_audio_upload(
            request.files.get("audio"),
            root,
            engine=request.form.get("engine", "google"),
            language=request.form.get("language", "mandarin"),
        )
        return jsonify(result)

    @app.post("/api/admin/action")
    @app.post("/project/api/admin/action")
    def api_admin_action():
        payload = request.get_json(silent=True) or {}
        action = str(payload.get("action") or "").strip()
        if action == "status":
            return jsonify({
                "ok": True,
                "platform": platform.system(),
                "database": database.stats(),
            })

        if action == "exit_kiosk":
            if os.name == "nt":
                return jsonify({"ok": False, "error": "unsupported_on_windows"}), 400
            try:
                subprocess.Popen(["pkill", "-f", "firefox.*--kiosk"])
                subprocess.Popen(["pkill", "-f", "firefox-esr.*--kiosk"])
                subprocess.Popen(["pkill", "-f", "firefox.*tcm-diagnosis-kiosk-firefox"])
                subprocess.Popen(["pkill", "-f", "firefox-esr.*tcm-diagnosis-kiosk-firefox"])
                subprocess.Popen(["pkill", "-f", "chromium.*--kiosk"])
                return jsonify({"ok": True, "message": "exit_kiosk_requested"})
            except OSError as exc:
                return jsonify({"ok": False, "error": str(exc)}), 500

        if action == "show_keyboard":
            if os.name == "nt":
                return jsonify({"ok": False, "error": "unsupported_on_windows"}), 400
            env = os.environ.copy()
            env.setdefault("DISPLAY", ":0")
            env.setdefault("WAYLAND_DISPLAY", "wayland-0")
            env.setdefault("XDG_RUNTIME_DIR", "/run/user/1000")
            env.setdefault("DBUS_SESSION_BUS_ADDRESS", "unix:path=/run/user/1000/bus")
            env["GTK_IM_MODULE"] = "xim"
            env["QT_IM_MODULE"] = "xim"
            env["XMODIFIERS"] = "@im=none"
            try:
                subprocess.Popen(
                    [
                        "sh",
                        "-lc",
                        "pgrep -u pi -x fcitx5 >/dev/null || fcitx5 -d >/tmp/tcm-fcitx5.log 2>&1; "
                        "fcitx5-remote -s keyboard-us >/dev/null 2>&1 || true; "
                        "pgrep -u pi -x squeekboard >/dev/null || squeekboard >/tmp/tcm-squeekboard.log 2>&1 &",
                    ],
                    env=env,
                )
                return jsonify({"ok": True, "message": "keyboard_requested"})
            except OSError as exc:
                return jsonify({"ok": False, "error": str(exc)}), 500

        return jsonify({"ok": False, "error": "unknown_action"}), 400

    @app.post("/api/chat")
    @app.post("/project/api/chat")
    def api_chat():
        payload = request.get_json(silent=True) or {}
        result = chat_reply(payload)
        return jsonify(result)

    return app


def load_env_file(path):
    """Load simple KEY=VALUE pairs for local Windows/Pi runs without extra deps."""
    if not Path(path).exists():
        return
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def normalize_face_observation_payload(payload):
    payload = payload if isinstance(payload, dict) else {}
    roi_signals = payload.get("roi_signals") if isinstance(payload.get("roi_signals"), list) else []
    routing_hints = payload.get("routing_hints") if isinstance(payload.get("routing_hints"), list) else []
    if not routing_hints:
        routing_hints = routing_hints_from_roi_signals(roi_signals)
    return {
        "status": payload.get("status") or "complete",
        "baseline_used": bool(payload.get("baseline_used", False)),
        "quality": payload.get("quality") if isinstance(payload.get("quality"), dict) else {
            "distance": "unknown",
            "lighting": "unknown",
            "alignment": "unknown",
        },
        "progress": payload.get("progress", 100),
        "observation_summary": payload.get("observation_summary") or summarize_roi_signals(roi_signals),
        "raw_image_stored": False,
        "features": payload.get("features") if isinstance(payload.get("features"), dict) else {},
        "roi_signals": roi_signals,
        "routing_hints": routing_hints,
    }


def summarize_roi_signals(roi_signals):
    abnormal = [
        item for item in roi_signals
        if isinstance(item, dict) and str(item.get("status")) in {"slight_redness", "obvious_redness"}
    ]
    if not abnormal:
        return "已接收面部 ROI 資料，未見明顯局部紅色比例偏高的 ROI。"
    labels = []
    for item in abnormal[:4]:
        label = item.get("meridian") or item.get("label") or item.get("roi_id") or "ROI"
        labels.append(f"{label} {item.get('status')}")
    return f"面部 ROI 顯示 {'、'.join(labels)}，系統會將其作為後續問診方向提示。"


def routing_hints_from_roi_signals(roi_signals):
    hints = []
    for signal in roi_signals:
        if not isinstance(signal, dict):
            continue
        if str(signal.get("status")) not in {"slight_redness", "obvious_redness"}:
            continue
        roi_id = str(signal.get("roi_id") or "").lower()
        meridian = str(signal.get("meridian") or signal.get("label") or "")
        if "stomach" in roi_id or roi_id.startswith("st_") or "胃" in meridian:
            hints.extend(["digestive", "mouth", "diet_stimulation"])
        if "conception" in roi_id or roi_id.startswith("cv_") or "任脈" in meridian:
            hints.extend(["mouth_chin", "sleep_stress", "fatigue"])
        if "spleen" in roi_id or roi_id.startswith("sp_") or "脾" in meridian:
            hints.extend(["digestive", "fatigue"])
        if "liver" in roi_id or roi_id.startswith("lr_") or "肝" in meridian:
            hints.extend(["sleep", "emotion", "eye_fatigue"])
        if "kidney" in roi_id or roi_id.startswith("ki_") or "腎" in meridian:
            hints.extend(["fatigue", "sleep"])
    return list(dict.fromkeys(hints))
