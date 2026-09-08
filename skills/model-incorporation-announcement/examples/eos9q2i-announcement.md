# Announcement — eos9q2i · mol-jepa

**Paper:** Mol-JEPA: A multimodal Joint Embedding Predictive Architecture for Molecules — arXiv preprint, 2026 · [10.48550/arXiv.2608.22642](https://doi.org/10.48550/arXiv.2608.22642)
**Authors:** all five named in the post — Florian Rottach (first, corresponding) → Carsten Eickhoff (last). Affiliations transcribed by hand from the arXiv HTML; OpenAlex deposits none for preprints.

**Method paragraph checked against the abstract** (`publication.abstract`, via OpenAlex):

| Claim in the post | Abstract |
|---|---|
| masks entire modalities and predicts their latent representations | "masks entire modalities and predicts the corresponding latent representations" ✓ |
| perturbing structures produces chemically invalid molecules | "chemically invalid augmentations"; "rather than using suboptimal molecular perturbations" ✓ |
| cellular phenotypes, binding affinities, ADMET, quantum chemistry | listed verbatim among the modalities ✓ |
| 4.69 million compounds | abstract says "nearly 5 million molecules"; 4.69 M is the figure in `Description` ✓ |
| 512-dimensional vector | shared 512-dimensional latent space; matches `Output Dimension: 512` ✓ |

## Post

```text
New in the Ersilia Model Hub: Mol-JEPA

We are very excited to announce the incorporation of Mol-JEPA, a multimodal molecular featurizer, into the Hub.

Thanks to Florian Rottach, Sebastian Schieferdecker, William Rudman, Randall Balestriero and Carsten Eickhoff, at the University of Tübingen, Boehringer Ingelheim, Brown University and UT Austin, Mol-JEPA turns any SMILES string into a 512-dimensional embedding that carries biological and chemical context, not just structure.

The model masks entire modalities during pretraining and predicts their latent representations. Rather than perturbing molecular structures, which often produces chemically invalid molecules, it learns across cellular phenotypes, binding affinities, ADMET profiles and quantum-chemistry simulations over 4.69 million compounds.

Preprint: https://doi.org/10.48550/arXiv.2608.22642
The authors' code: https://github.com/Boehringer-Ingelheim/mol-jepa

It now runs as a featurizer in any pipeline, with no need to rebuild the original environment:

ersilia fetch mol-jepa

https://github.com/ersilia-os/eos9q2i

#DrugDiscovery #MachineLearning #OpenScience #Cheminformatics
```

## Profiles to tag

Authors only — Ersilia does not tag institutions. Tag by typing the name into the LinkedIn
composer and picking the profile: pasted handles do not bind, and the composer is where a
human sees the profile and makes the final call. Never tag a row marked `ambiguous` or
`unverified`.

| Author | Position | Profile | Status |
|---|---|---|---|
| Florian Rottach | first, corresponding | `linkedin.com/in/florian-rottach-78486b12b` | **corroborated** — title lists Boehringer Ingelheim; Google Scholar and ResearchGate independently tie him to Tübingen and to Mol-JEPA |
| Sebastian Schieferdecker | middle | `linkedin.com/in/sebastian-schieferdecker-1a1a51164` | **corroborated** — title lists Boehringer Ingelheim; BI Nonclinical Drug Safety, Biberach, ORCID 0000-0002-4016-7409 |
| William Rudman | middle | `linkedin.com/in/william-rudman-9a730b193` | **corroborated** — title lists UT Austin; `wrudman.github.io` and Brown CCMB confirm a PhD under Eickhoff. Several people share this name — this URL only |
| Randall Balestriero | middle | `linkedin.com/in/randall-balestriero-4b5185b0` (Brown) **or** `linkedin.com/in/randallbalestriero` (Meta) | **ambiguous** — he moved Meta AI → Brown CS in August 2024 and both profiles exist. The paper lists Brown, but which is current is unresolved |
| Carsten Eickhoff | last | `de.linkedin.com/in/carsteneickhoff` | **corroborated** — title lists University of Tübingen; the uni-tuebingen.de staff directory and his lab page at health-nlp.com agree |

**No profile page was opened.** LinkedIn returns HTTP 999 to non-browser clients, so
`corroborated` means the search-result title carries a matching affiliation *and* at least
one independent source ties the person to this paper or lab. See
`references/author-lookup.md`.
