# Data handling — what may be recorded about a person

Read this before the sweep, not after someone asks why an address is in a report.

Ersilia is a Spanish foundation (*Fundació Ersilia Open Source Initiative*), so recording
a named journalist's or programme officer's details is **GDPR-relevant processing**. This
skill therefore treats contact data as a controlled field with a fixed vocabulary, and
`scripts/filter_and_sort.py` enforces that vocabulary on every run. A rule that lives
only in prose gets applied case-by-case and drifts; this one is executable.

## The principle

Record a channel **only when the organisation publishes it for the purpose of being
contacted** about coverage, collaboration or press. That is the whole test. An address
being technically findable is not the same as it being offered.

## Allowed channel kinds

These are the only values `contacts[].kind` may take (see `ALLOWED_CONTACT_KINDS` in
`scripts/_common.py`):

| Kind | What it is |
|---|---|
| `outlet_pitch` | A tips / pitch / desk address the outlet publishes for story submissions. |
| `press_office` | An institutional press or communications office. |
| `institutional` | A role address on an institution's own site (`comms@`, `partnerships@`). |
| `public_form` | A "contact us" or pitch web form — record the **URL**, not a person. |
| `none` | Explicitly no channel recorded. Use this rather than omitting the field. |

## Recorded but restricted

| Kind | Handling |
|---|---|
| `scientific_correspondence` | A corresponding-author address from a paper. Published for **scientific correspondence**, not for outreach. It is kept, flagged `restricted: true`, and both renderers label it "not a pitch channel". Using it to pitch is off-purpose — if the approach is scientific, a named colleague makes the introduction instead. |

## Never recorded

`personal_email` · `personal_handle` · `phone` · `scraped` · `inferred`

These are stripped by `filter_and_sort.py`, which warns and keeps the partner row without
the contact. A personal address obtained from a CV, a mailing-list archive, a conference
programme or a WHOIS record is in this category however easy it was to find.

**The policy fails closed.** A `kind` that is not in any list above is stripped too, with
a warning saying so. Adding a new channel kind is a deliberate edit to
`ALLOWED_CONTACT_KINDS` after someone has decided it meets the principle — never an
inference made mid-run.

## Two further rules

- **No contact details leave the local machine.** v1 writes only to `reports/`, which is
  gitignored. Nothing is published to `ersilia-os/digests` (a public repo) and nothing is
  posted to Slack. If the Drive step in "Future work" is ever built, the target must be a
  restricted-access folder.
- **A person is never characterised beyond their public professional record.** Record what
  they cover and what they have published, each traced to a live URL. Do not record
  inferred sympathies, personal circumstances, or a guess at their politics — none of it
  is needed to decide whether to pitch, and all of it is a liability in a written file.
