from __future__ import annotations

import json
import statistics
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
MODELS = ["qwen2.5:1.5b", "qwen2.5:3b"]
DATA_PATH = Path("PromptCBLUE_toy_dev.json")
OUT_PATH = Path("promptcblue_20_model_eval_results.json")


def main() -> None:
    examples = [json.loads(line) for line in DATA_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    selected = select_20(examples)
    results = []
    for model in MODELS:
        print(f"Running {model}...")
        for idx, sample in enumerate(selected, start=1):
            started = time.perf_counter()
            output = ask_model(model, sample["input"], sample.get("answer_choices"))
            elapsed = time.perf_counter() - started
            score, metric, exact = score_output(sample, output)
            row = {
                "model": model,
                "idx": idx,
                "sample_id": sample.get("sample_id"),
                "task_dataset": sample.get("task_dataset"),
                "task_type": sample.get("task_type"),
                "target": sample.get("target"),
                "answer_choices": sample.get("answer_choices"),
                "prediction": output,
                "score": score,
                "metric": metric,
                "exact_or_choice_match": exact,
                "elapsed_sec": round(elapsed, 2),
            }
            results.append(row)
            print(f"  {idx:02d} {row['task_dataset']} {row['task_type']}: {score:.3f} ({elapsed:.1f}s)")

    payload = {"summary": summarize(results), "samples": selected, "results": results}
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"\nSaved detail: {OUT_PATH.resolve()}")


def select_20(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_dataset: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for item in examples:
        by_dataset.setdefault(item["task_dataset"], []).append(item)
    selected = [items[0] for items in by_dataset.values()]
    extra_task_types = {"response_generation", "event_extraction", "report_generation", "ner"}
    for item in examples:
        if len(selected) >= 20:
            break
        if item in selected:
            continue
        if item["task_type"] in extra_task_types:
            selected.append(item)
    return selected[:20]


def ask_model(model: str, input_text: str, answer_choices: list[str] | None) -> str:
    if answer_choices:
        instruction = f"\n\n請只從以下選項中選擇最合適的一項作答：{json.dumps(answer_choices, ensure_ascii=False)}"
    else:
        instruction = "\n\n請直接回答，不要補充與題目無關的內容。"
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "prompt": input_text + instruction,
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 700},
        },
        timeout=180,
    )
    response.raise_for_status()
    return response.json().get("response", "").strip()


def score_output(sample: dict[str, Any], output: str) -> tuple[float, str, bool]:
    target = str(sample.get("target", "")).strip()
    choices = sample.get("answer_choices")
    if not target:
        return 0.0, "empty_target", False
    cleaned = normalize(output)
    target_clean = normalize(target)
    if choices:
        extracted = extract_choice(cleaned, [normalize(choice) for choice in choices])
        exact = extracted == target_clean or target_clean in cleaned
        return (1.0 if exact else 0.0), "choice_exact", exact
    exact = target_clean == cleaned
    return rouge_l_f1(target_clean, cleaned), "rouge_l_char_f1", exact


def extract_choice(output: str, choices: list[str]) -> str | None:
    matches = [choice for choice in choices if choice and choice in output]
    if not matches:
        return None
    return max(matches, key=len)


def normalize(text: str) -> str:
    return "".join(str(text).split()).strip("。；;，,：:")


def rouge_l_f1(target: str, prediction: str) -> float:
    if not target or not prediction:
        return 0.0
    lcs = lcs_len(target, prediction)
    precision = lcs / len(prediction)
    recall = lcs / len(target)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def lcs_len(a: str, b: str) -> int:
    previous = [0] * (len(b) + 1)
    for char_a in a:
        current = [0]
        for idx_b, char_b in enumerate(b, start=1):
            if char_a == char_b:
                current.append(previous[idx_b - 1] + 1)
            else:
                current.append(max(previous[idx_b], current[-1]))
        previous = current
    return previous[-1]


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {}
    for model in MODELS:
        rows = [row for row in results if row["model"] == model]
        by_type = {}
        by_dataset = {}
        for row in rows:
            by_type.setdefault(row["task_type"], []).append(row["score"])
            by_dataset.setdefault(row["task_dataset"], []).append(row["score"])
        summary[model] = {
            "avg_score": round(statistics.mean(row["score"] for row in rows), 4),
            "median_score": round(statistics.median(row["score"] for row in rows), 4),
            "choice_exact_rate": round(
                sum(row["exact_or_choice_match"] for row in rows if row["metric"] == "choice_exact")
                / max(1, sum(row["metric"] == "choice_exact" for row in rows)),
                4,
            ),
            "avg_generation_rouge_l": round(
                statistics.mean(row["score"] for row in rows if row["metric"] == "rouge_l_char_f1"),
                4,
            ),
            "avg_latency_sec": round(statistics.mean(row["elapsed_sec"] for row in rows), 2),
            "by_type": {key: round(statistics.mean(value), 4) for key, value in sorted(by_type.items())},
            "by_dataset": {key: round(statistics.mean(value), 4) for key, value in sorted(by_dataset.items())},
        }
    gap = summary["qwen2.5:3b"]["avg_score"] - summary["qwen2.5:1.5b"]["avg_score"]
    summary["comparison"] = {
        "score_gap_3b_minus_1_5b": round(gap, 4),
        "relative_gap_percent_vs_3b": round(gap / summary["qwen2.5:3b"]["avg_score"] * 100, 1)
        if summary["qwen2.5:3b"]["avg_score"]
        else None,
    }
    return summary


if __name__ == "__main__":
    main()
