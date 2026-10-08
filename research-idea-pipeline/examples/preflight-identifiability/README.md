# CT→MRI managed-execution fixture

`ct-mri.json` is synthetic CVPR27 CT→MRI source-free, measurement-only SSL input.
It includes an R7 critical capacity attack, an R8 identifying design, matched
Psi/control arms and frozen prospective outcomes. No training data was accessed.

`test_execution_gate.py` performs PEIG, sealed issuance, mocked dispatch, R9.O,
R10/R11 application, independent Assurance, bounded AALG and Scheduler checks.
It simulates positive, negative, inconclusive and invalid packets plus repetition
and independent new evidence. The stored packet/analysis/audit are builder inputs,
not applied results: tests rebind them to each mocked execution snapshot. They
cannot be directly applied to the initial planned state. No GPU is invoked.

Review scientific reasonableness separately from mechanical contract compliance.
