# Partner classification — the 5-axis taxonomy

Single source of truth for how every candidate is labelled. Each partner carries a value
on **all five axes** plus a compact marker ribbon. The values here are the only allowed
values — `filter_and_sort.py` **rejects a partner whose axis value is not on this list**
(it does not silently coerce), and `render_sweep.py` groups and sorts on them verbatim.
Do not invent new axis values.

## The five axes

| Axis | Field | Allowed values |
|---|---|---|
| **Class** | `class` | `Media` · `Open-source` · `Institution` · `Comms-team` · `Community` · `Creative` |
| **Scope** | `scope` | `Local` · `Regional` · `Global-South` · `International` |
| **Reach** | `reach` | `Niche` · `Field` · `Broad` |
| **Warmth** | `warmth` | `Cold` · `Shared network` · `Warm intro` · `Existing contact` |
| **Priority** | `priority` | `High` · `Medium` · `Low` |

### Class — which family this belongs to

The first three serve the standing `sweep`; the last three were added for `campaign` mode
(amplifying a specific occasion) and are equally usable in a sweep.

- `Media` — science journalists, outlet editors and desks, podcasters, newsletter
  authors, and science-communication platforms.
- `Open-source` — open-source and open-science organisations, foundations, fellows
  programmes and maintainer communities.
- `Institution` — research centres and universities **in Barcelona, Catalonia or Spain**,
  plus a Global-South researcher reached through an academic tie (a citing author, a
  workshop alumnus). Global research institutions and networks as a *family* are **out of
  v1 scope** — see "Not in scope" in SKILL.md.
- `Comms-team` — the press or communications office of an institution we would ask to
  **carry** an announcement. The distinction from `Institution` is the direction of the
  ask: `Institution` is somewhere we want to be hosted or listed, `Comms-team` is someone
  we want to amplify us.
- `Community` — local science-comms groups, other non-profits, university societies,
  meetup and network organisers who would co-promote to their own list.
- `Creative` — photographers, videographers, designers, illustrators. **Commissioned, not
  pitched**: you are buying a skill, not borrowing an audience.

#### `reach` does not apply to `Creative`

Leave `reach` empty for a photographer. You are not reaching their audience, so any value
would assert something the sweep never assessed — and the renderers omit the field rather
than printing a misleading "reach Niche". `REACHLESS_CLASSES` in `scripts/_common.py`
records where an empty `reach` is expected rather than an oversight. What matters instead
is `portfolio_url`, `does_events` and `rate_note`.

### Scope — where they sit geographically

- `Local` — Barcelona, Catalonia, or elsewhere in Spain. Earns the 🏠 marker.
- `Regional` — elsewhere in Europe.
- `Global-South` — based in a low- or lower-middle-income country, or explicitly serving
  Global-South audiences. Earns the 🌍 marker.
- `International` — global, or in a high-income country outside Europe.

Pick the single most informative value. An outlet headquartered in London that syndicates
across anglophone Africa is `Regional` by base but `Global-South` by the audience that
matters — choose by **who they reach**, since reach is the point of this skill, and say so
in the `audience` note.

### Reach — how far their audience extends, *within a relevant field*

- `Niche` — a specific community: one department's seminar series, a specialist newsletter.
- `Field` — the drug-discovery / global-health / open-science field broadly.
- `Broad` — beyond the field, into policy, funder or general audiences. Earns 📣.

**Reach is not follower count.** A 200k-follower account in an unrelated field is `Niche`
for our purposes; a 2k-subscriber newsletter read by every AMR programme officer is
`Broad`. Score the *relevant* audience, and justify it in `audience`.

### Warmth — how we get there

- `Cold` — no connection; approach from scratch.
- `Shared network` — a shared consortium, event, mailing list or community, but no
  individual who would make the introduction.
- `Warm intro` — a named person is willing to introduce us.
- `Existing contact` — someone at Ersilia has already corresponded with them.

Anything other than `Cold` earns the 🤝 marker. **Warmth is a claim about a specific
path, so it must be evidenced in `warm_paths`** — a `warmth` above `Cold` with an empty
`warm_paths` is a guess dressed as an asset, and the reason the ranking puts warm rows at
the top is that they are supposed to be genuinely cheaper to action.

### Priority — the action signal

`High` / `Medium` / `Low`, scored with the rubric in `partner-priorities.md`.
Every partner also gets a recommended **action**, from a fixed set:

| Action | Meaning |
|---|---|
| `pitch` | Offer them a specific story or angle. |
| `introduce` | Make first contact and establish who we are. |
| `invite` | Ask them into something of ours — a seminar, a workshop, a call. |
| `nurture` | A relationship exists or has started; keep it warm with a concrete next touch. |
| `watch` | Worth knowing about; no approach yet. |
| `commission` | Engage a paid creative — a photographer, videographer or designer. `Creative`-class rows almost always take this. |

## Marker ribbon (fixed display order `⏱️⭐🏠🌍💻📣🤝✉️`)

| Marker | Meaning | Set by |
|---|---|---|
| ⏱️ | `contact_by` is within 14 days (campaign mode only) | script |
| ⭐ | `priority` is High | script |
| 🏠 | `scope` is Local (Barcelona / Catalonia / Spain) | script |
| 🌍 | `scope` is Global-South | script |
| 💻 | `class` is Open-source | script |
| 📣 | `reach` is Broad | script |
| 🤝 | `warmth` is anything above Cold | script |
| ✉️ | a **non-restricted** contact channel is on file | script |

⏱️ **leads the ribbon deliberately**: in campaign mode urgency outranks every other
signal, and a reader scanning the left edge of the page should meet it first. It is set
only when `filter_and_sort.py` runs with `--order deadline`, so a standing sweep never
shows it even if a row carries a `contact_by`.

Every marker is derived by `filter_and_sort.py` from the axes — do not hand-set them.
`✉️` deliberately excludes a `scientific_correspondence` address: that is not a channel
we may pitch on, so a row carrying only one is not "contactable" for this purpose.

**Never de-duplicate the ribbon by character.** Several markers are two-codepoint
sequences ending in the same variation selector (U+FE0F) — `⏱️` and `✉️` both do — so a
character-level dedup silently strips the second one's selector and it renders as a bare
`✉`. `order_markers` emits each known marker at most once, which is the only
de-duplication needed. This was a real bug, caught when campaign mode first put `⏱️` and
`✉️` in the same ribbon.

**The ribbon is emoji locally and bracketed text for a Drive Doc.** `render_sweep.py
--markers text` swaps it, because the Drive markdown-to-Doc conversion corrupts emoji
above U+1FFFF. See the note at the top of that script.

## Verification and the `†` flag

`verified: false` marks a partner whose details could not be confirmed against a live
page. Such rows render with a `†` and are listed again in their own section. They are
kept rather than dropped so the sweep is auditable — but **a `†` row must never be acted
on**, and Step 6's review gate exists partly to force a decision on each one.
