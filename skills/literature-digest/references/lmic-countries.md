# LMIC countries — World Bank low- and lower-middle-income economies

Used by the digest's ranking step to apply the 🌍 marker (LMIC-led work).

- **Source**: World Bank country classifications by income level (FY2027 list, effective
  July 2026): <https://datahelpdesk.worldbank.org/knowledgebase/articles/906519>. The list below
  was regenerated from the World Bank API (`api.worldbank.org/v2/country`) and cross-checked
  against the FY2027 classification note, so it is the authoritative membership, not a
  hand-maintained copy.
- **Snapshot date**: Last refreshed **2026-09-18** (FY2027 classification). The World Bank
  updates the list each July; refresh this file at least once a year.
- **Scope**: Low-income (25 economies) and lower-middle-income (47 economies) only.
  Upper-middle-income (e.g. South Africa, Brazil, China, Mexico) is *not* included — see the rationale in `search-landscape.md`.
- **Format**: One country per line, tab-separated: `ISO2<TAB>Name<TAB>Tier`.
  `Tier ∈ {low, lower-middle}`. Scripts parse this file as TSV; lines starting with `#` are
  comments.

## Tagging rule

A paper gets the 🌍 marker iff its **first author** OR **senior (last) author** is at an
institution whose country (as parsed from the affiliation string) appears in this list.
Multi-affiliation authors use the first listed affiliation for v1.

## Country list

```tsv
# Low-income economies (GNI per capita <= $1,175 in 2025)
AF	Afghanistan	low
BF	Burkina Faso	low
BI	Burundi	low
CF	Central African Republic	low
TD	Chad	low
CD	Democratic Republic of the Congo	low
ER	Eritrea	low
ET	Ethiopia	low
GM	Gambia	low
GW	Guinea-Bissau	low
KP	Korea, Dem. People's Rep.	low
LR	Liberia	low
MG	Madagascar	low
MW	Malawi	low
ML	Mali	low
MZ	Mozambique	low
NE	Niger	low
RW	Rwanda	low
SL	Sierra Leone	low
SO	Somalia	low
SS	South Sudan	low
SD	Sudan	low
SY	Syrian Arab Republic	low
UG	Uganda	low
YE	Yemen	low

# Lower-middle-income economies (GNI per capita $1,176-$4,635 in 2025)
AO	Angola	lower-middle
BD	Bangladesh	lower-middle
BJ	Benin	lower-middle
BT	Bhutan	lower-middle
BO	Bolivia	lower-middle
KH	Cambodia	lower-middle
CM	Cameroon	lower-middle
KM	Comoros	lower-middle
CI	Côte d'Ivoire	lower-middle
DJ	Djibouti	lower-middle
EG	Egypt	lower-middle
SZ	Eswatini	lower-middle
GH	Ghana	lower-middle
GN	Guinea	lower-middle
HT	Haiti	lower-middle
HN	Honduras	lower-middle
IN	India	lower-middle
KE	Kenya	lower-middle
KI	Kiribati	lower-middle
KG	Kyrgyz Republic	lower-middle
LA	Lao PDR	lower-middle
LB	Lebanon	lower-middle
LS	Lesotho	lower-middle
MR	Mauritania	lower-middle
MA	Morocco	lower-middle
MM	Myanmar	lower-middle
NA	Namibia	lower-middle
NP	Nepal	lower-middle
NI	Nicaragua	lower-middle
NG	Nigeria	lower-middle
PK	Pakistan	lower-middle
PG	Papua New Guinea	lower-middle
CG	Republic of the Congo	lower-middle
SN	Senegal	lower-middle
SB	Solomon Islands	lower-middle
ST	São Tomé and Príncipe	lower-middle
TJ	Tajikistan	lower-middle
TZ	Tanzania	lower-middle
TL	Timor-Leste	lower-middle
TG	Togo	lower-middle
TN	Tunisia	lower-middle
UZ	Uzbekistan	lower-middle
VU	Vanuatu	lower-middle
VE	Venezuela	lower-middle
PS	West Bank and Gaza	lower-middle
ZM	Zambia	lower-middle
ZW	Zimbabwe	lower-middle
```

## Notes

- **Edge cases**: Affiliations sometimes use historical country names (e.g. "Burma" for
  Myanmar, "Zaire" for DR Congo) or city-only strings ("Kampala", "Lagos"). The parser in
  `dedup_and_rank.py` keeps a small alias map and a city → country fallback. When in doubt,
  the script logs an unresolved affiliation rather than guessing.
- **Reclassifications to watch**: countries hover on the boundary year-to-year. When refreshing
  this file, diff against the prior version and flag any moves in the digest's methodology
  footer so reviewers know the tagging rule has shifted.

### Diff applied on the 2026-09-18 refresh (FY2026 file -> FY2027 list)

**Gained the marker** - Kiribati (KI), Namibia (NA) and Venezuela (VE) enter lower-middle;
Korea, Dem. People's Rep. (KP) was missing from the prior file and is low-income; Togo (TG)
moves low -> lower-middle (still eligible, tier changed).

**Lost the marker** - twelve economies leave the list:

| Economy | Why |
|---|---|
| Jordan, Micronesia, Philippines, Sri Lanka, Viet Nam | Advanced to upper-middle income in the FY2027 update. |
| Algeria, Cabo Verde, El Salvador, Iran, Mongolia, Samoa, Ukraine | Already upper-middle before FY2027; the prior file was carrying them in error. |

**Consequence for the digest.** The economies that supply most of Ersilia's LMIC entries -
India, Nigeria, Kenya, Ghana, Bangladesh, Egypt, Pakistan, Cameroon, Tanzania, Zambia,
Zimbabwe, Uganda - are unaffected. The material change is that Viet Nam, the Philippines and
Sri Lanka no longer earn the marker, and neither do Algeria or Iran, all of which appear
regularly in antimicrobial and QSAR literature. Work from those countries still scores on
topic and author signals; it simply stops receiving the equity marker and its +2 bonus.
