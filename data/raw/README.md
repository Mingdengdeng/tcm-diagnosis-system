# Raw Dataset Drop Zone

Place externally downloaded research/demo datasets here.

Expected sources for experiments:

- PromptCBLUE or CBLUE task files for Chinese medical NLP evaluation.
- ChatMed/ShenNong-style TCM instruction data for non-commercial research/demo experiments.
- Any self-owned or explicitly commercial-licensed TCM cases for production training.

Important:

- Do not commit large raw datasets unless the license allows redistribution.
- Do not use non-commercial datasets for a commercial model release without separate permission.
- Keep original license files or source URLs next to each dataset.

Suggested layout:

```text
data/raw/
  chatmed_tcm/
    LICENSE_OR_SOURCE.txt
    train.jsonl
  promptcblue/
    LICENSE_OR_SOURCE.txt
    dev.json
```
