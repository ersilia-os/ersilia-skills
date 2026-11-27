# Calibration corpus: sources and licences

Every window keeps its own `source_url` and `license`. To rebuild the human set, run `build_corpus.py`.

| File | What | Source | Licence |
|---|---|---|---|
| `human.jsonl` | Abstracts, Introduction/Discussion paragraphs and eLife decision letters, 2015–2021 | Europe PMC open-access subset | CC BY (filtered on licence) |
| `human.jsonl` | Grant abstracts, fiscal years 2015–2021 | NIH RePORTER | Public domain (US government works) |
| `ai.jsonl` | Abstracts, article passages, peer reviews and grant passages written for this skill in Nov 2026 by Claude Opus, Sonnet and Haiku, with three prompt styles (plain, "write like an experienced scientist", polishing a non-native researcher's notes) | Generated for this repository | Same as this repository |
| `ai.jsonl` | Abstracts by ChatGPT (gpt-3.5-turbo) and GPT-4, written from a title | RAID benchmark (Dugan et al., ACL 2024), huggingface.co/datasets/liamdugan/raid, rows from the `zero_width_space` attack with U+200B removed | MIT |
| `polished.jsonl` | 48 human windows from `human.jsonl`, rewritten by Claude Sonnet "to improve the English, keeping content and length" | Generated for this repository | CC BY (derived from the CC BY originals) |

These are not committed: ChatGPT peer reviews and arXiv abstracts from M4 (Wang et al., EACL 2024; the repository states no licence). They are kept in `~/.ai-text-detection/corpus/`, which `calibrate.py` reads when present, and `validation.md` reports how many such windows were used.
