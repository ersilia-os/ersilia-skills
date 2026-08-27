# examples — synthetic guard fixture

```bash
python3 examples/run_guards.py     # prints "30 guards OK", or fails naming the guard
```

## What this is, and what it is not

`guards.json` is **not** sample output. It is 15 deliberately broken partner rows, each
constructed to trip exactly one of the skill's rejection rules, plus `run_guards.py`, which
runs the real scripts over them and asserts every guard fired.

Unlike `event-discovery/examples/`, which ships real digests, **this skill cannot commit its
real output.** A sweep names journalists and carries contact addresses; `reports/` is
gitignored for that reason and this repository is public. So the fixture is synthetic: every
entity is invented and every domain is under `.test`, a reserved TLD that can never resolve.
Nothing here points at a real person or organisation.

`known-partners-fixture.md` is a two-entry stand-in for the real list, one matched by domain
and one by name. It also carries a fenced example and stray prose on purpose, to assert that
neither is parsed as an entry — that was a real bug.

## Why the guards and not the discovery

The guards are the deterministic half of the skill: pure functions over JSON, so they can be
asserted. Discovery needs live web searches and cannot be — that is what the review gate in
`SKILL.md` is for, and why every report flags what it could not verify.

## What is covered

The relevance gate · vocabulary rejection · the contact policy (forbidden kinds,
unrecognised kinds failing closed, restricted addresses earning no envelope marker) ·
duplicate merging preferring the more complete copy · known-partner suppression by domain
and by name · the ledger with `--hide-seen` · link-year freshness (stale flagged, future
not, old `recent_work` not) · campaign deadline warnings · `Creative` rows omitting reach ·
marker-ribbon variation selectors · pipe escaping and table column consistency ·
`next_step` never being trimmed · the Drive-safe rendition avoiding tables and non-BMP
emoji · the empty-pool path.

## It has already paid for itself

Its first run found a crash: `--hide-seen` dropped a row *after* registering it as the
dedup incumbent, so a richer duplicate arriving later tried to swap places with a row that
was no longer in the kept list, and raised `StopIteration`. That path — a duplicate pair
plus `--hide-seen` — had never been exercised by hand. See `ROADMAP.md`.

**Add a guard whenever a bug is fixed.** A fix without an assertion is a bug waiting to
return.
