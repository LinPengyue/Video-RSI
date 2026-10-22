# Stop: IG active investigation as the primary novelty

This note records a decision. It does not delete the EM, IG, controlled-fault, or natural-pilot artifacts.

The action-space audit of the 68 clean natural failures on initial_harness is in `action_space_audit/viability_report.md` and `action_space_audit/natural68_actions.csv`.

Recorded results:

- 68/68 failures were audited.
- Legal task-relevant coverage candidates: 0.
- 63/68 (92.6%) have only reobserve as an active probe family.
- 68/68 first-round IG rankings are cost-only under uniform q0 and the current family-level synthetic likelihood.
- The predetermined stop rule fired: fewer than 25% of cases have two or more active probe families, and at least 75% are cost-only. The observed rates are 7.4% and 100%.

Current probe-selection formulation is not viable as the primary novelty on the initial Video-RSI harness.

The experiments remain a negative-result record of that formulation. They are not a claim that information gain is impossible under every future action space.
