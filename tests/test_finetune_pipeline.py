import json

from tools.prepare_tcm_finetune_data import normalize_record
from tcm_demo.knowledge_sources import is_commercial_safe_source


def test_prepare_tcm_data_keeps_safe_example():
    record = {
        "instruction": "最近口乾，睡不好，有點疲倦，請問要注意什麼？",
        "output": "可能與燥熱和睡眠不佳有關，建議清淡飲食並補充睡眠。",
    }

    normalized = normalize_record(record, "original_curated_tcm", False)

    assert normalized is not None
    assistant = json.loads(normalized["messages"][2]["content"])
    assert set(assistant) == {
        "preliminary_assessment",
        "possibility_level",
        "supporting_evidence",
        "next_question",
        "dietary_suggestion",
    }
    assert "口乾" in assistant["supporting_evidence"]
    assert "藥" not in normalized["messages"][2]["content"]


def test_prepare_tcm_data_filters_prescription_example():
    record = {
        "instruction": "失眠可以吃什麼？",
        "output": "建議服用某某中藥方劑，每日兩次。",
    }

    assert normalize_record(record, "original_curated_tcm", True) is None


def test_prepare_tcm_data_escalates_red_flag():
    record = {
        "instruction": "胸痛而且呼吸困難，怎麼辦？",
        "output": "需要注意。",
    }

    normalized = normalize_record(record, "original_curated_tcm", False)
    assistant = json.loads(normalized["messages"][2]["content"])

    assert "儘快就醫" in assistant["preliminary_assessment"]
    assert assistant["possibility_level"] == "高"


def test_unknown_source_is_not_commercial_safe_by_default():
    record = {
        "instruction": "最近疲倦。",
        "output": "建議先休息。",
    }

    assert normalize_record(record, "unknown_web_scrape", False) is None
    assert is_commercial_safe_source("original_curated_tcm")
    assert not is_commercial_safe_source("tcm_mkg")
