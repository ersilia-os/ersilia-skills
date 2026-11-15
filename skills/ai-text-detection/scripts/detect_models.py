"""Zero-shot, model-based detection on the local machine (no text leaves it).

Two published statistics, computed from one forward pass of each of two language models
that share a tokenizer (an "observer" base model and a "performer" instruct model):

    binoculars      Hans et al. 2024 (arXiv:2401.12070): log-perplexity of the text under
                    the performer divided by the observer-vs-performer cross-perplexity.
                    LOWER means more machine-like.
    fast_detectgpt  Bao et al. 2024 (arXiv:2310.05130), analytic sampling discrepancy:
                    (log p(x) - E[log p(x~)]) / sd, with x~ drawn from the observer and
                    scored by the performer. HIGHER means more machine-like.

Both are about how *predictable* the text is to a language model, relative to how
predictable that kind of text usually is. They come from the same two models, so their
agreement is not independent corroboration.

The published thresholds belong to other model pairs, so thresholds here come from
references/calibration.json, fitted by calibrate.py on human scientific text written before
ChatGPT. Each window is compared with the thresholds at 1% and 5% false-positive rate.

Run inside the env:  conda run -n ai-text-detection python detect_models.py
Writes ``<work>/detectors.json``. ``--texts file.jsonl`` scores arbitrary texts instead
(used by calibrate.py): each line {"id", "text", ...} gets the two scores added.

Usage:
    python detect_models.py [--work /tmp/ai_text_detection] [--texts in.jsonl --out out.jsonl]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from _common import REFS, WORK_DIR, chunks, die, load_text, read_json, write_json

OBSERVER = "Qwen/Qwen2.5-1.5B"
PERFORMER = "Qwen/Qwen2.5-1.5B-Instruct"
MAX_TOKENS = 512


class Scorer:
    """Both models loaded once; ``score(text)`` returns the two statistics."""

    def __init__(self, observer: str = OBSERVER, performer: str = PERFORMER) -> None:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError:
            die(
                "needs torch + transformers: run inside the env (`conda run -n ai-text-detection python ...`)"
            )
        self.torch = torch
        self.device = (
            "mps"
            if torch.backends.mps.is_available()
            else ("cuda" if torch.cuda.is_available() else "cpu")
        )
        dtype = torch.float16 if self.device != "cpu" else torch.float32
        self.tok = AutoTokenizer.from_pretrained(observer)
        kw = {"torch_dtype": dtype}
        self.obs = (
            AutoModelForCausalLM.from_pretrained(observer, **kw).to(self.device).eval()
        )
        self.perf = (
            AutoModelForCausalLM.from_pretrained(performer, **kw).to(self.device).eval()
        )
        self.names = {
            "observer": observer,
            "performer": performer,
            "device": self.device,
            "dtype": str(dtype),
        }

    def score(self, text: str) -> dict:
        """{'binoculars', 'fast_detectgpt', 'n_tokens'} for one text (first 512 tokens)."""
        torch = self.torch
        enc = self.tok(
            text, return_tensors="pt", truncation=True, max_length=MAX_TOKENS
        ).to(self.device)
        ids = enc["input_ids"]
        if ids.shape[1] < 16:
            return {
                "binoculars": None,
                "fast_detectgpt": None,
                "n_tokens": int(ids.shape[1]),
            }
        with torch.no_grad():
            lo = self.obs(**enc).logits[0, :-1].float()
            lp = self.perf(**enc).logits[0, :-1].float()
        target = ids[0, 1:]
        n = min(lo.shape[-1], lp.shape[-1])
        lo, lp = lo[:, :n], lp[:, :n]
        logp_perf = torch.log_softmax(lp, dim=-1)
        p_obs = torch.softmax(lo, dim=-1)
        ll = logp_perf.gather(-1, target.unsqueeze(-1)).squeeze(-1)  # log p_perf(x_t)
        mean_ref = (p_obs * logp_perf).sum(-1)  # E_{x~obs}[log p_perf]
        var_ref = (p_obs * logp_perf.square()).sum(-1) - mean_ref.square()
        # Binoculars: ppl (performer) / cross-ppl (observer -> performer), in log space.
        bino = (-ll.mean()) / (-mean_ref.mean())
        fdg = (ll.sum() - mean_ref.sum()) / var_ref.sum().clamp_min(1e-6).sqrt()
        return {
            "binoculars": float(bino),
            "fast_detectgpt": float(fdg),
            "n_tokens": int(target.shape[0]),
        }


def flag(value: float | None, thr: dict) -> str | None:
    """'1%' / '5%' / None: the strictest FPR operating point this value passes."""
    if value is None or not thr:
        return None
    machine_low = thr["direction"] == "lower"
    for level in ("1", "5"):
        t = thr.get(f"thr_{level}")
        if t is None:
            continue
        if (value <= t) if machine_low else (value >= t):
            return f"{level}%"
    return None


def summarise(rows: list[dict], cal: dict) -> dict:
    """Document-level summary per detector: medians and windows past each threshold."""
    out = {}
    for det in ("binoculars", "fast_detectgpt"):
        vals = [r[det] for r in rows if r.get(det) is not None]
        thr = cal.get(det, {})
        n1 = sum(1 for r in rows if r.get(f"{det}_flag") == "1%")
        n5 = sum(1 for r in rows if r.get(f"{det}_flag") in ("1%", "5%"))
        doc_thr = cal.get("document", {}).get(det, {})
        frac1 = n1 / len(vals) if vals else 0
        out[det] = {
            "median": statistics.median(vals) if vals else None,
            "windows": len(vals),
            "over_1pct": n1,
            "over_5pct": n5,
            "fraction_over_1pct": frac1,
            "fraction_over_5pct": n5 / len(vals) if vals else 0,
            "document_flag": (
                "1%"
                if doc_thr.get("frac_1") is not None
                and len(vals) >= 3
                and frac1 > doc_thr["frac_1"]
                else (
                    "5%"
                    if doc_thr.get("frac_5") is not None
                    and len(vals) >= 3
                    and frac1 > doc_thr["frac_5"]
                    else None
                )
            ),
            "threshold": thr,
            "document_threshold": doc_thr,
        }
    return out


def main(argv: list[str] | None = None) -> int:
    """Score the document's windows (or a JSONL of texts)."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    p.add_argument(
        "--texts", help="JSONL of {id, text} to score instead of the document"
    )
    p.add_argument("--out", help="output JSONL for --texts")
    args = p.parse_args(argv)
    t0 = time.time()
    scorer = Scorer()

    if args.texts:
        out = Path(args.out or str(args.texts).replace(".jsonl", ".scored.jsonl"))
        done = set()
        if out.exists():
            done = {
                json.loads(line)["id"]
                for line in out.read_text().splitlines()
                if line.strip()
            }
        with Path(args.texts).open() as fin, out.open("a") as fout:
            for i, line in enumerate(fin, 1):
                row = json.loads(line)
                if row["id"] in done:
                    continue
                row.update(scorer.score(row["text"]))
                fout.write(json.dumps(row, ensure_ascii=False) + "\n")
                fout.flush()
                if i % 25 == 0:
                    print(f"  scored {i} ({time.time() - t0:.0f}s)", flush=True)
        print(f"scored texts -> {out} in {time.time() - t0:.0f}s")
        return 0

    work = Path(args.work)
    doc = load_text(work)
    cal = (read_json(REFS / "calibration.json") or {}).get("detectors", {})
    if not cal:
        print(
            "WARNING: detectors not calibrated yet; scores are shown without thresholds",
            file=sys.stderr,
        )
    rows = []
    for c in chunks(doc):
        s = scorer.score(c["text"])
        r = {"id": c["id"], "section": c["section"], "n_words": c["n_words"], **s}
        for det in ("binoculars", "fast_detectgpt"):
            r[f"{det}_flag"] = flag(s[det], cal.get(det, {}))
        rows.append(r)
    summary = summarise(rows, cal)
    write_json(
        work / "detectors.json",
        {
            "models": scorer.names,
            "calibration_version": cal.get("version"),
            "summary": summary,
            "windows": rows,
            "seconds": round(time.time() - t0, 1),
        },
    )
    print(
        f"detectors: {len(rows)} window(s) in {time.time() - t0:.0f}s on {scorer.device}"
    )
    for det, s in summary.items():
        med = f"{s['median']:.3f}" if s["median"] is not None else "n/a"
        print(
            f"  {det:<15} median {med}; windows past the 1% FPR threshold {s['over_1pct']}/{s['windows']}, "
            f"past 5% {s['over_5pct']}/{s['windows']}; document flag {s['document_flag']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
