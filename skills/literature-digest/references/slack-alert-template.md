# Slack alert template — published digest notification

Posted to `#literature` (workspace `ersilia-workspace`, channel ID
`C010067BP2Q`) after `scripts/upload_digest.py` exits 0 — never on dry-run,
never on failure.

The Slack post is **a thematic summary, not a preview.** It tells the team
what is in the digest at a chapter level and points at GitHub. The team scans
this; they click through for the detail.

## Template

```text
📚 *Ersilia Literature Digest — week of {YYYY-MM-DD}*

*{N_total} items* · *{N_models}* Hub-candidate models 🤖 · *{N_datasets}* datasets 🗃️ · *{N_lmic}* LMIC-led 🌍 · *{N_high_impact}* high-impact ⭐

• *Hub candidates*: {one Slack line — task families and standout names/venues, no per-paper title quotes}.
• *Datasets*: {one line, or "nothing met the ≥10k-row Hub threshold this week"}.
• *Methods*: {one line on chapter 3 — high-impact reviews and methodology}.
• *Antimicrobial discovery*: {one line on chapter 4 — pathogens, LMIC concentration, notable hits}.
• *Agents & automation*: {one line on chapter 5 — omit bullet if chapter 5 is empty}.
• *Global health*: {one line on chapter 6 — omit bullet if chapter 6 is empty}.

📖 *Read the full digest →* {html_url}
```

## Composition rules

The composer (Step 9 of `SKILL.md`) reads the just-uploaded digest from disk
and fills the template.

- **One bullet per chapter, in chapter order.** Each bullet describes the
  chapter at a thematic level. Name task families, venue clusters, and LMIC
  countries; do **not** quote per-paper titles. Generalities like "a few
  interesting papers" defeat the purpose — be specific or omit the bullet.
- **Chapters 1 and 2 always render** (use the empty-handling phrasing if
  zero). Chapters 5 and 6 are **omitted entirely** when empty.
- **Counts strip** uses the digest's actual bullet counts. Empty chapter 1 or
  2 → `*0*`.

## Ersilia style — non-negotiable

- **No italics.** Slack `_underscore_` is banned in this post; species names,
  journal names, emphasis all go in bold or plain text. (The GitHub digest
  itself still italicises venue names — that is a separate surface.)
- **Bold** uses Slack `*single-asterisk*`.
- **Bullets** start with `•` (U+2022).
- **Impersonal.** No first-person plural ("our pipeline" → "the Ersilia Model
  Hub"); no team-member names; no internal channels named.
- **LMIC and decolonisation lens.** When LMIC-led work is present, name the
  countries — not as flavour, as signal.
- **Curation emojis only.** 🤖 🗃️ 🌍 ⭐ + the six task emojis (the digest
  legend's vocabulary). 📚 prefix on the header is the only extra.
- **No dividers**, no per-section headers beyond the bold caption inside each
  bullet, no preamble, no sign-off. The footer is the link.

## Posting rules

- **Post once per push.** `--force` overwrite still triggers a single post.
- **Do not post** on a failed upload, on `--dry-run`, or on a generated-but-
  not-pushed digest.
- The footer `📖 *Read the full digest →* {html_url}` is **always** present —
  it is the call to action.

## Worked example

```text
📚 *Ersilia Literature Digest — week of 2026-06-04*

*23 items* · *10* Hub-candidate models 🤖 · *0* datasets 🗃️ · *6* LMIC-led 🌍 · *3* high-impact ⭐

• *Hub candidates*: QSAR, peptide bioactivity, CPI binding-affinity, GNN-based drug repurposing, an NIST antimicrobial-peptide featurizer, and five generative releases — HELM macrocyclic peptides (TU Berlin), MMP expansion (Chemotargets Barcelona), geometric-diffusion 3D generation, and two AMP generators.
• *Datasets*: nothing met the ≥10k-row Hub threshold this week.
• *Methods*: Nat Rev Drug Discov on AI for target identification (Insilico Medicine), Nat Mach Intell peptide MS foundation model, Nat Chem Biol on PTM ligandability.
• *Antimicrobial discovery*: five mostly LMIC-led papers covering MRSA, malaria, MERS-CoV, and AgNP green synthesis — from India, Algeria, Nigeria, and Morocco.
• *Global health*: Commun Med ML-for-NTD scoping review led from Uganda and Kenya.

📖 *Read the full digest →* https://github.com/ersilia-os/digests/blob/main/literature/26-06-04-literature-digest.md
```
