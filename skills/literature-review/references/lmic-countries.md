# LMIC countries — World Bank low- and lower-middle-income economies

Used to apply the 🌍 marker (LMIC-led work).

- **Source**: World Bank country classifications by income level (FY2026 list, effective
  July 2025): <https://datahelpdesk.worldbank.org/knowledgebase/articles/906519>.
- **Snapshot date**: This file was last refreshed manually on **2026-05-20**. The World Bank
  updates the list each July; refresh this file at least once a year.
- **Scope**: Low-income and lower-middle-income only. Upper-middle-income (e.g. South Africa,
  Brazil, China, Mexico) is *not* included.
- **Format**: One country per line, tab-separated: `ISO2<TAB>Name<TAB>Tier`.
  `Tier ∈ {low, lower-middle}`. Lines starting with `#` are comments.

## Tagging rule

A paper gets the 🌍 marker iff its **first author** OR **senior (last) author** is at an
institution whose country (as parsed from the affiliation string) appears in this list.
Multi-affiliation authors use the first listed affiliation.

## Country list

```tsv
# Low-income economies (GNI per capita ≤ $1,145)
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
TG	Togo	low
UG	Uganda	low
YE	Yemen	low

# Lower-middle-income economies (GNI per capita $1,146–$4,515)
DZ	Algeria	lower-middle
AO	Angola	lower-middle
BD	Bangladesh	lower-middle
BJ	Benin	lower-middle
BT	Bhutan	lower-middle
BO	Bolivia	lower-middle
CV	Cabo Verde	lower-middle
KH	Cambodia	lower-middle
CM	Cameroon	lower-middle
KM	Comoros	lower-middle
CG	Republic of the Congo	lower-middle
CI	Côte d'Ivoire	lower-middle
DJ	Djibouti	lower-middle
EG	Egypt	lower-middle
SV	El Salvador	lower-middle
SZ	Eswatini	lower-middle
GH	Ghana	lower-middle
GN	Guinea	lower-middle
HT	Haiti	lower-middle
HN	Honduras	lower-middle
IN	India	lower-middle
IR	Iran	lower-middle
JO	Jordan	lower-middle
KE	Kenya	lower-middle
KG	Kyrgyz Republic	lower-middle
LA	Lao PDR	lower-middle
LB	Lebanon	lower-middle
LS	Lesotho	lower-middle
MR	Mauritania	lower-middle
FM	Micronesia	lower-middle
MN	Mongolia	lower-middle
MA	Morocco	lower-middle
MM	Myanmar	lower-middle
NP	Nepal	lower-middle
NI	Nicaragua	lower-middle
NG	Nigeria	lower-middle
PK	Pakistan	lower-middle
PG	Papua New Guinea	lower-middle
PH	Philippines	lower-middle
WS	Samoa	lower-middle
ST	São Tomé and Príncipe	lower-middle
SN	Senegal	lower-middle
SB	Solomon Islands	lower-middle
LK	Sri Lanka	lower-middle
TJ	Tajikistan	lower-middle
TZ	Tanzania	lower-middle
TL	Timor-Leste	lower-middle
TN	Tunisia	lower-middle
UA	Ukraine	lower-middle
UZ	Uzbekistan	lower-middle
VU	Vanuatu	lower-middle
VN	Vietnam	lower-middle
PS	West Bank and Gaza	lower-middle
ZM	Zambia	lower-middle
ZW	Zimbabwe	lower-middle
```

## Notes

- **Edge cases**: Affiliations sometimes use historical country names (e.g. "Burma" for
  Myanmar, "Zaire" for DR Congo) or city-only strings ("Kampala", "Lagos"). When in doubt,
  log an unresolved affiliation rather than guessing.
- **Reclassifications**: Countries hover on the boundary year-to-year. Refresh annually from
  the World Bank source above.
