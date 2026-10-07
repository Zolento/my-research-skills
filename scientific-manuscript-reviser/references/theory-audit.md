# Stepwise theory and proof audit

Activate when the manuscript has a proposition, lemma, theorem, bound, corollary,
mathematical derivation or theoretical claim. Inspect the actual argument, not
mathematical typography. No theorem present means not applicable, not “proof verified”.

Build definitions → assumptions → lemmas → theorem → corollary → deployed claim.
Every step cites a previous step, definition, assumption, lemma, known theorem,
external citation or algebraic identity. “Clearly”, “therefore” and “easy to see”
are not evidence. Explicitly separate claimed dependence from verified dependence.

## Definition ledger

Check each symbol before first use, meaning across sections, domain/codomain,
random versus deterministic quantities, expectation/probability/empirical averages.
If expansion context is missing, report NOT_VERIFIED rather than infer a definition.

## Assumption ledger for each theorem

List stated assumptions, where used, hidden requirements, unused conditions and
whether the implemented method and experimental setting satisfy them. Identify
UNUSED_ASSUMPTION, HIDDEN_ASSUMPTION, ASSUMPTION_VIOLATION and ASSUMPTION_SCOPE_INFLATION.
Unused sufficient assumptions do not alone invalidate a theorem; state their role.
Do not silently strengthen a theorem's premises or change its conclusion.

## Stepwise verification

Check existence versus uniqueness, convergence versus stability/consistency,
optimality versus a bound, upper versus lower bounds, asymptotic versus finite
sample guarantees, local versus global conclusions and sufficient versus necessary
conditions. Inspect each algebraic/probabilistic operation, its domains and premises.
Record proof steps with source location, explicit dependencies, a local verification
verdict and rationale. Unknown steps stay NOT_VERIFIED. A locally checked step is
not a formal proof certificate. Optional formal verification can be suggested for
a suitable bounded subproblem; name tooling/context needed without claiming it ran.

## Theory–method alignment

Compare the object proved with the full algorithm. A simplified algorithm theorem
does not automatically cover the deployed method. Exact optimization does not imply
the same guarantee for finite iterations. Record what theorem remains valid and
what empirical or theoretical gap remains. Asymptotic/local results rephrased as
finite-sample/global guarantees fail entailment. Empirical convergence is an
observation, not a theorem. Keep correctly scoped theoretical strengths.
