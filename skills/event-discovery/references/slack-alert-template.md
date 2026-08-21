# Slack alert template — published event-discovery report notification

Posted to `#networking` (workspace `ersilia-workspace`, channel resolved by name via
`slack_search_channels` — see SKILL.md Step 9) after the Step 8 `gh api` submission
succeeds — never on dry-run, never on failure.

The Slack post is **a thematic summary, not a preview.** It tells the team what
is in the report at a continent/deadline level and points at GitHub. The team
scans this; they click through for the detail.

```text
📅 **Ersilia Event Digest — <date>**

**{N_total} new events** · **{N_priority}** high-priority fit ⭐ · **{N_lmic}** Global-South 🌍 · **{N_bursary}** with bursary/travel support 💰 · **{N_deadlines}** deadlines in the next 30 days 🗓️{closed_suffix}

**Act now** — {one line naming the single most time-sensitive deadline, or "nothing due in the next 30 days"}.

• **Africa**: {one line — standout events/venues, or omit the bullet if this continent's section is empty}.
• **Europe**: {one line}.
• **Asia**: {one line}.
• **South America**: {one line}.
• **North America**: {one line}.
• **Oceania**: {one line}.
• **Virtual / online**: {one line, or omit if empty}.

Read it: {pages_url}
```

## Field rules

- **Every figure is a delta, not a standing total.** The report is monthly and
  Step 6 drops already-seen editions, so the strip describes *what is new since
  the last digest*. Say "new" explicitly — `**3 new events**`, never `**3 events**`,
  which reads as "we only know about three conferences on earth". Do **not** add
  a "tracked in window" total alongside it: that number is not in the report and
  would have to be computed and kept consistent separately.
- **Counts strip counts only events the reader can still act on.** Every figure
  in the strip — total, ⭐, 🌍, 💰 — is computed over the report *excluding* its
  **"Registration closed"** section. The strip sits above a call to action, so a
  number that includes events nobody can register for overstates what is on
  offer.
  - `{N_total}` — new events in the report minus the registration-closed ones.
  - `{N_priority}` — ⭐-marked (high-priority fit) among those.
  - `{N_lmic}` — 🌍-marked (Global-South) among those.
  - `{N_bursary}` — 💰-marked (bursary / travel support) among those.
  - `{N_deadlines}` — entries in the report's **"Act now → Deadlines in the next
    30 days"** list. This one is *already* actionable-only by construction, so it
    needs no adjustment. Note it is **not** the 🗓️ marker count: 🗓️ means
    "deadline anywhere in the window", which is a much larger and different set.
- **`{closed_suffix}`** — when the registration-closed section is non-empty,
  append ` · **{N}** closed to new registrations` so the strip still reconciles
  with the report's own event total ({N_total} + {N} = the report header's `Scope:` count). **Omit the suffix entirely when that section is empty** —
  don't render a zero.
- **Do not** take `{N_priority}` from the "Top picks" list. Top picks is a
  truncated highlight reel ("…and N more"), not a census; it already excludes
  registration-closed events, so reading a count off it happens to agree here
  but will drift the moment the truncation rule changes.
- **`{pages_url}`** is the rendered GitHub **Pages** URL, derived from the
  submitted filename
  (`https://ersilia-os.github.io/digests/events/{YY-MM-DD}-event-discovery.html`).
  Use it, not the github.com blob URL — it's the reader-friendly page.
- **One bullet per continent, in the fixed order** Africa → Europe → Asia →
  South America → North America → Oceania → Virtual / online — matching the
  report's default `--group-by continent` sectioning. **Omit a continent's
  bullet entirely if that section is empty** in the report (don't render
  "nothing found" placeholders inline; the report itself already marks
  searched-but-empty continents in its coverage footer).
- **Name venues and countries, not generic themes.** "A strong showing from
  Kenya and Rwanda" beats "several African events" — be specific or omit the
  bullet.

## Composition rules

The composer (Step 9 of `SKILL.md`) reads the just-uploaded report from disk
and fills the template.

- **Chapters 1 and 2 always render — for events, this maps to: the counts
  strip and the Act-now line always render**, even when the deadline line
  reads "nothing due in the next 30 days".
- Continent bullets are omitted entirely when empty, exactly as
  `slack-alert-template.md`'s literature-digest counterpart omits empty
  chapters.

## Ersilia style — non-negotiable

- **No italics.** Species/country names, venue names, emphasis all go in bold or
  plain text.
- **Bold uses `**double-asterisk**`, NOT Slack's native `*single-asterisk*`.**
  This is counter-intuitive and was got wrong once, visibly. The `slack_send_message`
  MCP tool accepts **standard markdown** and converts it to Slack formatting — so a
  single `*x*` is read as ordinary markdown emphasis and posts as *italic*, which is
  exactly what the rule above bans. Verified by reading back the alert posted on
  2026-08-04: every `*…*` came back from the API as `_…_`. Write `**x**`.
- **Bullets** start with `•` (U+2022).
- **Impersonal.** No first-person plural ("our shortlist" → "the report");
  no team-member names; no internal channels named.
- **LMIC and decolonisation lens.** When Global-South events are present,
  name the countries — not as flavour, as signal. 🌍 now follows what an event is
  *about* rather than where it sits, so an Africa-focused meeting held in Europe
  belongs in that count — say so ("Africa-focused, held in London") rather than
  filing it silently under Europe.
- **Never credit sharers in the alert.** Team-shared events (💬 in the report)
  appear here as ordinary events. The report footnote does the crediting; the
  alert names no team members, per the rule above.
- **Curation emojis only.** ⭐ 🌍 🎓 💻 💰 🗓️ (the report's own marker
  legend). 📅 prefix on the header is the only extra.
- **No dividers**, no per-section headers beyond the bold caption inside each
  bullet, no preamble, no sign-off. The footer is the link.

## Posting rules

- **Post once per push.** `--force` overwrite still triggers a single post.
- **Do not post** on a failed submission, or a generated-but-not-pushed report.
- The footer `Read it: {pages_url}` is **always** present — it is the call to
  action.

## Worked example

```text
📅 **Ersilia Event Digest — 2026-01-02**

**34 new events** · **9** high-priority fit ⭐ · **14** Global-South 🌍 · **11** with bursary/travel support 💰 · **2** deadlines in the next 30 days 🗓️ · **2** closed to new registrations

**Act now** — abstract deadline in 12 days (2026-01-13) for the H3D Symposium (Cape Town, South Africa).

• **Africa**: H3D Symposium (Cape Town) and the AMR Africa Conference (Nairobi) both carry travel bursaries.
• **Europe**: RSC AI in Chemistry (London) and the LMRL workshop (Barcelona) are strong methods-fit scouting targets.
• **Asia**: ISNTD Bites (Singapore) and a WHO AMR surveillance training (Manila).
• **South America**: DNDi's regional NTD forum (Rio de Janeiro).
• **North America**: ACS Spring meeting (industry-heavy, scout only).
• **Virtual / online**: three fully-remote training schools with open bursaries, no travel required.

Read it: https://ersilia-os.github.io/digests/events/26-01-01-event-discovery.html
```
