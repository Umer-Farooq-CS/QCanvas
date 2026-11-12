# QCanvas Paper — Open Items To Do

Things still needing **your** decision or verification. These are capability/accuracy
claims and human checks — not the numeric/formatting bugs already fixed in
`QCanvas-Tool-Paper.tex`.

---

## 1. Must verify before submission

- [ ] **Confirm the four simulation methods are actually implemented.**
  The QSim FYP report flagged **MPS** and **density-matrix (noise)** backends as *future work* (§5.2.5), but the paper presents all four (`statevector`, `density_matrix`, `mps`, `chp`) as supported/validated.
  - If MPS and density-matrix are **working**: keep the claims, but make sure the evaluation says only `statevector` was benchmarked (it does).
  - If they are **not yet working**: downgrade the claim everywhere it appears — Abstract, Contribution 3, Table 2 (`tab:sim_types`), §6.3, §9.1, Conclusion — to e.g. "statevector and stabilizer are implemented; density-matrix and MPS are provided in the type system / in progress."

- [ ] **Recompute the PennyLane Grover multi-qubit ratio (`R_mq = 0.00`).**
  In Table 7 (`tab:structural`), 216 gates with a 0.00 multi-qubit ratio is almost certainly a report error (a decomposed Grover is full of CNOTs). Recompute from the actual emitted circuit and update the cell. I preserved 0.00 only for traceability to Report Table 4.4.

- [ ] **Align the Abstract/Conclusion equivalence claim with the §9 single-engine caveat.**
  §9 correctly notes the equivalence test runs only on `backend="cirq"` (tests the Cirq round-trip, not true cross-framework agreement). The Abstract and Conclusion still lead with the equivalence result without that caveat. Either soften the headline or add a one-clause caveat so they match.

---

## 2. Should address (a reviewer will likely flag)

- [ ] **QPack overall-score formula is undefined.** The paper shows sub-scores (2.84 / 3.91 / 9.41 / 8) and an overall of 58.80, but not how they combine. Add the weighting formula, or state explicitly that `Q_pack` is an externally-defined weighted composite.

- [ ] **Empirically show the 3 divergence corrections.** Teleportation (marginalization → JSD 0.00012) and the error codes (bit reversal → 0.00035) are currently asserted. Consider showing the raw vs corrected count vectors, or confirm the corrected values come directly from data.

- [ ] **Confirm the async infrastructure is deployed/tested, not just designed.** RabbitMQ / Kubernetes / S3 and the "100 concurrent jobs (PERF-3)" claim were softened to "designed to / requirement." If you actually ran the load test, you can restate it as a measured result; if not, keep it soft.

- [ ] **Add a derivation or citation for the analytical JSD threshold.** The formula `E[JSD] ≈ (K−1)/(4N ln 2)` needs a source, and should account for comparing **two sampled** distributions (variance roughly doubles vs sample-vs-truth).

- [ ] **Double-check every "Report Table X" number against the actual FYP report.** I reconciled the paper to the reports, but verify the reports themselves are correct (esp. the structural and JSD tables).

---

## 3. Optional / editorial

- [ ] **Length & venue.** With the float fix the paper is ~20–22 pages — long for LNCS (typically 12–16). Decide the target venue, or move the testing matrix, QPack, and baseline breakdown to an appendix.

- [ ] **Recompile locally** and skim once for float placement and any remaining overfull lines (my sandbox mount was stale, so I verified via a proxy build rather than your exact file).

---

*Already fixed in the `.tex` (no action needed): running-title header, table float cascade, Grover depth (62), pairwise JSD table + 0.02 threshold, QPack raw sub-scores, QV heavy-output column removed, baseline percentages, version/hardware/example-count consistency, "at n=4 qubits" text, overclaim wording.*
