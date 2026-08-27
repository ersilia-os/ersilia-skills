# Known partners — FIXTURE for run_guards.py

Not Ersilia's real list. Two entries only, one matched by domain and one by name, so the
runner can assert both suppression paths.

This file also deliberately contains a fenced example and prose, to assert that neither is
parsed as an entry — a real bug, see ROADMAP.md.

```
- notparsed.test — inside a fence, must be ignored
- Fenced Organisation Name
```

- this prose bullet sits outside the Entries section and must also be ignored

## Entries

- example-institute.test — matched by domain
- Testwire Foundation
