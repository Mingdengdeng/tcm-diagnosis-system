# Cloud QLoRA Training Guide: Qwen2.5 1.5B TCM Assistant

This guide trains a research/demo TCM assistant LoRA and prepares it for offline Raspberry Pi 5 inference through Ollama.

## License Warning

ChatMed/ShenNong-style TCM instruction data may be limited to academic research and may prohibit commercial use. Use it only for internal research/demo unless you have permission. For commercial release, replace it with self-owned or explicitly commercial-licensed data.

## Goal

Base model:

```text
Qwen/Qwen2.5-1.5B-Instruct
```

Target model behavior:

- Understand vague Traditional Chinese user symptom descriptions.
- Ask useful follow-up questions.
- Produce the app JSON schema.
- Avoid medication, prescriptions, dosages, formulas, acupuncture, and cure claims.
- Escalate red flags to medical consultation.

## 1. Prepare Data Locally

For commercial product work, use only project-owned or explicitly commercial-safe data. The repo includes a small original seed set:

```text
data/raw/commercial_safe_seed/seed.jsonl
```

List the approved free commercial-use source labels:

```powershell
python tools/prepare_tcm_finetune_data.py --list-commercial-safe-sources --input dummy --output dummy
```

Prepare the commercial-safe seed data:

```powershell
python tools/prepare_tcm_finetune_data.py `
  --input data/raw/commercial_safe_seed/seed.jsonl `
  --output data/processed/tcm_commercial_safe_seed.jsonl `
  --source original_curated_tcm
```

If you are doing non-commercial research only, place raw data in:

```text
data/raw/chatmed_tcm/train.jsonl
```

Normalize:

```powershell
python tools/prepare_tcm_finetune_data.py `
  --input data/raw/chatmed_tcm/train.jsonl `
  --output data/processed/tcm_finetune.jsonl `
  --source chatmed_tcm `
  --allow-risky-source
```

For commercial-safe training, omit `--allow-risky-source` and use a dataset you own or have rights to use. Unknown source labels are blocked by default.

## 2. Cloud Environment

Recommended GPU:

- NVIDIA L4 / A10 / A100
- 16GB VRAM minimum for QLoRA comfort

Install:

```bash
pip install -U "transformers>=4.45" "trl>=0.11" "peft>=0.13" "datasets>=3.0" "accelerate>=0.34" bitsandbytes
```

## 3. Example QLoRA Training Script

Create `train_qwen_tcm_lora.py` in the cloud workspace:

```python
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig
from trl import SFTConfig, SFTTrainer

model_name = "Qwen/Qwen2.5-1.5B-Instruct"
dataset = load_dataset("json", data_files="data/processed/tcm_finetune.jsonl", split="train")

tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)

bnb = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype="bfloat16",
)

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    quantization_config=bnb,
    device_map="auto",
    trust_remote_code=True,
)

def format_example(example):
    return tokenizer.apply_chat_template(example["messages"], tokenize=False, add_generation_prompt=False)

lora = LoraConfig(
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    task_type="CAUSAL_LM",
)

config = SFTConfig(
    output_dir="outputs/qwen2.5-1.5b-tcm-lora",
    num_train_epochs=2,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=8,
    learning_rate=2e-4,
    max_seq_length=1536,
    logging_steps=10,
    save_steps=200,
    bf16=True,
)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    args=config,
    peft_config=lora,
    formatting_func=format_example,
)

trainer.train()
trainer.save_model("outputs/qwen2.5-1.5b-tcm-lora")
```

Run:

```bash
python train_qwen_tcm_lora.py
```

## 4. Merge and Export

Merge LoRA into the base model:

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = "Qwen/Qwen2.5-1.5B-Instruct"
lora = "outputs/qwen2.5-1.5b-tcm-lora"
out = "outputs/qwen2.5-1.5b-tcm-merged"

tokenizer = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(base, device_map="auto", trust_remote_code=True)
model = PeftModel.from_pretrained(model, lora)
model = model.merge_and_unload()
model.save_pretrained(out, safe_serialization=True)
tokenizer.save_pretrained(out)
```

Convert to GGUF with llama.cpp tooling, then quantize:

```bash
python llama.cpp/convert_hf_to_gguf.py outputs/qwen2.5-1.5b-tcm-merged --outfile qwen2.5-1.5b-tcm-f16.gguf
llama.cpp/build/bin/llama-quantize qwen2.5-1.5b-tcm-f16.gguf qwen2.5-1.5b-tcm-q4_k_m.gguf Q4_K_M
```

Create Ollama model:

```text
FROM ./qwen2.5-1.5b-tcm-q4_k_m.gguf
PARAMETER temperature 0.1
PARAMETER num_ctx 2048
SYSTEM 你是中醫健康問答助理。只提供初步健康參考，不取代醫師診斷。不可提供藥物、處方、劑量、方劑、針灸或治療保證。請只輸出指定 JSON。
```

```bash
ollama create qwen2.5-1.5b-tcm-assistant -f Modelfile
```

## 5. Evaluate

Before training:

```powershell
python tools/evaluate_tcm_model.py --model qwen2.5:1.5b --output eval_baseline_1_5b.json
```

After export:

```powershell
python tools/evaluate_tcm_model.py --model qwen2.5-1.5b-tcm-assistant --output eval_tcm_assistant.json
```

Acceptance targets:

- JSON valid rate >= 99%.
- Forbidden terms = 0.
- Internal leak = 0.
- Model-only red flag recall >= 95%.
- App-specific score improves at least 8-12% over baseline.

## 6. Raspberry Pi 5 Deployment

Copy the GGUF/Ollama model to the Pi 5, then run:

```bash
ollama run qwen2.5-1.5b-tcm-assistant
```

Run the Flask app:

```bash
export OLLAMA_MODEL=qwen2.5-1.5b-tcm-assistant
python app.py
```

If latency is too high, reduce prompt size, keep `num_ctx` near 2048, or quantize smaller.
