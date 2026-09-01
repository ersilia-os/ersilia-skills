# Recall fixture — events the sweep must keep finding

A regression net for **discovery**, not a measure of recall. Every improvement to
`event-sources.md` or to Step 2's axis pass is unverifiable without it: a sweep that
quietly gets worse produces a thin report, and a thin report is indistinguishable from a
quiet month.

Graded by `scripts/check_recall.py` (SKILL.md Step 6a). It **warns, it never blocks** —
unlike the sweep-completeness gate in `render_report.py`. A missing query is always the
operator's fault and always fixable by running it; a fixture miss may just mean the event
moved, was renamed, or stopped existing. A check that blocks on legitimate misses is a
check people learn to bypass.

**Matching is by event name**, normalised and year-stripped via
`filter_and_sort.normalise_series_key` so the fixture cannot drift from the skill's own
notion of event identity — then compared as a **token subset**, not for equality. Rows here
abbreviate ("EMBO Workshop — mycobacterial infections" for a title that runs to fifteen
words), and demanding the full title would produce false misses and force this file to be
re-copied verbatim whenever an organiser rewords a subtitle. Keep every row to **two or
more distinctive words**; a one-word entry is rejected as unsafe to match.

Location is reported on mismatch but never causes a miss: the question is "did the sweep
find this event", not "did it word the venue identically".

## Maintenance — this file rots if left alone

- **Entries expire on their event date.** `check_recall.py` reports expired rows as
  *needs replacing*, never as misses. An expired entry left in place is a false alarm, and
  false alarms are how a check gets ignored.
- **Cap it at ~20 rows.** Prefer an entry that exercises a *specific* axis or rule over one
  that merely happened to be found. This is not a copy of the back catalogue.
- **Replace, don't just delete.** When an entry expires, add the next edition of the same
  series, or another event that exercises the same lever.

## Must find

Graded against the **candidate pool** (`/tmp/events_pool.json`) — what the sweep found,
before the window filter and before the ledger suppresses already-seen editions. Grading
the finished report instead would make every entry start failing the month after it first
appeared.

| Event | Location | Event date | Should be found by | Note |
|---|---|---|---|---|
| EDCTP Forum 2027 | Madrid, Spain | 2027-04-05 | news feeds · deadline axis · EDCTP3 row | The original miss that prompted all of §7. If this ever goes missing again, the recall work has regressed. |
| Tuberculosis Drug Discovery and Development (Gordon Research Conference 2027) | Castelldefels, Barcelona, Spain | 2027-07-18 | TB axis · Spain axis · grc.org row | Found by the TB axis, not by Pass A's Gordon row — exercises the axis pass specifically. |
| 9th Pan-African Malaria Conference (PAMC 9, MIM Society) | Kigali, Rwanda | 2027-04-26 | malaria axis | Only Africa entry in the 2026-08-19 run; also the only test of the malaria axis. |
| ESCMID Global 2027 | Stockholm, Sweden | 2027-04-09 | AMR axis | The AMR venue whose absence proved the pathogen list was a filter and never a search axis. |
| 2nd Theodor Bilharz Conference | Leiden, Netherlands | 2027-06-09 | schistosomiasis axis | S. mansoni had no venue in any earlier report. |
| XXVIII Latin American Congress of Parasitology (FLAP) | Cartagena de Indias, Colombia | 2026-10-27 | Leishmania/Chagas axis | First South-America hit in any report — guards the continent floor. |
| AI4DD — AI for Drug Discovery (NeurIPS 2026 workshop) | Sydney, Australia | 2026-12-11 | ML methods axis | Only Oceania entry, and the proof the rewritten ML-methods hint finds workshops rather than arXiv papers. |
| MozFest 2026 (Mozilla Festival) | Barcelona, Spain | 2026-10-28 | Spain axis · community sources | Priority-4-only event that clears the second-reason test on Spanish reachability. |
| EMBO Workshop — mycobacterial infections | Paris, France | 2026-09-14 | TB axis · EMBO row | Recovered from the archived #networking backfill; TB, in Europe, with a live deadline. |
| AI4Sci 2026 (2nd International Conference on AI for Science) | Mainz, Germany | 2026-10-05 | Pass A AI4Sci row | Recovered from the backfill; guards the AI-for-science row. |

## Must exclude — and the rule that should exclude it

Graded against the **cleaned set** (`/tmp/events_clean.json`), because these test the
window and filter rules that run *after* the pool is written.

| Event | Location | Event date | Rule | Note |
|---|---|---|---|---|
| ECTMIH — European Congress on Tropical Medicine and International Health | Barcelona, Spain | 2027-10-25 | outside the window, no open deadline | Legitimately dropped. If it appears, the window rule or the beyond-window escape has broken. |

## Must never become an event

Graded against the **candidate pool**. These are drawn from the Slack path, where the
input is deterministic: `#general`'s history is stable, so the same links recur every run.
A negative drawn from the web sweep would be vacuous — it only bites if the sweep happens
to encounter that exact item.

| Link or title | Shared by | Rule | Note |
|---|---|---|---|
| medium.com/blog/write-for-humans-not-algorithms | Arnau Comajuncosa | participation test — blog post | The case that proved §2.2's unconditional bypass was unsafe on a mixed channel. |
| devpolicy.org/a-not-for-profit-medicine-development-model | Gemma Turon | participation test — article | Relevant reading, not a convening. |
| pubs.acs.org/jmcmar — Bridging the AI Divide in Drug Discovery | Inés Vicente Navarro | participation test — paper | Ersilia's own publication. |
| incubator.ersilia.io | Inés Vicente Navarro | our own programme, not an event to attend | Passes the participation test as a cohort programme, but we do not apply to ourselves. Judgement call, surfaced at Step 7a rather than silently dropped. |
| AI Congress Barcelona | — | Not in scope — general tech conference | In Barcelona, so it tests that geography alone never admits an event. |
