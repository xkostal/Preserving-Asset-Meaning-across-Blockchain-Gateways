# Reference conformance study

Run from the project root:

```sh
python3 validation/run_study.py
```

Requires Python 3.10 or later and only its standard library. The runner evaluates 43 deterministic cases and 12 stateful checks. A failed full-configuration case or stateful expectation raises an assertion. Run without Python's `-O` option, which disables assertions.

## Files

- `admission.py`: decision procedure, restricted deterministic context digest, and single-process reservation illustration.
- `run_study.py`: declared cases, expected outcomes, diagnostic configurations, and boundary checks.
- `cases.json`: generated inputs and expected outcomes.
- `results.csv`: generated per-case outcomes and reasons for all three configurations.
- `summary.json`: generated configuration counts and stateful check outcomes.

The runner also updates `chapter-asset-meaning/results-macros.tex` and `results-rows.tex`. Regenerate figures and rebuild the PDF after changing the study.

## Recorded result

| Configuration | Exact agreement | Unsupported acceptances | Admissible cases not accepted |
|---|---:|---:|---:|
| Syntactic | 8/43 | 35 | 0 |
| Semantic | 22/43 | 21 | 0 |
| Full admission | 43/43 | 0 | 0 |

All 12 stateful checks match their declared expectations. They cover reservation contention, one-time commitment, changed context, current policy, authority revocation, approval expiry, underlying asset expiry, and commitment without reservation.

An unsupported acceptance is an acceptance of a fixture whose declared expected result is rejection or deferral. The two reduced configurations omit requirement groups on purpose. These figures describe this authored corpus; they are not deployment-wide detection rates or comparisons against real gateway implementations.

## Domain and trust boundary

Inputs are normalized JSON-compatible fixture records. Quantities are non-negative integers; decimal scales are limited to 0–36. Exact quantity conversion is fee-free. Expiry and validity endpoints in this illustration are inclusive. The deterministic JSON digest is restricted to these fixtures and does not claim full RFC 8785 conformance.

Authentication, finality, legal recognition, recipient eligibility, and delegation are asserted fixture facts. The checker evaluates the resulting predicates; it does not verify signatures, run consensus, decide applicable law, or prove arbitrary target contract behavior. The reservation object is in memory, has no durable recovery, and does not provide distributed atomicity or protect against an operator bypassing it.
