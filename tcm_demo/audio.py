import base64
import json
import os
import re
import wave
from pathlib import Path

import requests


_VOSK_MODEL = None
_VOSK_MODEL_PATH = None

GOOGLE_STT_ENDPOINT = "https://speech.googleapis.com/v1/speech:recognize"
GOOGLE_STT_PHRASES = [
    "頭痛", "頭暈", "胸悶", "氣短", "呼吸困難", "腹脹", "胃脹", "腹痛",
    "大便不成形", "腹瀉", "便秘", "口乾", "喉嚨痛", "咳嗽", "鼻塞",
    "失眠", "多夢", "夜醒", "疲倦", "身體沉重", "心悸", "壓力大",
    "怕冷", "怕熱", "盜汗", "食慾差", "噁心", "反酸", "月經", "經痛",
]

_SIMPLIFIED_SYMPTOM_TERMS = {
    "头痛": "頭痛",
    "头晕": "頭暈",
    "头重": "頭重",
    "发烧": "發燒",
    "发热": "發熱",
    "怕热": "怕熱",
    "口干": "口乾",
    "嘴干": "嘴乾",
    "喉咙": "喉嚨",
    "恶心": "噁心",
    "呕吐": "嘔吐",
    "腹泻": "腹瀉",
    "肚子胀": "肚子脹",
    "胃胀": "胃脹",
    "没力": "沒力",
    "无力": "無力",
    "身体": "身體",
    "睡觉": "睡覺",
    "出汗": "出汗",
    "盗汗": "盜汗",
    "脸": "臉",
    "经痛": "經痛",
    "月经": "月經",
    "肚子胀": "肚子脹",
    "胃胀": "胃脹",
    "腹胀": "腹脹",
    "拉肚子": "腹瀉",
    "便秘": "便秘",
    "大便不成形": "大便不成形",
    "食欲": "食慾",
    "胃口不好": "胃口不好",
    "睡不好": "睡不好",
    "失眠": "失眠",
    "胸闷": "胸悶",
    "气短": "氣短",
    "呼吸困难": "呼吸困難",
    "心悸": "心悸",
    "喉咙痛": "喉嚨痛",
    "牙龈": "牙齦",
    "口腔": "口腔",
    "压力": "壓力",
    "哪里": "哪裡",
    "这里": "這裡",
    "那里": "那裡",
    "症状": "症狀",
    "厉害": "厲害",
    "持续": "持續",
    "发冷": "發冷",
    "发麻": "發麻",
    "发炎": "發炎",
    "尿频": "尿頻",
    "颜色": "顏色",
    "抑郁": "抑鬱",
    "焦虑": "焦慮",
    "烦躁": "煩躁",
    "做梦": "做夢",
    "线上": "線上",
    "语音": "語音",
    "识别": "辨識",
}

_SIMPLIFIED_TO_TRADITIONAL_CHARS = {
    "头": "頭", "晕": "暈", "发": "發", "热": "熱", "干": "乾",
    "咙": "嚨", "恶": "噁", "呕": "嘔", "泻": "瀉", "胀": "脹",
    "没": "沒", "无": "無", "体": "體", "觉": "覺", "盗": "盜",
    "脸": "臉", "经": "經", "闷": "悶", "气": "氣", "难": "難",
    "压": "壓", "药": "藥", "医": "醫", "疗": "療", "诊": "診",
    "问": "問", "个": "個", "么": "麼", "为": "為", "会": "會",
    "时": "時", "间": "間", "长": "長", "过": "過", "还": "還",
    "轻": "輕", "对": "對", "开": "開", "关": "關", "状": "狀",
    "紧": "緊", "张": "張", "虑": "慮", "郁": "鬱", "湿": "濕",
    "虚": "虛", "风": "風", "阳": "陽", "阴": "陰", "痒": "癢",
    "软": "軟", "厉": "厲", "频": "頻", "黄": "黃", "红": "紅",
    "肿": "腫", "劳": "勞", "烦": "煩", "梦": "夢", "质": "質",
    "涩": "澀", "颜": "顏", "这": "這", "吗": "嗎", "语": "語", "识": "識",
    "线": "線",
}


def preload_audio_model():
    model_path = os.environ.get("VOSK_MODEL_PATH")
    if not model_path or not Path(model_path).exists():
        return False
    _load_vosk_model(model_path)
    return True


def transcribe_audio_upload(file_storage, root, engine="google", language="mandarin"):
    """Transcribe a browser-recorded WAV file with Google online or local Vosk."""
    if not file_storage:
        return {"ok": False, "status": "missing_audio", "message": "未收到錄音檔。"}

    audio_dir = Path(root) / "data" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / "latest_voice_input.wav"
    file_storage.save(audio_path)
    result: dict = {}

    try:
        if _normalize_engine(engine) == "offline":
            result = _transcribe_offline(audio_path)
            return result

        result = _transcribe_google(audio_path, language)
        return result
    finally:
        try:
            if audio_path.exists():
                audio_path.unlink()
                result["audio_deleted"] = True
                result["audio_saved"] = False
        except OSError:
            result["audio_deleted"] = False


def _normalize_engine(engine):
    return "offline" if str(engine or "").lower() in {"offline", "vosk", "local"} else "google"


def _transcribe_offline(audio_path):
    model_path = os.environ.get("VOSK_MODEL_PATH")
    if not model_path:
        return {
            "ok": False,
            "status": "missing_model",
            "engine": "offline",
            "audio_saved": False,
            "audio_deleted": False,
            "message": "已收到錄音，但尚未設定離線語音辨識模型 VOSK_MODEL_PATH。",
        }

    if not Path(model_path).exists():
        return {
            "ok": False,
            "status": "model_not_found",
            "engine": "offline",
            "audio_saved": False,
            "audio_deleted": False,
            "message": f"找不到離線語音模型：{model_path}",
        }

    try:
        transcript = normalize_transcript(_transcribe_with_vosk(audio_path, model_path))
    except Exception as exc:  # pragma: no cover - depends on optional native package/model
        return {
            "ok": False,
            "status": "transcribe_failed",
            "engine": "offline",
            "audio_saved": False,
            "audio_deleted": False,
            "message": f"離線語音辨識失敗：{exc}",
        }

    return {
        "ok": True,
        "status": "transcribed",
        "engine": "offline",
        "audio_saved": False,
        "audio_deleted": False,
        "transcript": transcript,
        "message": "離線語音已轉成文字。",
    }


def _transcribe_google(audio_path, language):
    api_key = os.environ.get("GOOGLE_CLOUD_SPEECH_API_KEY") or os.environ.get("GOOGLE_SPEECH_API_KEY")
    if not api_key:
        return {
            "ok": False,
            "status": "missing_google_key",
            "engine": "google",
            "audio_saved": False,
            "audio_deleted": False,
            "message": "已收到錄音，但尚未設定 GOOGLE_CLOUD_SPEECH_API_KEY，無法使用 Google 線上語音辨識。",
        }

    try:
        sample_rate, channels, sample_width = _wav_info(audio_path)
        if channels != 1 or sample_width != 2:
            return {
                "ok": False,
                "status": "unsupported_audio_format",
                "engine": "google",
                "audio_saved": False,
                "audio_deleted": False,
                "message": "錄音格式必須是 mono 16-bit WAV。",
            }

        config = {
            "encoding": "LINEAR16",
            "sampleRateHertz": sample_rate,
            "languageCode": _google_language_code(language),
            "maxAlternatives": 3,
            "enableAutomaticPunctuation": True,
            "speechContexts": [{"phrases": GOOGLE_STT_PHRASES, "boost": 12}],
        }
        model = os.environ.get("GOOGLE_CLOUD_SPEECH_MODEL", "").strip()
        if model:
            config["model"] = model

        payload = {
            "config": config,
            "audio": {"content": base64.b64encode(audio_path.read_bytes()).decode("ascii")},
        }
        endpoint = os.environ.get("GOOGLE_CLOUD_SPEECH_ENDPOINT", GOOGLE_STT_ENDPOINT)
        timeout = float(os.environ.get("GOOGLE_CLOUD_SPEECH_TIMEOUT", "18"))
        response = requests.post(f"{endpoint}?key={api_key}", json=payload, timeout=timeout)
        body = response.json()
        if not response.ok:
            error = body.get("error", {}) if isinstance(body, dict) else {}
            message = error.get("message") or f"Google 語音辨識失敗：HTTP {response.status_code}"
            return {
                "ok": False,
                "status": "google_api_error",
                "engine": "google",
                "audio_saved": False,
                "audio_deleted": False,
                "message": message,
            }

        transcript = normalize_transcript(_google_transcript(body))
        if not transcript:
            return {
                "ok": False,
                "status": "no_speech",
                "engine": "google",
                "audio_saved": False,
                "audio_deleted": False,
                "message": "Google 已處理錄音，但沒有辨識到清楚語音，請靠近麥克風再試一次。",
            }

        return {
            "ok": True,
            "status": "transcribed",
            "engine": "google",
            "audio_saved": False,
            "audio_deleted": False,
            "transcript": transcript,
            "message": "Google 線上語音已轉成文字。",
        }
    except requests.RequestException as exc:
        return {
            "ok": False,
            "status": "google_network_error",
            "engine": "google",
            "audio_saved": False,
            "audio_deleted": False,
            "message": f"連線 Google 語音辨識失敗：{exc}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "google_transcribe_failed",
            "engine": "google",
            "audio_saved": False,
            "audio_deleted": False,
            "message": f"Google 語音辨識處理失敗：{exc}",
        }


def _wav_info(audio_path):
    with wave.open(str(audio_path), "rb") as wav_file:
        return wav_file.getframerate(), wav_file.getnchannels(), wav_file.getsampwidth()


def _google_language_code(language):
    # Google Cloud Speech does not reliably provide Taiwanese Hokkien in this flow yet.
    return "zh-TW"


def _google_transcript(body):
    if not isinstance(body, dict):
        return ""
    texts = []
    for result in body.get("results", []):
        alternatives = result.get("alternatives", []) if isinstance(result, dict) else []
        if not alternatives:
            continue
        best = max(alternatives, key=lambda item: float(item.get("confidence", 0) or 0))
        if best.get("transcript"):
            texts.append(str(best["transcript"]))
    return " ".join(texts).strip()


def _transcribe_with_vosk(audio_path, model_path):
    from vosk import KaldiRecognizer

    with wave.open(str(audio_path), "rb") as wav_file:
        if wav_file.getnchannels() != 1 or wav_file.getsampwidth() != 2:
            raise ValueError("錄音格式必須是 mono 16-bit WAV。")

        _load_vosk_model(model_path)
        recognizer = KaldiRecognizer(_VOSK_MODEL, wav_file.getframerate())
        texts = []
        while True:
            data = wav_file.readframes(4000)
            if not data:
                break
            if recognizer.AcceptWaveform(data):
                text = json.loads(recognizer.Result()).get("text", "")
                if text:
                    texts.append(text)
        final_text = json.loads(recognizer.FinalResult()).get("text", "")
        if final_text:
            texts.append(final_text)
    return " ".join(texts).strip()


def normalize_transcript(text):
    normalized = re.sub(r"[\s，,。！？!?、；;：:]+", "", str(text or "").strip())
    for simplified, traditional in _SIMPLIFIED_SYMPTOM_TERMS.items():
        normalized = normalized.replace(simplified, traditional)
    normalized = "".join(_SIMPLIFIED_TO_TRADITIONAL_CHARS.get(char, char) for char in normalized)
    return normalized


def _load_vosk_model(model_path):
    global _VOSK_MODEL, _VOSK_MODEL_PATH

    if _VOSK_MODEL is None or _VOSK_MODEL_PATH != str(model_path):
        from vosk import Model

        _VOSK_MODEL = Model(str(model_path))
        _VOSK_MODEL_PATH = str(model_path)
    return _VOSK_MODEL
