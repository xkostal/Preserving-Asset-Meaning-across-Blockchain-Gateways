# Preserving Asset Meaning across Blockchain Gateways

- `validation/`: reference checker, declared cases, results, and reproduction notes.

## Reproduce the study and figures

```sh
python3 validation/run_study.py
```

The checker requires only the Python standard library. It regenerates the JSON corpus, CSV results, JSON summary, and LaTeX result macros. The study contains 43 cases and 12 stateful checks. All full-configuration outcomes and all stateful checks agree with their declared expectations.

