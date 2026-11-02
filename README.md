# SOTIF Validation Atlas

Quantitative validation of the safety of the intended functionality (ISO 21448:2022) for one hazardous behaviour of an urban robotaxi, from hazard identification to the release recommendation and field monitoring.

| File | What it is |
|---|---|
| `docs/validation-atlas.html` | Pan-and-zoom map of the whole argument along ISO 21448 Clauses 5–13, with the robotaxi example on every card and a mathematical-foundations layer with step-by-step lessons. |
| `docs/robotaxi-crosswalk-example.html` | Worked example: behaviour “does not yield”, hazardous event at a zebra crossing, three logical scenarios, budget per logical scenario, validation targets, evaluation (Cl. 12) and monitoring (Cl. 13). |
| `docs/08-risk-budget-split.md` | Methodology note on splitting the risk budget, with the 2 Nov 2026 revision: the split follows equal protection per encounter, never test cost or effort. |
| `tools/sotif_validation_workbook.py` | Python workbook (numpy, scipy; runs as a script or, via jupytext, as a notebook) implementing the chain step by step, labelled with ISO 21448 clauses and sources. |
| `tools/mock_inputs_robotaxi.json` | Synthetic inputs for the example. Replace them with your own data. |

## Running the workbook

```bash
pip install numpy scipy            # pandas and openpyxl optional, for xlsx export
python tools/sotif_validation_workbook.py --check                       # self-test
python tools/sotif_validation_workbook.py --inputs tools/mock_inputs_robotaxi.json --out-dir results
python tools/sotif_validation_workbook.py --write-mock my_inputs.json  # template for your own data
```

## Status of the content

All numerical inputs are synthetic placeholders, including the human accident data. Every formula carries a source with one of three labels: **checked** (location confirmed against the source), **location not checked**, or **derived in this course** (own construction, to be scrutinised before reuse). Open the HTML pages directly in a browser; formulas are rendered with KaTeX from cdnjs.
