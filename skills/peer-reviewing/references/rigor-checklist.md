# Cheminformatics / AI4science rigor checklist

A checklist of pitfalls that recur specifically in cheminformatics and AI-for-science
manuscripts — the kind of thing a reviewer with deep domain experience catches that a
generic reviewer misses. Organized by category; each category notes which contribution
types it applies to. Skip categories that don't apply to the paper being reviewed rather
than forcing a verdict on every item — an irrelevant "N/A" is noise, and too much noise
buries the findings that matter.

## Contents

1. [Data splits & leakage](#1-data-splits--leakage)
2. [Baselines & comparison rigor](#2-baselines--comparison-rigor)
3. [Metrics & statistical reporting](#3-metrics--statistical-reporting)
4. [Reproducibility & availability](#4-reproducibility--availability)
5. [Applicability domain & generalization claims](#5-applicability-domain--generalization-claims)
6. [Chemistry-specific data handling](#6-chemistry-specific-data-handling)
7. [Generative model evaluation](#7-generative-model-evaluation-generative-papers-only)
8. [Docking / virtual screening validation](#8-docking--virtual-screening-validation-docking-papers-only)
9. [Ablations & architecture justification](#9-ablations--architecture-justification)

---

## 1. Data splits & leakage

*Applies to: any paper training or evaluating a predictive model.*

- **Split type stated?** Random split, scaffold split, time split, or cluster split — the
  paper should say which, and the choice should match the claim being made. A random split
  systematically overestimates performance for a "this generalizes to new chemotypes" claim,
  because near-identical molecules can land on both sides of the split.
- **Near-duplicate leakage.** Even with a nominal split, near-identical molecules (same
  scaffold, single substituent swap, or salts/stereoisomers of the same compound) can end up
  in both train and test if deduplication wasn't scaffold- or similarity-aware. This is one
  of the single most common inflaters of reported performance in the field.
  Cross-checked (assay-level dedup, InChIKey-skeleton dedup)?
  Cross-checked. Prospective claims backed by prospective-in-time data, or is a random split
  masquerading as one?

## 2. Baselines & comparison rigor

*Applies to: any paper claiming an improvement over prior methods.*

- **Trivial baseline included?** A simple descriptor + random forest / gradient boosting
  baseline is cheap to run and is the single best sanity check that a fancy architecture is
  earning its complexity. Its absence is a real gap, not a stylistic choice.
- **True SOTA comparison, not a strawman?** Is the comparison against the actual current
  best public method on the same benchmark, or against an older/weaker method that's easier
  to beat?
- **Same evaluation protocol across all compared methods?** A comparison is only fair if
  every method was tuned and evaluated under the same split, same metric, same test set —
  watch for the new method being cross-validated while baselines are cited from their
  original papers under different protocols.

## 3. Metrics & statistical reporting

*Applies to: any paper reporting quantitative performance.*

- **Metric fits the task.** Accuracy on an imbalanced classification task (e.g. 95% inactive
  compounds) is close to meaningless without AUC-ROC/AUC-PRC or a class-balance-aware metric
  alongside it.
- **Variance reported, not just a point estimate.** A single train/test split gives one
  number with no sense of stability. Cross-validation folds, multiple random seeds, or
  bootstrap confidence intervals should back any headline number — especially one being
  compared against a competing method by a small margin.
- **Statistical significance addressed when claiming "better than".** A 1-point AUC
  improvement without any measure of variance or a significance test is not evidence of a
  real difference.

## 4. Reproducibility & availability

*Applies to: every paper.*

- **Environment specified.** Dependency versions or an environment file (not just "we used
  PyTorch and RDKit") — cheminformatics results are notoriously sensitive to RDKit version
  drift (canonicalization, descriptor calculation can change between versions).
- **Seeds and hyperparameters reported.** Enough detail to actually rerun the training, not
  just the final config.
- **Data licensing clear.** If the training data has a license, is it stated, and is it
  compatible with reuse (this matters a great deal for anyone downstream, including Ersilia,
  trying to reuse the data or model)?
- (See Step 4 of `SKILL.md` for the automated link-reachability check — this section is
  about whether the *paper's text* makes reproduction possible at all, independent of
  whether the links currently resolve.)

## 5. Applicability domain & generalization claims

*Applies to: any paper making a generalization claim ("works broadly", "generalizes to new
chemical space", "applicable across targets").*

- **Chemical space coverage discussed.** Does the paper show or discuss how similar the test
  set's chemical space is to the training set's (e.g. a UMAP/PCA overlay, a nearest-neighbor
  similarity distribution)? Without this, "generalizes well" is an assertion, not a finding.
- **Endpoint breadth matches the generalization claim.** A model validated on one target or
  one assay claiming to "generalize across drug discovery" is over-claiming; the claim should
  be scoped to what was actually tested.
- **Failure modes acknowledged.** Does the paper say anything about where the model is
  expected to fail (out-of-domain inputs, rare scaffolds, specific structural classes)?

## 6. Chemistry-specific data handling

*Applies to: any paper processing SMILES or other molecular representations.*

- **Canonicalization consistency.** Is there a stated, consistent SMILES canonicalization
  step, and is it the same across training and evaluation data (mismatched canonicalization
  is a subtle, common source of silent duplicate/near-duplicate leakage)?
- **Stereochemistry handling stated.** Are stereoisomers treated as distinct or collapsed,
  and is that choice appropriate for the endpoint (it usually is not appropriate to collapse
  stereoisomers for a bioactivity/toxicity endpoint)?
- **Salt / tautomer handling stated.** Salts stripped consistently? Tautomer standardization
  applied uniformly, or left to whatever the raw data happened to contain?

## 7. Generative model evaluation (generative papers only)

*Applies to: papers whose contribution is generating/proposing new molecules.*

- **Beyond validity/uniqueness/novelty.** These three metrics are necessary but not
  sufficient — a model can score well on all three while generating chemically nonsensical
  or entirely non-useful molecules. Does the paper also report synthesizability (e.g. SA
  score), drug-likeness (e.g. QED), or downstream utility (e.g. predicted activity against
  the actual target of interest)?
- **Naive baseline included.** Comparison against a trivial baseline — e.g. random sampling
  from the training set's chemical space, or simple genetic/rule-based generation — is the
  cheapest way to show the model is doing more than memorizing or trivially perturbing known
  actives.
- **Property-conditioned claims validated.** If the model claims to generate molecules with
  a target property (e.g. "high binding affinity", "low toxicity"), is that property actually
  measured on the generated set, or only assumed from the conditioning signal?

## 8. Docking / virtual screening validation (docking papers only)

*Applies to: papers using or proposing docking-based virtual screening, including
docking-score surrogate/QSAR models.*

- **Docking scores treated as evidence, not ground truth.** Docking scores are a noisy proxy
  for binding, not a measurement. A paper that presents top docking hits as if their ranking
  were established fact — with no experimental or higher-fidelity computational follow-up —
  is overclaiming.
- **Redocking / self-docking sanity check.** Was the docking protocol validated by redocking
  a co-crystallized ligand and confirming the pose is recovered? Without this, there's no
  evidence the docking setup itself (grid box, protonation state, force field) is sound.
- **Pose plausibility discussed**, not just the numeric score, for any highlighted hit.

## 9. Ablations & architecture justification

*Applies to: any paper proposing a new or modified architecture.*

- **Each architectural choice justified by an ablation**, not just included because it's
  common in the literature. If the paper adds three components (e.g. attention, a specific
  pooling layer, a data augmentation scheme), does it show what each one contributes
  individually?
- **Complexity earns its keep.** If a simpler variant (fewer parameters, simpler
  architecture) is not shown to underperform, the added complexity of the full model isn't
  justified by the paper's own evidence.
