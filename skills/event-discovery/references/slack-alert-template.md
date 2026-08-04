# Slack alert template — published event-discovery report notification

Posted to `#networking` (workspace `ersilia-workspace`, channel resolved by name via
`slack_search_channels` — see SKILL.md Step 9) after the Step 8 `gh api` submission
succeeds — never on dry-run, never on failure.

The Slack post is **a thematic summary, not a preview.** It tells the team what
is in the report at a continent/deadline level and points at GitHub. The team
scans this; they click through for the detail.

```text
📅 *Ersilia Event Discovery — <from> → <to>*

*{N_total} events* · *{N_priority}* high-priority fit ⭐ · *{N_lmic}* Global-South 🌍 · *{N_bursary}* with bursary/travel support 💰 · *{N_deadlines}* deadlines in the next 30 days 🗓️

*Act now* — {one line naming the single most time-sensitive deadline, or "nothing due in the next 30 days"}.

• *Africa*: {one line — standout events/venues, or omit the bullet if this continent's section is empty}.
• *Europe*: {one line}.
• *Asia*: {one line}.
• *South America*: {one line}.
• *North America*: {one line}.
• *Oceania*: {one line}.
• *Virtual / online*: {one line, or omit if empty}.

Read it: {pages_url}
```

## Field rules

- **Counts strip** uses the report's actual figures: total events, ⭐-marked
  (high-priority fit), 🌍-marked (Global-South), 💰-marked (bursary / travel
  support), and 🗓️-marked (deadline falling in the next 30 days from the "Act
  now" section).
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

- **No italics.** Slack `_underscore_` is banned in this post; species/country
  names, venue names, emphasis all go in bold or plain text.
- **Bold** uses Slack `*single-asterisk*`.
- **Bullets** start with `•` (U+2022).
- **Impersonal.** No first-person plural ("our shortlist" → "the report");
  no team-member names; no internal channels named.
- **LMIC and decolonisation lens.** When Global-South events are present,
  name the countries — not as flavour, as signal.
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
📅 *Ersilia Event Discovery — 2026-01-01 → 2027-01-01*

*34 events* · *9* high-priority fit ⭐ · *14* Global-South 🌍 · *11* with bursary/travel support 💰 · *2* deadlines in the next 30 days 🗓️

*Act now* — abstract deadline in 12 days (2026-01-13) for the H3D Symposium (Cape Town, South Africa).

• *Africa*: H3D Symposium (Cape Town) and the AMR Africa Conference (Nairobi) both carry travel bursaries.
• *Europe*: RSC AI in Chemistry (London) and the LMRL workshop (Barcelona) are strong methods-fit scouting targets.
• *Asia*: ISNTD Bites (Singapore) and a WHO AMR surveillance training (Manila).
• *South America*: DNDi's regional NTD forum (Rio de Janeiro).
• *North America*: ACS Spring meeting (industry-heavy, scout only).
• *Virtual / online*: three fully-remote training schools with open bursaries, no travel required.

Read it: https://ersilia-os.github.io/digests/events/26-01-01-event-discovery.html
```
