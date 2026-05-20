# TCM AI Preliminary Diagnosis Demo

Offline Flask demo for a two-mode Traditional Chinese TCM health assessment flow.

## Features

- Auto mode selection:
  - `multimodal` when camera baseline is at least 15 days and confidence is high enough.
  - `qa_only` when the user is new, baseline is not ready, or the user chooses Q&A-only testing.
- Deep Q&A flow with 5-8 Traditional Chinese questions.
- Rule-based Python trace plus optional Ollama/Qwen reasoning.
- Safe preliminary output with:
  - `初步判斷`
  - `可能性等級`
  - `支持依據`
  - `需要再確認的問題`
  - `日常飲食建議`
  - `注意事項`
- No medication, prescriptions, dosages, or cure claims in visible output.

## Run

```powershell
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000.

If Ollama is running locally, the app uses:

```powershell
$env:OLLAMA_URL='http://localhost:11434/api/generate'
$env:OLLAMA_MODEL='qwen2.5:1.5b'
```

If Ollama is unavailable, the app falls back to deterministic rule-based Traditional Chinese output so the demo still works.

## AI / Knowledge Design

The app intentionally keeps the most important medical safety logic in Python:

- Red flags are detected before the LLM response.
- TCM pattern ranking is rule-based and weighted.
- The LLM receives public candidate patterns/evidence, not raw `rule_trace`.
- Follow-up questions are selected from deterministic pattern-aware guidance, so weak LLM questions are overridden.
- The default local model is `qwen2.5:1.5b` for Raspberry Pi 5 and commercial-license friendliness.

Useful Chinese medical NLP resources should be used selectively:

- Symptom dictionaries and medical knowledge graphs can improve `tcm_demo/knowledge.py`.
- QA/dialogue datasets can improve the question bank and evaluation cases.
- PromptCBLUE/CBLUE are better for benchmarking Chinese medical NLP ability than for direct TCM diagnosis.
- Fine-tuning should happen off-device; Raspberry Pi 5 should run inference only.

## Fine-Tune / Dataset Pipeline

This project includes a safe-by-default fine-tune preparation path:

- `tools/prepare_tcm_finetune_data.py` normalizes TCM instruction data into the app JSON schema.
- The preparation script blocks unknown or non-commercial sources by default.
- `tools/train_lora_qwen_tcm.md` documents cloud QLoRA training and Ollama export.
- `tools/evaluate_tcm_model.py` evaluates baseline or fine-tuned Ollama models.
- `data/raw/` is for externally downloaded datasets.
- `data/processed/` is for generated fine-tune JSONL.

List approved free commercial-use sources:

```powershell
python tools/prepare_tcm_finetune_data.py --list-commercial-safe-sources --input dummy --output dummy
```

Prepare the included project-owned seed set:

```powershell
python tools/prepare_tcm_finetune_data.py `
  --input data/raw/commercial_safe_seed/seed.jsonl `
  --output data/processed/tcm_commercial_safe_seed.jsonl `
  --source original_curated_tcm
```

Important license note: ChatMed/ShenNong-style TCM instruction datasets may be research-only or non-commercial. Use them for internal demo/research unless you have commercial permission. For a product release, use self-owned or explicitly commercial-licensed cases.

## Test

```powershell
python -m pytest -q
```

## Fast Optimization Path

Before LoRA, improve the deterministic layer and benchmark it:

```powershell
python tools/evaluate_tcm_model.py --model qwen2.5:1.5b --cases data/evaluation/tcm_curated_eval_20.json --output tcm_model_eval_curated.json
```

Use LoRA only after the rule engine, question bank, and curated evaluation cases show a clear recurring LLM weakness.
