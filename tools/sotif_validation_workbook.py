# %%
"""
SOTIF validation workbook: one hazardous event, from acceptance criterion to release recommendation
===================================================================================================

What this file does
-------------------
It takes one hazardous event (HE) from the hazard analysis of an automated driving system and
computes the quantitative SOTIF validation chain of ISO 21448:2022 in the form used in the course
worked example "Robotaxi crosswalk" (course doc 14). The steps follow the clauses of the standard:
each step names its clause and produces, or records, the related work product. Any number K of
logical scenarios, any confidence level and any observed failure counts are allowed.

    clause          step                                        main formula or content
    --------------  ------------------------------------------  --------------------------------------------
    Cl. 5 / 6.3     function and hazard identification (record) HB and HE tables, harm-class shares
    Cl. 6.4         risk evaluation of the selected HE          P(E|HB), P(notC|E), P(S|notC); optional per LS
    Cl. 6.5         acceptance criterion                        h = events / hours;  A_H = share x margin x h
    Annex C.2.1     tolerable behaviour rate                    R_HB = A_H / (P_E P_C P_S)
    Annex C.3       naive validation target (for scale)         tau = ln(1/(1-C)) / R_HB
    Cl. 7.3         logical scenarios, triggering conditions    TC = region inside one or more LS
    Cl. 9.3 (a)     joint confidence                            C_b = 1 - (1-C)/m;  L = ln(1/(1-C_b))
    Cl. 9.3 (b)     exposure per logical scenario (pilot)       lambda_k^U = chi2_{C_b}(2N_k+2) / (2 tau_pilot)
    Cl. 9.3 (c)     reserve for unknown scenarios (Cl. 11)      b_unk = f R_HB;  B = R_HB - b_unk
    Cl. 9.3 (d)     budget per logical scenario (safety rule)   default b_k = B lambda_k^U / sum_j lambda_j^U
    Cl. 9.3 (e)     allowed failure probability, runs           p_k* = b_k / lambda_k^U;  n_k = L w_k / p_k*
    Cl. 9.3 (f)     simulator credibility (Annex C.1)           sigma^U;  delta = mu + z sigma^U;  Phi(-z)
    Cl. 9.4         validation targets (work product)           runs, targeted cases, driving hours
    Cl. 10          evaluation of known scenarios               every targeted case passes
    Cl. 11          evaluation of unknown scenarios             upper bound on every term
    Cl. 12          achievement of the SOTIF, release           sum of bounds <= R_HB, Cl. 10 passed, caps met
    sensitivity     planning aid                                what if LS k had j failures
    Cl. 13          operation phase                             field count that shows a violation; e-process
    work products   map to 6.6, 7.5, 9.4, 10.8, 11.4, 12.5, 13.5

(a)-(f) are sub-steps of this workbook, not numbered subclauses of the standard. Every step is one
function (``cl6_3_...``, ``annexC2_1_...``, ``cl9_3d_...``, ...) whose docstring gives what it
computes, the formula, parameters with units, returns, assumptions, and sources with a status label
(see below).

Two design decisions
--------------------
1. The risk budget is allocated per logical scenario (LS). Following Menzel et al. (2018), the
   operational situation of the hazardous event is the functional scenario; logical scenarios
   describe it with parameter ranges (ego speed, pedestrian speed, light, occlusion, ...); concrete
   scenarios are single parameter values (one simulation run, one targeted case). Triggering
   conditions (Cl. 7.3) are regions of the parameter space inside the logical scenarios. They steer
   the targeted cases of Clause 10 and the importance sampling of the simulation runs. They do not
   hold a budget of their own, so an encounter in which several triggering conditions are present
   (a child, at night, on a wet road) is counted once, in its logical scenario.
2. Test cost is not an input. The budget split decides how much of the tolerable rate each logical
   scenario may use, i.e. how much risk the road users in that scenario carry, and with it the
   validation targets. If test cost or test effort decided the split, the scenarios that are
   hardest to test would receive the largest budgets: more risk would be accepted exactly where
   testing is harder. Cost may decide how the evidence is produced (simulation or proving ground,
   sampling design, scheduling), never how much risk is accepted. The default rule, "equal
   protection", gives every logical scenario the same allowed failure probability per encounter.
   Input files that still contain cost keys are rejected with this explanation.

How to run
----------
    python sotif_validation_workbook.py                      # mock example (built in)
    python sotif_validation_workbook.py --write-mock my_inputs.json
    python sotif_validation_workbook.py --inputs my_inputs.json --out-dir results
    python sotif_validation_workbook.py --check              # self-test, exit code 1 on failure

A run prints a clause-by-clause report (formula in words, numbers, sources, notes) and writes
``results_<case_name>.csv`` (one row per quantity: name, symbol, value, unit, step, source) to
``--out-dir`` (default: current directory). If pandas and openpyxl are installed, it also writes
``results_<case_name>.xlsx`` (sheets "results", "per_logical_scenario", "rule_comparison",
"validation_targets"); if not, that export is skipped with a message.

The file uses "percent" cells (``# %%`` and ``# %% [markdown]``), so it also opens as a notebook in
VS Code or via Jupytext. Running all cells in a notebook runs the mock example and prints the
report; nothing is written to disk in that case.

Dependencies: numpy, scipy (required); pandas + openpyxl (optional, for .xlsx).

How to replace the mock data
----------------------------
1. ``python sotif_validation_workbook.py --write-mock my_inputs.json``
2. Edit the values in ``my_inputs.json``. Keep the keys. Keys starting with "_" are comments and are
   ignored. Unknown keys are rejected, so a typo fails loudly instead of silently falling back to a
   default. Keys of the previous version (situation_types, cost_per_run, ...) are rejected with a
   message that says what replaced them.
3. Add or remove entries in "hazardous_behaviours", "hazardous_events", "triggering_conditions"
   and "logical_scenarios" freely; K is the length of "logical_scenarios".
4. ``python sotif_validation_workbook.py --inputs my_inputs.json``

The loader checks types (counts must be integers, numbers must be finite), ranges (probabilities in
[0, 1], rates and hours positive, chain probabilities > 0) and consistency: unique ids; every
hazardous event names an existing hazardous behaviour; the selected event exists; per harm class
the shares of the listed hazardous events sum to at most 1; the benchmark is for the harm class of
the selected event and gives exactly one exposure (exposure_hours, or miles with average_speed_mph);
every triggering condition names existing logical scenarios; human shares and fixed shares are
given for all logical scenarios or none and then sum to 1; a logical scenario gives P_S or a
severity curve, not both; targeted failures do not exceed targeted cases; N1 <= N_discovery;
alt_factor > 1. Violations raise ``InputError`` with the field path.

Status of the mock data
-----------------------
All mock values are synthetic, chosen to be plausible, and describe no real system. This includes
the human benchmark (50 harm events in 1.0e7 hours, h = 5.0e-6 /h), which is a placeholder: replace
it with human accident data matched to the ODD (road type, speed, time of day), e.g. GIDAS or
national statistics. Its quantities carry the label "input (synthetic)".

Source labels
-------------
Each formula's source carries exactly one of these labels:
    checked                 location confirmed in the course verification log
    location not checked    the source is right, but page/section not verified
    derived in this course  a construction of the course, not a published formula
Input values carry the label "input" and the source text given in the input file. Clause titles of
ISO 21448:2022 are taken from its table of contents; a claim about the content of a clause whose
pages are not in the verification log (6.3, 6.4, 7.3, 7.4, 8.3.3, 9.3, 12.4, 13.4 and the
work-product subclauses) is labelled "location not checked".

Notation
--------
    symbol          code name                   unit     meaning
    --------------  --------------------------  -------  ---------------------------------------------
    HB, HE          ids in the input            -        hazardous behaviour, hazardous event
    LS, TC          ids in the input            -        logical scenario, triggering condition
    h               h                           1/h      human harm rate per hour in the ODD (harm class),
                                                         events / exposure hours
    A_H             A_H                         1/h      acceptable harm rate attributed to the selected HE
    P_E             chain.P_E                   -        P(E | HB): the HB meets an exposed person
    P_C             chain.P_C                   -        P(not C | E): the event is not avoided
    P_S             chain.P_S                   -        P(S | not C): the collision causes the harm
    G, G_k          P_chain, G                  -        P_E P_C P_S of the HE (G) or of LS k (G_k, optional
                                                         per-LS chain); G_unk for unknown scenarios
    R_HB            R_HB                        1/h      tolerable rate of the hazardous behaviour in this HE
    C               confidence.C                -        joint confidence of the release claim
    m               m                           -        number of simultaneous bounds (Bonferroni)
    C_b             C_b                         -        per-bound confidence, 1 - (1 - C)/m
    L               L                           -        zero-failure factor, ln(1/(1 - C_b))
    F(j)            failure_factor(j, C_b)      -        j-failure factor, chi2_{C_b}(2j + 2)/2; F(0) = L
    K               K                           -        number of logical scenarios
    N_k             N_pilot, N_conf             count    encounters of LS k counted while driving
    tau             *_hours                     h        driving hours (pilot, confirmatory, discovery)
    lambda_k^U      lambda_U_*                  1/h      upper bound on the encounter rate of LS k
    f               reserve_fraction            -        share of R_HB kept for unknown scenarios
    b_unk           b_unk                       1/h      reserve, f * R_HB
    B               B                           1/h      budget for the K logical scenarios, R_HB - b_unk
    A'              A_prime                     1/h      harm budget for the K logical scenarios, (1 - f) A_H
                                                         (= G B with one chain)
    a_k             harm_budget                 1/h      harm budget of LS k; b_k = a_k / G_k
    v_k             weights                     varies   weight of LS k under the budget rule (a_k ~ v_k)
    s_k             human_share                 -        share of this harm human drivers cause in LS k
    h_k             human_cap_behaviour_rate    1/h      human-level rate of the behaviour in LS k (cap)
    b_k             b                           1/h      budget of LS k
    p_k*            p_star                      -        allowed failure probability per encounter in LS k
    w_k             importance_factor           -        largest importance weight p/q in the failure
                                                         region of LS k (1 = plain Monte Carlo)
    n_k             n                           runs     simulation runs needed with zero failures
    j_k             failures                    count    failures in the confirmatory simulation runs
    mu, sigma       mu_hat, sigma_hat           m        bias and spread of (y_sim - y_real)
    sigma^U         sigma_U                     m        upper bound on sigma at confidence C_b
    z               z                           -        simulator margin in units of sigma^U
    delta           delta                       m        simulator margin, mu + z sigma^U
    Phi(-z)         p_miss                      -        P(error > delta) under a Gaussian error model
    p_k^U           p_U                         -        upper bound on the failure probability in LS k
    lambda_new^U    lambda_new_U                1/h      upper bound on the rate of unknown scenarios
    p_new           p_new                       -        failure probability in an unknown scenario
                                                         (argued from a design rule, not tested)
    N1, N           N1, N_discovery             count    Good-Turing singletons, total encounters
    T               fleet_hours_per_year        h/yr     fleet driving per year of operation
    lambda_L        poisson_lower_rate          1/h      lower confidence bound on the field rate
    k_min           k_min                       count    smallest yearly count with lambda_L > R_HB
    E(T)            e_value                     -        likelihood-ratio e-process of the field count
    a               alt_factor                  -        alternative rate of the e-process, a x R_HB

Conventions and limits
----------------------
Rates are per hour of driving in the ODD; probabilities are per encounter. All evidence is assumed
to come from one frozen software release. By default one harm chain (Cl. 6.4) is used for the whole
hazardous event, i.e. for all its logical scenarios; optional per-LS chains move the budget and the
release claim to harm units, and with one common chain the two forms are identical. The workbook
checks arithmetic and input ranges; it does not check whether the modelling assumptions hold. Each
step's docstring and markdown cell names the assumption to defend.

Literature map (which source feeds which step)
----------------------------------------------
    source (status)                                          used for                        step
    Littlewood & Wright 1997 (checked)                       Formula (C.7), zero-failure     Annex C.3, 9.3 (e)
    Kalra & Paddock 2016, RAND RR-1478 (checked)             naive driving target            Annex C.3
    Putze et al. 2023, arXiv:2304.10170, IV-B(b) (checked)   full conditioning per LS; sum   6.4, 9.3 (d), 11, 12
                                                             of upper bounds
    Wang 2022, NHTSA DOT HS 813 219, Table 1-1               P_S from a logistic injury-     6.4 (optional curve)
      (location not checked)                                 risk curve
    Kroeger 2025, Next Research 2:100238                     plausibility of the criterion   6.5 (note)
      (location not checked)
    Menzel et al. 2018, arXiv:1801.08598                     functional / logical /          7.3
      (location not checked)                                 concrete scenarios
    de Gelder & Op den Camp 2024 (location not checked)      scenario parameterisation       7.3, 9.3 (b)
    Hofmeister & Kinalzyk (AVL, ca. 2023), Sec. 2.2          budget hierarchy, one           9.3 (d), 9.4
      (location not checked)                                 validation target per class
    Warg et al. 2020, QRN, Sec. III-B (location not checked) budgets add up                  6.3, 9.3 (c)-(d)
    Werling et al. 2025, arXiv:2503.20544, Sec. 3.3,         budgets frozen before the       9.3 (d)
      Remark 3.7 (location not checked)                      confirmatory campaign
    Owen 2013, Ch. 9 (checked); Zhao et al. 2017, IEEE       importance sampling             9.3 (e), 11
      T-ITS 18(3) (checked)
    Feng et al. 2023, Nature 615:620-627; Moss et al. 2023   scenario exploration (search    7.3, 11 (note)
      (both checked at abstract level)                       for failures and new scenarios)
    Patel & Jung 2026, arXiv:2610.35092, Sec. 3.5            independent evidence units;     10, 11
      (location not checked)                                 evidence per triggering condition
    Betschinske et al. 2025, arXiv:2506.10363, Sec. VII      no efficiency method fully      11 (note)
      (checked)                                              replaces field testing
    Good 1953 (location not checked); Berend & Kontorovich   missing mass of unseen          11
      2013, Theorem 1 (checked)                              scenarios
    Garwood 1936, Sec. 4 p. 441 (checked); Porter 2025 (checked) Poisson upper and lower limits  9.3 (b), 11, 13
    Ramdas, Gruenwald, Vovk & Shafer 2023, Statistical       anytime-valid monitoring,       13
      Science 38(4), arXiv:2210.01948 (checked at abstract   e-process and Ville's
      level); Wald 1945, SPRT (location not checked)         inequality

Related open-source work (found by web search on 2 Nov 2026; none implements this whole chain)
---------------------------------------------------------------------------------------------
- janlucakaestle/adas-validation-agent: SOTIF-style validation of a learned ACC in simulation
  with exposure-weighted estimation and acceptance criteria fixed before testing.
- milinpatel07/lidar-performance-target-applicability: code for Patel & Jung (2026), whether
  a performance target shown under one triggering condition holds under another.
- michigan-traffic-lab/Dense-Deep-Reinforcement-Learning: code for Feng et al. (2023), Nature
  615:620-627, accelerated testing of rare events with dense RL.
- MelkorBalrog/AutoML: general safety-engineering tool covering ISO 26262 / ISO 21448 analyses.
- GitHub topic "iso-21448" lists further perception-evaluation projects.
These were found, not reviewed; check licence and maturity before reuse.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import re
import sys
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import numpy as np
from scipy.stats import beta, chi2, norm, poisson

# %% [markdown]
# ## Mock inputs: robotaxi crosswalk example
#
# Hazard analysis (Cl. 6.3): six hazardous behaviours of an urban robotaxi at vehicle level (no
# situation named), and four hazardous events of HB-1 "does not yield", each with its own harm class.
# The chain follows HE-1.1, a pedestrian about to cross at a zebra crossing (harm class "pedestrian
# injury"). Three logical scenarios are derived from that event (clear view, emerging from behind a
# stationary vehicle, robotaxi turning in), and five triggering conditions mark regions inside them
# (occlusion, low light, wet road, child, short time to arrival). All values are synthetic, including
# the human benchmark, which is a placeholder for human accident data matched to the ODD.
# `write_mock_inputs(path)` writes this dictionary as JSON; that file is the template for real data.
# Keys starting with "_" are comments for the reader and are ignored by the loader. Optional keys
# that are null by default (per-LS chain, severity curve, unknown-scenario chain) show where the
# literature options of the workbook plug in.

# %%
MOCK_INPUTS_ROBOTAXI: dict[str, Any] = {
    "_about": (
        "Mock inputs for the robotaxi crosswalk example of the SOTIF course (doc 14), structured along "
        "ISO 21448:2022. All values are synthetic, including the human benchmark. Replace the values with "
        "your own data and keep the keys. Keys starting with '_' are comments and are ignored by the "
        "loader; unknown keys are rejected. Test cost is deliberately not an input: cost may decide how "
        "evidence is produced, never how much risk is accepted."
    ),
    "case_name": "robotaxi",
    "function": "Urban robotaxi (SAE Level 4), roads up to 50 km/h, day and night, dry and wet.",
    "hazardous_behaviours": [
        {
            "_note": "Cl. 6.3. Vehicle level: no situation named. ISO 21448 6.5 sets acceptance criteria "
                     "per hazardous behaviour.",
            "id": "HB-1",
            "description": "Does not yield: no or too little deceleration although another road user has "
                           "right of way",
        },
        {"id": "HB-2", "description": "Unintended braking"},
        {"id": "HB-3", "description": "Unintended acceleration"},
        {"id": "HB-4", "description": "Unintended steering"},
        {"id": "HB-5", "description": "Insufficient deceleration"},
        {"id": "HB-6", "description": "Loss of braking, steering or propulsion"},
    ],
    "hazardous_events": [
        {
            "_units": (
                "Cl. 6.3. One hazardous behaviour (hb_id) in one operational situation. severity and "
                "controllability: rating text from the HARA. share_of_harm_class_budget: fraction of the "
                "harm-class budget given to this event [-]; per harm class the shares of all hazardous "
                "events (of all hazardous behaviours) must sum to at most 1."
            ),
            "id": "HE-1.1",
            "hb_id": "HB-1",
            "operational_situation": "Pedestrian about to cross at a zebra crossing",
            "harm_class": "pedestrian injury",
            "severity": "S2-S3",
            "controllability": "low",
            "share_of_harm_class_budget": 0.2,
        },
        {
            "id": "HE-1.2",
            "hb_id": "HB-1",
            "operational_situation": "Cyclist going straight while the robotaxi turns right",
            "harm_class": "cyclist injury",
            "severity": "S2-S3",
            "controllability": "low",
            "share_of_harm_class_budget": 0.2,
        },
        {
            "id": "HE-1.3",
            "hb_id": "HB-1",
            "operational_situation": "Oncoming vehicle at an unprotected left turn",
            "harm_class": "occupant injury",
            "severity": "S1-S3",
            "controllability": "medium",
            "share_of_harm_class_budget": 0.1,
        },
        {
            "id": "HE-1.4",
            "hb_id": "HB-1",
            "operational_situation": "Vehicle with right of way at an unsignalised junction",
            "harm_class": "occupant injury",
            "severity": "S1-S3",
            "controllability": "medium",
            "share_of_harm_class_budget": 0.1,
        },
    ],
    "selected_hazardous_event": "HE-1.1",
    "benchmark": {
        "_units": (
            "Cl. 6.5. harm_class: must equal the harm class of the selected hazardous event; events: human "
            "harm events over the benchmark exposure [count]; exposure_hours: human driving hours in a "
            "comparable ODD [h]. Alternative to exposure_hours (give exactly one of the two): miles [mi] "
            "with average_speed_mph [mi/h], then exposure = miles / speed. source_note: where the data come "
            "from; synthetic: true marks placeholder data (label 'input (synthetic)'), set it to false or "
            "remove it for real data"
        ),
        "harm_class": "pedestrian injury",
        "events": 50,
        "exposure_hours": 1.0e7,
        "source_note": (
            "Synthetic placeholder. Replace with human accident data matched to the ODD (road type, speed, "
            "time of day), e.g. GIDAS or national statistics."
        ),
        "synthetic": True,
    },
    "criterion": {
        "_units": (
            "Cl. 6.5. margin_factor: robotaxi harm rate / human harm rate [-] (0.1 = ten times better); "
            "round_A_H_to: round A_H to the nearest multiple of this [1/h], null = no rounding. The share "
            "of the harm-class budget comes from the selected hazardous event."
        ),
        "margin_factor": 0.1,
        "round_A_H_to": None,
    },
    "chain": {
        "_units": (
            "Cl. 6.4, for the selected hazardous event. P_E = P(E | HB), P_C = P(not C | E), "
            "P_S = P(S | not C); all [-], in (0, 1]"
        ),
        "P_E": 0.5,
        "P_C": 0.5,
        "P_S": 0.8,
    },
    "confidence": {
        "_units": "C: joint confidence [-]; m_bounds: number of simultaneous bounds, null = 2K + 2",
        "C": 0.95,
        "m_bounds": None,
    },
    "fleet": {
        "_units": "cars [count]; hours_per_day_per_car [h/day]",
        "cars": 100,
        "hours_per_day_per_car": 20,
    },
    "driving": {
        "_units": (
            "pilot_hours: fleet hours used to estimate exposure for planning [h]; confirmatory_hours: "
            "fleet hours on the frozen release for the verdict [h]; discovery_hours: hours searched for "
            "scenarios outside the K logical scenarios [h] (here the same 20,000 h as the confirmatory "
            "driving)"
        ),
        "pilot_hours": 1000,
        "confirmatory_hours": 20000,
        "discovery_hours": 20000,
    },
    "budget": {
        "_units": (
            "reserve_fraction: share of R_HB kept for unknown scenarios (Cl. 11) [-], in [0, 1); "
            "allocation_rule: 'equal_protection' (default: same allowed failure probability per encounter "
            "in every logical scenario), 'proportional_to_human' (needs human_share), 'equal_split' "
            "(for comparison only) or 'fixed' (needs fixed_share)"
        ),
        "reserve_fraction": 0.1,
        "allocation_rule": "equal_protection",
    },
    "unknown": {
        "_units": (
            "p_new: failure probability per encounter with an unknown scenario [-], argued from a design "
            "rule, not tested statistically; N1: kinds of scenario seen exactly once in the discovery data "
            "[count] (a kind outside the K logical scenarios would show up here; 0 = none appeared); "
            "N_discovery: encounters classified in the discovery data [count], null = unknown (here "
            "80,000 + 10,000 + 6,000 from the confirmatory driving)"
        ),
        "p_new": 1e-4,
        "p_new_rationale": (
            "Functional restriction (Cl. 8.3.3): any unclassified object within 3 m of a crosswalk caps the "
            "speed at 10 km/h; the fallback is tested on its own."
        ),
        "G_unknown": None,
        "_G_unknown": (
            "G_unknown: probability that one occurrence of the behaviour in an unknown scenario causes the "
            "harm [-], in (0, 1]; null = the common chain of the hazardous event (P_E P_C P_S). Only matters "
            "when logical scenarios have their own chains; a conservative choice is the largest G_k."
        ),
        "N1": 0,
        "N_discovery": 96000,
    },
    "triggering_conditions": [
        {
            "_units": (
                "Cl. 7.3. A triggering condition is a region of the parameter space inside one or more "
                "logical scenarios: logical_scenarios = list of LS ids, or \"all\". It holds no budget; it "
                "steers the targeted cases (Cl. 10) and the importance sampling (Annex C.5)."
            ),
            "id": "TC-1",
            "description": "Occlusion by a stationary vehicle (parked car, van, bus)",
            "parameter_region": "occluder type car, van or bus between pedestrian and robotaxi; defines LS-2",
            "logical_scenarios": ["LS-2"],
        },
        {
            "id": "TC-2",
            "description": "Low light (dusk, night)",
            "parameter_region": "light = dusk or night",
            "logical_scenarios": "all",
        },
        {
            "id": "TC-3",
            "description": "Wet road, reflections",
            "parameter_region": "road = wet",
            "logical_scenarios": "all",
        },
        {
            "id": "TC-4",
            "description": "Small pedestrian (child)",
            "parameter_region": "pedestrian size = child",
            "logical_scenarios": "all",
        },
        {
            "id": "TC-5",
            "description": "Short time to arrival at high approach speed",
            "parameter_region": "time to arrival <= 1.5 s at approach speed >= 40 km/h",
            "logical_scenarios": ["LS-1", "LS-2"],
        },
    ],
    "logical_scenarios": [
        {
            "_units": (
                "Derived from the selected hazardous event (functional -> logical -> concrete scenarios). "
                "N_pilot, N_conf: encounters counted in pilot / confirmatory driving [count]; "
                "importance_factor w_k: largest importance weight p/q in the failure region [-], in (0, 1] "
                "(1 = plain Monte Carlo); human_share s_k: share of this harm that human drivers cause in "
                "this LS [-], all LS sum to 1, null = not known; human_cap_behaviour_rate h_k: human-level "
                "rate of the behaviour in this LS [1/h], null = no cap; targeted_cases, targeted_failures: "
                "Clause 10 cases built from the triggering conditions and how many failed [count]; "
                "failures j_k: failures in the confirmatory simulation runs [count]; runs_executed: runs "
                "actually executed, null = the planned n_k; fixed_share: only for allocation_rule 'fixed', "
                "all LS sum to 1. Optional per-LS harm chain (Putze et al. 2023): P_E, P_C, P_S [-] in (0, 1], "
                "null = the chain of the hazardous event; severity_curve {beta0, beta1, impact_speed, "
                "source_note}: P_S = 1/(1 + exp(-(beta0 + beta1 impact_speed))), instead of P_S (not both), "
                "impact_speed in the unit the coefficients were fitted for. independent_units_note: why the "
                "runs and targeted cases are independent evidence units (text)"
            ),
            "id": "LS-1",
            "name": "Pedestrian approaches the crossing in clear view",
            "parameters": (
                "ego speed 20-50 km/h; pedestrian speed 0.8-2.5 m/s; time to arrival 0.5-5 s; light (day, "
                "dusk, night); road (dry, wet); pedestrian size (adult, child)"
            ),
            "N_pilot": 4000,
            "N_conf": 80000,
            "importance_factor": 0.01,
            "human_share": 0.50,
            "human_cap_behaviour_rate": 2.5e-6,
            "targeted_cases": 48,
            "targeted_case_design": (
                "light (day, dusk, night) x road (dry, wet) x pedestrian (adult, child) x 4 approach speeds "
                "(20, 30, 40, 50 km/h) = 48"
            ),
            "targeted_failures": 0,
            "failures": 0,
            "runs_executed": None,
            "fixed_share": None,
            "P_E": None,
            "P_C": None,
            "P_S": None,
            "severity_curve": None,
            "independent_units_note": (
                "One run = one concrete scenario drawn independently from the LS-1 parameter distribution (own "
                "seed); each targeted case is a distinct parameter combination; no frames or slices of one run "
                "are counted separately."
            ),
        },
        {
            "id": "LS-2",
            "name": "Pedestrian emerges from behind a stationary vehicle at the crossing",
            "parameters": (
                "as LS-1, plus occluder type (car, van, bus) and lateral gap between occluder and crossing"
            ),
            "N_pilot": 500,
            "N_conf": 10000,
            "importance_factor": 0.05,
            "human_share": 0.35,
            "human_cap_behaviour_rate": 1.75e-6,
            "targeted_cases": 144,
            "targeted_case_design": (
                "light (day, dusk, night) x road (dry, wet) x pedestrian (adult, child) x 4 approach speeds "
                "(20, 30, 40, 50 km/h) x 3 occluders (car, van, bus) = 144"
            ),
            "targeted_failures": 0,
            "failures": 0,
            "runs_executed": None,
            "fixed_share": None,
            "P_E": None,
            "P_C": None,
            "P_S": None,
            "severity_curve": None,
            "independent_units_note": (
                "As LS-1; each occluder type is tested under every triggering condition it is combined with, "
                "since evidence under one condition does not carry over to another."
            ),
        },
        {
            "id": "LS-3",
            "name": "Robotaxi turns into the street and meets a pedestrian on the crossing",
            "parameters": (
                "turning speed 10-30 km/h; pedestrian position on the crossing; pedestrian speed 0.8-2.5 m/s; "
                "light (day, dusk, night); road (dry, wet); pedestrian size (adult, child)"
            ),
            "N_pilot": 300,
            "N_conf": 6000,
            "importance_factor": 0.10,
            "human_share": 0.15,
            "human_cap_behaviour_rate": 7.5e-7,
            "targeted_cases": 48,
            "targeted_case_design": (
                "light (day, dusk, night) x road (dry, wet) x pedestrian (adult, child) x 4 approach "
                "(turning) speeds (10, 15, 20, 30 km/h) = 48"
            ),
            "targeted_failures": 0,
            "failures": 0,
            "runs_executed": None,
            "fixed_share": None,
            "P_E": None,
            "P_C": None,
            "P_S": None,
            "severity_curve": None,
            "independent_units_note": "As LS-1.",
        },
    ],
    "simulator": {
        "_units": (
            "Annex C.1. m_pairs: paired sim/real runs [count]; mu_hat, sigma_hat: mean and standard "
            "deviation of e = y_sim - y_real [m], where y is the distance between robotaxi and pedestrian "
            "when the pedestrian reaches the conflict zone; z_mode: 'fixed' or 'auto'; z_fixed [-]; "
            "z_auto_fraction f [-]: auto mode picks z with Phi(-z) = f * min_k p_k*"
        ),
        "m_pairs": 180,
        "mu_hat": 0.05,
        "sigma_hat": 0.15,
        "z_mode": "fixed",
        "z_fixed": 6.5,
        "z_auto_fraction": 0.01,
    },
    "operation": {
        "_units": (
            "Cl. 13. fleet_hours_per_year: planned fleet driving per year of operation [h/yr] "
            "(100 cars x 20 h x 365 days); alt_factor a [-], > 1: the e-process tests R_HB against the "
            "alternative a x R_HB, null = 2; hb_detection_rule: how a hazardous behaviour is counted in the "
            "field (text)"
        ),
        "fleet_hours_per_year": 730000,
        "alt_factor": 2,
        "hb_detection_rule": (
            "HB-1 is counted when the robotaxi enters the conflict zone of a crossing above 10 km/h while a "
            "pedestrian with right of way is less than 2 s from it (on-board monitoring, Cl. 13.3)."
        ),
    },
}

# %% [markdown]
# ## Input data model and loader
#
# All inputs live in one frozen dataclass `WorkbookInputs` with nested sections. The loader
# `inputs_from_dict` (and `load_inputs` for a JSON file) checks every field for type, range and
# consistency and raises `InputError` with the field path. Strict checking is deliberate: in a safety
# argument a silently defaulted value is worse than a crash. Two kinds of old input are refused with
# an explanation: any cost key (cost is no longer an input, see the module docstring), and keys that
# were renamed when the budget moved from "situation types" to logical scenarios.

# %%
class InputError(ValueError):
    """Raised when an input is missing, has the wrong type, is out of range, or is no longer an input."""


ALLOCATION_RULES: tuple[str, ...] = ("equal_protection", "proportional_to_human", "equal_split", "fixed")

COST_NOT_AN_INPUT = (
    "cost is no longer an input. The budget split decides how much risk each logical scenario may carry "
    "and therefore the validation targets; letting test cost or test effort decide it would accept more "
    "risk exactly where testing is harder. Cost may decide how evidence is produced, never how much risk "
    "is accepted. Remove these keys."
)

# Keys of the previous version of the workbook and what replaced them (used in error messages).
_RENAMED_KEYS: dict[str, str] = {
    "situation_types": "was renamed to 'logical_scenarios' (the budget is allocated per logical scenario)",
    "hazardous_behaviour": "was replaced by the list 'hazardous_behaviours' (Cl. 6.3 record)",
    "operational_situation": "is now a field of each entry of 'hazardous_events'",
    "hazardous_event": "was replaced by the list 'hazardous_events' and 'selected_hazardous_event'",
    "share_of_harm_budget": "moved to hazardous_events[].share_of_harm_class_budget",
    "human_cap": "was renamed to 'human_cap_behaviour_rate'",
    "actual_runs": "was renamed to 'runs_executed'",
    "source": "was replaced by 'source_note'",
    "speed_source": "was replaced by 'source_note' (give exposure_hours directly, or miles with average_speed_mph)",
}

# Plausibility reference for Cl. 6.5: Kroeger (2025), "How safe should automated vehicles be?", Next Research
# 2:100238, proposes about these vehicle-level targets for automated vehicles [location not checked].
KROEGER_FATALITIES_PER_H = 3e-9
KROEGER_FATAL_OR_SERIOUS_PER_H = 4e-8


@dataclass(frozen=True)
class HazardousBehaviour:
    id: str           # e.g. "HB-1"
    description: str  # vehicle-level behaviour, no situation named


@dataclass(frozen=True)
class HazardousEvent:
    id: str                                   # e.g. "HE-1.1"
    hb_id: str                                # the hazardous behaviour this event belongs to
    operational_situation: str                # where the behaviour meets the exposed person
    harm_class: str                           # e.g. "pedestrian injury"; selects benchmark and budget
    share_of_harm_class_budget: float         # fraction of the harm-class budget for this event [-]
    severity: str = ""                        # rating text from the HARA, e.g. "S2-S3"
    controllability: str = ""                 # rating text from the HARA, e.g. "low"


@dataclass(frozen=True)
class Benchmark:
    harm_class: str                            # harm class of the benchmark; must match the selected event
    events: float                              # human harm events over the exposure [count]
    exposure_hours: Optional[float] = None     # human driving hours in a comparable ODD [h]
    miles: Optional[float] = None              # alternative: exposure in miles [mi] ...
    average_speed_mph: Optional[float] = None  # ... with the average speed incl. stops [mi/h]
    source_note: str = ""                      # where the data come from
    synthetic: bool = False                    # True for placeholder data: label "input (synthetic)"

    @property
    def hours(self) -> float:
        """Exposure in hours: exposure_hours, or miles / average_speed_mph."""
        if self.exposure_hours is not None:
            return self.exposure_hours
        return self.miles / self.average_speed_mph  # type: ignore[operator]

    @property
    def label(self) -> str:
        return "input (synthetic)" if self.synthetic else "input"


@dataclass(frozen=True)
class Criterion:
    margin_factor: float                  # target harm rate / human harm rate [-], in (0, 1]
    round_A_H_to: Optional[float] = None  # round A_H to nearest multiple of this [1/h]; None = no rounding


@dataclass(frozen=True)
class HarmChain:
    P_E: float  # P(E | HB): the behaviour meets an exposed person [-], in (0, 1]
    P_C: float  # P(not C | E): the hazardous event is not avoided [-], in (0, 1]
    P_S: float  # P(S | not C): the uncontrolled event causes the harm considered [-], in (0, 1]


@dataclass(frozen=True)
class Confidence:
    C: float                        # joint confidence of the final claim [-], in (0, 1)
    m_bounds: Optional[int] = None  # number of simultaneous bounds [-]; None = 2K + 2


@dataclass(frozen=True)
class Fleet:
    cars: float                   # vehicles in the fleet [count]
    hours_per_day_per_car: float  # driving hours per car per day [h/day], in (0, 24]


@dataclass(frozen=True)
class Driving:
    pilot_hours: float         # tau_pilot: hours used for planning exposure bounds [h]
    confirmatory_hours: float  # tau_conf: hours on the frozen release for the verdict [h]
    discovery_hours: float     # tau_disc: hours searched for scenarios outside the K logical scenarios [h]


@dataclass(frozen=True)
class Budget:
    reserve_fraction: float                  # f: share of R_HB kept for unknown scenarios [-], in [0, 1)
    allocation_rule: str = "equal_protection"  # one of ALLOCATION_RULES


@dataclass(frozen=True)
class Unknown:
    p_new: float                       # failure probability per unknown-scenario encounter [-], argued
    N1: int                            # scenario kinds seen exactly once in discovery data [count]
    N_discovery: Optional[int] = None  # encounters classified in discovery data [count]; None = unknown
    p_new_rationale: str = ""          # the design rule that argues p_new (e.g. a Cl. 8.3.3 restriction)
    G_unknown: Optional[float] = None  # harm chain for unknown scenarios [-]; None = the HE's common chain


@dataclass(frozen=True)
class TriggeringCondition:
    id: str                              # e.g. "TC-1"
    description: str                     # what the condition is
    logical_scenarios: tuple[str, ...]   # LS ids the region lies in ("all" expanded)
    applies_to_all: bool = False         # True if the input said "all"
    parameter_region: str = ""           # the region in parameter terms (text)


@dataclass(frozen=True)
class SeverityCurve:
    beta0: float          # intercept of the logistic injury-risk curve [-]
    beta1: float          # slope per unit of impact speed [1/(speed unit)]
    impact_speed: float   # representative impact speed in this LS [unit the curve was fitted for]
    source_note: str = ""

    @property
    def P_S(self) -> float:
        """P(S | delta v) = 1 / (1 + exp(-(beta0 + beta1 * delta v)))."""
        return logistic_severity(self.beta0, self.beta1, self.impact_speed)


@dataclass(frozen=True)
class LogicalScenario:
    id: str                                            # e.g. "LS-1"
    name: str                                          # short description
    N_pilot: int                                       # encounters counted in pilot driving [count]
    N_conf: int                                        # encounters counted in confirmatory driving [count]
    importance_factor: float                           # w_k: max importance weight in failure region [-]
    targeted_cases: int                                # Clause 10 cases from the triggering conditions [count]
    targeted_failures: int = 0                         # targeted cases that failed [count]
    failures: int = 0                                  # j_k: failures in confirmatory simulation runs [count]
    human_share: Optional[float] = None                # s_k: share of this harm human drivers cause here [-]
    human_cap_behaviour_rate: Optional[float] = None   # h_k: human-level behaviour rate in this LS [1/h]
    runs_executed: Optional[float] = None              # runs executed; None = planned n_k [runs]
    fixed_share: Optional[float] = None                # harm share for allocation_rule "fixed" [-]
    P_E: Optional[float] = None                        # per-LS P(E | HB) [-]; None = the HE's chain
    P_C: Optional[float] = None                        # per-LS P(not C | E) [-]; None = the HE's chain
    P_S: Optional[float] = None                        # per-LS P(S | not C) [-]; None = the HE's chain
    severity_curve: Optional[SeverityCurve] = None     # per-LS P_S from an injury-risk curve (not with P_S)
    parameters: str = ""                               # parameter ranges (text)
    targeted_case_design: str = ""                     # how the targeted cases were built (text)
    independent_units_note: str = ""                   # why runs and cases are independent units (text)
    description: str = ""                              # free text


@dataclass(frozen=True)
class Simulator:
    m_pairs: int                   # paired sim/real runs [count], >= 2
    mu_hat: float                  # mean of e = y_sim - y_real [m]
    sigma_hat: float               # sample standard deviation of e [m], > 0
    z_mode: str = "fixed"          # "fixed" or "auto"
    z_fixed: float = 6.5           # z used in fixed mode [-]
    z_auto_fraction: float = 0.01  # f in Phi(-z) = f * min_k p_k* for auto mode [-]


@dataclass(frozen=True)
class Operation:
    fleet_hours_per_year: float    # T: fleet driving per year of operation [h/yr]
    hb_detection_rule: str = ""    # how a hazardous behaviour is counted in the field (text)
    alt_factor: float = 2.0        # a: e-process alternative rate a x R_HB [-], > 1


@dataclass(frozen=True)
class WorkbookInputs:
    case_name: str
    function: str
    hazardous_behaviours: tuple[HazardousBehaviour, ...]
    hazardous_events: tuple[HazardousEvent, ...]
    selected_hazardous_event: str
    benchmark: Benchmark
    criterion: Criterion
    chain: HarmChain
    confidence: Confidence
    fleet: Fleet
    driving: Driving
    budget: Budget
    unknown: Unknown
    triggering_conditions: tuple[TriggeringCondition, ...]
    logical_scenarios: tuple[LogicalScenario, ...]
    simulator: Simulator
    operation: Operation

    @property
    def K(self) -> int:
        """Number of logical scenarios."""
        return len(self.logical_scenarios)

    @property
    def ls_ids(self) -> list[str]:
        return [s.id for s in self.logical_scenarios]

    @property
    def selected_he(self) -> HazardousEvent:
        return next(e for e in self.hazardous_events if e.id == self.selected_hazardous_event)

    @property
    def selected_hb(self) -> HazardousBehaviour:
        hb_id = self.selected_he.hb_id
        return next(h for h in self.hazardous_behaviours if h.id == hb_id)


def _check_keys(d: Mapping[str, Any], allowed: set[str], where: str) -> None:
    """Reject unknown keys (keys starting with '_' are comments and are ignored)."""
    if not isinstance(d, Mapping):
        raise InputError(f"{where}: expected an object, got {type(d).__name__}")
    unknown = sorted(k for k in d if not str(k).startswith("_") and k not in allowed)
    if unknown:
        msg = f"{where}: unknown key(s) {unknown}; allowed: {sorted(allowed)}"
        hints = [f"'{k}' {_RENAMED_KEYS[k]}" for k in unknown if k in _RENAMED_KEYS]
        if hints:
            msg += ". Note: " + "; ".join(hints)
        raise InputError(msg)


def _reject_cost_keys(raw: Any) -> None:
    """Refuse any cost key anywhere in the input (cost is no longer an input; see COST_NOT_AN_INPUT)."""
    found: list[str] = []

    def walk(o: Any, path: str) -> None:
        if isinstance(o, Mapping):
            for k, v in o.items():
                ks = str(k)
                if ks.startswith("_"):
                    continue  # comments
                if ks in ("run_time_s", "compute_price_eur_per_h") or "cost" in ks.lower():
                    found.append(f"{path}.{ks}")
                walk(v, f"{path}.{ks}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")

    walk(raw, "inputs")
    if found:
        raise InputError(f"{', '.join(found)}: {COST_NOT_AN_INPUT}")


def _num(
    d: Mapping[str, Any],
    key: str,
    where: str,
    *,
    integer: bool = False,
    lo: Optional[float] = None,
    hi: Optional[float] = None,
    lo_open: bool = False,
    hi_open: bool = False,
    optional: bool = False,
) -> Any:
    """Read one number with type and range checks. Returns None for an absent optional field."""
    path = f"{where}.{key}"
    if key not in d or d[key] is None:
        if optional:
            return None
        raise InputError(f"{path}: missing (required)")
    v = d[key]
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise InputError(f"{path}: expected a number, got {type(v).__name__} {v!r}")
    if not math.isfinite(float(v)):
        raise InputError(f"{path}: must be finite, got {v!r}")
    if integer:
        if isinstance(v, float):
            if not v.is_integer():
                raise InputError(f"{path}: expected an integer count, got {v!r}")
            v = int(v)
    else:
        v = float(v)
    if lo is not None and (v < lo or (lo_open and v == lo)):
        raise InputError(f"{path} = {v!r}: must be {'>' if lo_open else '>='} {lo}")
    if hi is not None and (v > hi or (hi_open and v == hi)):
        raise InputError(f"{path} = {v!r}: must be {'<' if hi_open else '<='} {hi}")
    return v


def _str(d: Mapping[str, Any], key: str, where: str, *, optional: bool = False, default: str = "") -> str:
    path = f"{where}.{key}"
    if key not in d or d[key] is None:
        if optional:
            return default
        raise InputError(f"{path}: missing (required)")
    if not isinstance(d[key], str):
        raise InputError(f"{path}: expected a string, got {type(d[key]).__name__}")
    return d[key]


def _bool(d: Mapping[str, Any], key: str, where: str, default: bool = False) -> bool:
    if key not in d or d[key] is None:
        return default
    if not isinstance(d[key], bool):
        raise InputError(f"{where}.{key}: expected true or false, got {d[key]!r}")
    return d[key]


def _id(d: Mapping[str, Any], where: str, key: str = "id") -> str:
    s = _str(d, key, where).strip()
    if not s:
        raise InputError(f"{where}.{key}: must not be empty")
    return s


def _section(raw: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    if key not in raw:
        raise InputError(f"{key}: missing section")
    return raw[key]


def _list(raw: Mapping[str, Any], key: str, *, allow_empty: bool = False) -> list:
    if key not in raw:
        raise InputError(f"{key}: missing section")
    v = raw[key]
    if not isinstance(v, list) or (not v and not allow_empty):
        raise InputError(f"{key}: expected a {'list' if allow_empty else 'non-empty list'}")
    return v


def _unique(ids: Sequence[str], where: str) -> None:
    dup = sorted({i for i in ids if list(ids).count(i) > 1})
    if dup:
        raise InputError(f"{where}: ids must be unique, duplicated: {dup}")


def harm_class_share_sums(events: Sequence[HazardousEvent]) -> dict[str, float]:
    """Sum of share_of_harm_class_budget per harm class (grouped case-insensitively, first spelling kept)."""
    sums: dict[str, float] = {}
    spelling: dict[str, str] = {}
    for e in events:
        key = e.harm_class.strip().lower()
        spelling.setdefault(key, e.harm_class.strip())
        sums[key] = sums.get(key, 0.0) + e.share_of_harm_class_budget
    return {spelling[k]: v for k, v in sums.items()}


def _shares_all_or_none(scen: Sequence[LogicalScenario], attr: str) -> None:
    vals = [getattr(s, attr) for s in scen]
    given = [v is not None for v in vals]
    if any(given) and not all(given):
        missing = [s.id for s, g in zip(scen, given) if not g]
        raise InputError(f"logical_scenarios: {attr} must be given for every logical scenario or for none; "
                         f"missing for {missing}")
    if all(given):
        total = float(sum(vals))
        if abs(total - 1.0) > 1e-6:
            raise InputError(f"logical_scenarios: {attr} must sum to 1 over all logical scenarios, got {total:.6g}")


def inputs_from_dict(raw: Mapping[str, Any]) -> WorkbookInputs:
    """Build and validate `WorkbookInputs` from a dictionary (e.g. parsed JSON).

    Checks: no cost keys anywhere (cost is no longer an input); no unknown keys (old keys get a hint
    to their replacement); required fields present; numbers finite; counts integer; probabilities in
    [0, 1] (chain probabilities in (0, 1], since they divide); rates and hours positive; w_k in (0, 1];
    unique ids for HB, HE, LS and TC; every HE names an existing HB; the selected HE exists and has a
    share > 0; per harm class the shares of the listed HEs sum to <= 1; benchmark harm class equals the
    harm class of the selected HE; the benchmark gives exactly one exposure (exposure_hours, or miles
    together with average_speed_mph); K >= 1; every TC names existing LS ids or "all"; human_share and
    fixed_share given for all LS or none, then each in (0, 1] and summing to 1; per-LS P_E, P_C, P_S
    and G_unknown in (0, 1]; P_S and severity_curve not both, and the curve gives P_S in (0, 1]; the
    allocation rule is known and its inputs are given; targeted_failures <= targeted_cases;
    N1 <= N_discovery; z_mode in {"fixed", "auto"}; alt_factor > 1.
    """
    if not isinstance(raw, Mapping):
        raise InputError("inputs: expected a JSON object")
    _reject_cost_keys(raw)
    _check_keys(raw, {"case_name", "function", "hazardous_behaviours", "hazardous_events",
                      "selected_hazardous_event", "benchmark", "criterion", "chain", "confidence", "fleet",
                      "driving", "budget", "unknown", "triggering_conditions", "logical_scenarios",
                      "simulator", "operation"}, "inputs")

    # Cl. 5 / 6.3: function, hazardous behaviours, hazardous events
    function = _str(raw, "function", "inputs")
    hbs: list[HazardousBehaviour] = []
    for i, d in enumerate(_list(raw, "hazardous_behaviours")):
        where = f"hazardous_behaviours[{i}]"
        _check_keys(d, {"id", "description"}, where)
        hbs.append(HazardousBehaviour(id=_id(d, where), description=_str(d, "description", where)))
    _unique([h.id for h in hbs], "hazardous_behaviours")
    hb_ids = [h.id for h in hbs]

    hes: list[HazardousEvent] = []
    for i, d in enumerate(_list(raw, "hazardous_events")):
        where = f"hazardous_events[{i}]"
        _check_keys(d, {"id", "hb_id", "operational_situation", "harm_class", "severity", "controllability",
                        "share_of_harm_class_budget"}, where)
        he = HazardousEvent(
            id=_id(d, where),
            hb_id=_id(d, where, "hb_id"),
            operational_situation=_str(d, "operational_situation", where),
            harm_class=_id(d, where, "harm_class"),
            share_of_harm_class_budget=_num(d, "share_of_harm_class_budget", where, lo=0, hi=1),
            severity=_str(d, "severity", where, optional=True),
            controllability=_str(d, "controllability", where, optional=True),
        )
        if he.hb_id not in hb_ids:
            raise InputError(f"{where}.hb_id = {he.hb_id!r}: no hazardous behaviour with this id; known: {hb_ids}")
        hes.append(he)
    _unique([e.id for e in hes], "hazardous_events")
    for c, total in harm_class_share_sums(hes).items():
        if total > 1 + 1e-9:
            parts = ", ".join(f"{e.id} {e.share_of_harm_class_budget:g}" for e in hes
                              if e.harm_class.strip().lower() == c.lower())
            raise InputError(
                f"hazardous_events: the shares of harm class {c!r} sum to {total:.4g} > 1 ({parts}); the "
                "hazardous events of one harm class cannot together use more than the whole harm-class budget")
    selected = _id(raw, "inputs", "selected_hazardous_event")
    sel = next((e for e in hes if e.id == selected), None)
    if sel is None:
        raise InputError(f"inputs.selected_hazardous_event = {selected!r}: no hazardous event with this id; "
                         f"known: {[e.id for e in hes]}")
    if sel.share_of_harm_class_budget <= 0:
        raise InputError(f"hazardous event {sel.id}: share_of_harm_class_budget = 0, so the selected event has "
                         "no budget; select another event or give it a share")

    # Cl. 6.5: benchmark and criterion
    b = _section(raw, "benchmark")
    _check_keys(b, {"harm_class", "events", "exposure_hours", "miles", "average_speed_mph", "source_note",
                    "synthetic"}, "benchmark")
    benchmark = Benchmark(
        harm_class=_id(b, "benchmark", "harm_class"),
        events=_num(b, "events", "benchmark", lo=0, lo_open=True),
        exposure_hours=_num(b, "exposure_hours", "benchmark", lo=0, lo_open=True, optional=True),
        miles=_num(b, "miles", "benchmark", lo=0, lo_open=True, optional=True),
        average_speed_mph=_num(b, "average_speed_mph", "benchmark", lo=0, lo_open=True, optional=True),
        source_note=_str(b, "source_note", "benchmark", optional=True),
        synthetic=_bool(b, "synthetic", "benchmark"),
    )
    by_miles = benchmark.miles is not None or benchmark.average_speed_mph is not None
    if (benchmark.exposure_hours is None) == (not by_miles):
        raise InputError("benchmark: give exactly one exposure: exposure_hours, or miles with average_speed_mph")
    if by_miles and (benchmark.miles is None or benchmark.average_speed_mph is None):
        raise InputError("benchmark: miles and average_speed_mph must be given together")
    if benchmark.harm_class.lower() != sel.harm_class.lower():
        raise InputError(f"benchmark.harm_class = {benchmark.harm_class!r}, but the selected hazardous event "
                         f"{sel.id} has harm class {sel.harm_class!r}; the human benchmark must be for the harm "
                         "class of the selected event")

    c = _section(raw, "criterion")
    _check_keys(c, {"margin_factor", "round_A_H_to"}, "criterion")
    criterion = Criterion(
        margin_factor=_num(c, "margin_factor", "criterion", lo=0, hi=1, lo_open=True),
        round_A_H_to=_num(c, "round_A_H_to", "criterion", lo=0, lo_open=True, optional=True),
    )

    # Cl. 6.4: harm chain
    ch = _section(raw, "chain")
    _check_keys(ch, {"P_E", "P_C", "P_S"}, "chain")
    chain = HarmChain(
        P_E=_num(ch, "P_E", "chain", lo=0, hi=1, lo_open=True),
        P_C=_num(ch, "P_C", "chain", lo=0, hi=1, lo_open=True),
        P_S=_num(ch, "P_S", "chain", lo=0, hi=1, lo_open=True),
    )

    cf = _section(raw, "confidence")
    _check_keys(cf, {"C", "m_bounds"}, "confidence")
    confidence = Confidence(
        C=_num(cf, "C", "confidence", lo=0, hi=1, lo_open=True, hi_open=True),
        m_bounds=_num(cf, "m_bounds", "confidence", integer=True, lo=1, optional=True),
    )

    fl = _section(raw, "fleet")
    _check_keys(fl, {"cars", "hours_per_day_per_car"}, "fleet")
    fleet = Fleet(
        cars=_num(fl, "cars", "fleet", lo=0, lo_open=True),
        hours_per_day_per_car=_num(fl, "hours_per_day_per_car", "fleet", lo=0, hi=24, lo_open=True),
    )

    dr = _section(raw, "driving")
    _check_keys(dr, {"pilot_hours", "confirmatory_hours", "discovery_hours"}, "driving")
    driving = Driving(
        pilot_hours=_num(dr, "pilot_hours", "driving", lo=0, lo_open=True),
        confirmatory_hours=_num(dr, "confirmatory_hours", "driving", lo=0, lo_open=True),
        discovery_hours=_num(dr, "discovery_hours", "driving", lo=0, lo_open=True),
    )

    bu = _section(raw, "budget")
    _check_keys(bu, {"reserve_fraction", "allocation_rule"}, "budget")
    rule = _str(bu, "allocation_rule", "budget", optional=True, default="equal_protection")
    if rule not in ALLOCATION_RULES:
        raise InputError(f"budget.allocation_rule = {rule!r}: must be one of {list(ALLOCATION_RULES)}")
    budget = Budget(reserve_fraction=_num(bu, "reserve_fraction", "budget", lo=0, hi=1, hi_open=True),
                    allocation_rule=rule)

    un = _section(raw, "unknown")
    _check_keys(un, {"p_new", "p_new_rationale", "N1", "N_discovery", "G_unknown"}, "unknown")
    unknown = Unknown(
        p_new=_num(un, "p_new", "unknown", lo=0, hi=1),
        N1=_num(un, "N1", "unknown", integer=True, lo=0),
        N_discovery=_num(un, "N_discovery", "unknown", integer=True, lo=0, optional=True),
        p_new_rationale=_str(un, "p_new_rationale", "unknown", optional=True),
        G_unknown=_num(un, "G_unknown", "unknown", lo=0, hi=1, lo_open=True, optional=True),
    )
    if unknown.N_discovery is not None and unknown.N1 > unknown.N_discovery:
        raise InputError("unknown.N1 must not exceed unknown.N_discovery")

    # Logical scenarios (derived from the selected hazardous event)
    scen: list[LogicalScenario] = []
    for i, d in enumerate(_list(raw, "logical_scenarios")):
        where = f"logical_scenarios[{i}]"
        _check_keys(d, {"id", "name", "description", "parameters", "N_pilot", "N_conf", "importance_factor",
                        "human_share", "human_cap_behaviour_rate", "targeted_cases", "targeted_case_design",
                        "targeted_failures", "failures", "runs_executed", "fixed_share", "P_E", "P_C", "P_S",
                        "severity_curve", "independent_units_note"}, where)
        curve = None
        if d.get("severity_curve") is not None:
            sc_d = d["severity_curve"]
            w_sc = f"{where}.severity_curve"
            _check_keys(sc_d, {"beta0", "beta1", "impact_speed", "source_note"}, w_sc)
            curve = SeverityCurve(beta0=_num(sc_d, "beta0", w_sc), beta1=_num(sc_d, "beta1", w_sc),
                                  impact_speed=_num(sc_d, "impact_speed", w_sc, lo=0),
                                  source_note=_str(sc_d, "source_note", w_sc, optional=True))
            if not 0 < curve.P_S <= 1:
                raise InputError(f"{w_sc}: the curve gives P_S = {curve.P_S!r}, which must be in (0, 1]")
        ls = LogicalScenario(
            id=_id(d, where),
            name=_str(d, "name", where),
            N_pilot=_num(d, "N_pilot", where, integer=True, lo=0),
            N_conf=_num(d, "N_conf", where, integer=True, lo=0),
            importance_factor=_num(d, "importance_factor", where, lo=0, hi=1, lo_open=True),
            targeted_cases=_num(d, "targeted_cases", where, integer=True, lo=0),
            targeted_failures=_num(d, "targeted_failures", where, integer=True, lo=0),
            failures=_num(d, "failures", where, integer=True, lo=0),
            human_share=_num(d, "human_share", where, lo=0, hi=1, lo_open=True, optional=True),
            human_cap_behaviour_rate=_num(d, "human_cap_behaviour_rate", where, lo=0, lo_open=True, optional=True),
            runs_executed=_num(d, "runs_executed", where, lo=0, lo_open=True, optional=True),
            fixed_share=_num(d, "fixed_share", where, lo=0, hi=1, lo_open=True, optional=True),
            P_E=_num(d, "P_E", where, lo=0, hi=1, lo_open=True, optional=True),
            P_C=_num(d, "P_C", where, lo=0, hi=1, lo_open=True, optional=True),
            P_S=_num(d, "P_S", where, lo=0, hi=1, lo_open=True, optional=True),
            severity_curve=curve,
            parameters=_str(d, "parameters", where, optional=True),
            targeted_case_design=_str(d, "targeted_case_design", where, optional=True),
            independent_units_note=_str(d, "independent_units_note", where, optional=True),
            description=_str(d, "description", where, optional=True),
        )
        if ls.P_S is not None and ls.severity_curve is not None:
            raise InputError(f"{where}: give P_S or severity_curve, not both")
        if ls.targeted_failures > ls.targeted_cases:
            raise InputError(f"{where}.targeted_failures = {ls.targeted_failures} exceeds targeted_cases = "
                             f"{ls.targeted_cases}")
        scen.append(ls)
    _unique([s.id for s in scen], "logical_scenarios")
    _shares_all_or_none(scen, "human_share")
    _shares_all_or_none(scen, "fixed_share")
    if rule == "proportional_to_human" and scen[0].human_share is None:
        raise InputError("budget.allocation_rule = 'proportional_to_human' needs logical_scenarios[].human_share")
    if rule == "fixed" and scen[0].fixed_share is None:
        raise InputError("budget.allocation_rule = 'fixed' needs logical_scenarios[].fixed_share")
    ls_ids = [s.id for s in scen]

    # Cl. 7.3: triggering conditions, regions inside the logical scenarios
    tcs: list[TriggeringCondition] = []
    for i, d in enumerate(_list(raw, "triggering_conditions", allow_empty=True)):
        where = f"triggering_conditions[{i}]"
        _check_keys(d, {"id", "description", "parameter_region", "logical_scenarios"}, where)
        ref = d.get("logical_scenarios")
        if ref == "all":
            refs, to_all = tuple(ls_ids), True
        elif isinstance(ref, list) and ref and all(isinstance(x, str) for x in ref):
            bad = [x for x in ref if x not in ls_ids]
            if bad:
                raise InputError(f"{where}.logical_scenarios: unknown logical scenario id(s) {bad}; known: {ls_ids}")
            if len(set(ref)) != len(ref):
                raise InputError(f"{where}.logical_scenarios: duplicated ids in {ref}")
            refs, to_all = tuple(x for x in ls_ids if x in ref), False
        else:
            raise InputError(f"{where}.logical_scenarios: expected \"all\" or a non-empty list of logical "
                             f"scenario ids, got {ref!r}")
        tcs.append(TriggeringCondition(id=_id(d, where), description=_str(d, "description", where),
                                       logical_scenarios=refs, applies_to_all=to_all,
                                       parameter_region=_str(d, "parameter_region", where, optional=True)))
    _unique([t.id for t in tcs], "triggering_conditions")

    s = _section(raw, "simulator")
    _check_keys(s, {"m_pairs", "mu_hat", "sigma_hat", "z_mode", "z_fixed", "z_auto_fraction"}, "simulator")
    z_mode = _str(s, "z_mode", "simulator", optional=True, default="fixed")
    if z_mode not in ("fixed", "auto"):
        raise InputError(f"simulator.z_mode: must be 'fixed' or 'auto', got {z_mode!r}")
    simulator = Simulator(
        m_pairs=_num(s, "m_pairs", "simulator", integer=True, lo=2),
        mu_hat=_num(s, "mu_hat", "simulator"),
        sigma_hat=_num(s, "sigma_hat", "simulator", lo=0, lo_open=True),
        z_mode=z_mode,
        z_fixed=_num(s, "z_fixed", "simulator", lo=0, lo_open=True, optional=(z_mode == "auto")) or 6.5,
        z_auto_fraction=_num(s, "z_auto_fraction", "simulator", lo=0, hi=1, lo_open=True, hi_open=True,
                             optional=True) or 0.01,
    )

    op = _section(raw, "operation")
    _check_keys(op, {"fleet_hours_per_year", "hb_detection_rule", "alt_factor"}, "operation")
    operation = Operation(
        fleet_hours_per_year=_num(op, "fleet_hours_per_year", "operation", lo=0, lo_open=True),
        hb_detection_rule=_str(op, "hb_detection_rule", "operation", optional=True),
        alt_factor=_num(op, "alt_factor", "operation", lo=1, lo_open=True, optional=True) or 2.0,
    )

    return WorkbookInputs(
        case_name=_str(raw, "case_name", "inputs"), function=function,
        hazardous_behaviours=tuple(hbs), hazardous_events=tuple(hes), selected_hazardous_event=selected,
        benchmark=benchmark, criterion=criterion, chain=chain, confidence=confidence, fleet=fleet,
        driving=driving, budget=budget, unknown=unknown, triggering_conditions=tuple(tcs),
        logical_scenarios=tuple(scen), simulator=simulator, operation=operation,
    )


def load_inputs(path: str | Path) -> WorkbookInputs:
    """Read a JSON input file and validate it (see `inputs_from_dict`)."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return inputs_from_dict(raw)


def write_mock_inputs(path: str | Path) -> Path:
    """Write the mock robotaxi inputs as JSON to `path`; use the file as a template for real data."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(MOCK_INPUTS_ROBOTAXI, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return p

# %% [markdown]
# ## Statistical building blocks
#
# Almost every bound in the chain is one of two expressions. The Poisson upper bound on a rate from
# N events in tau hours is chi2_{C_b}(2N + 2) / (2 tau) (Garwood 1936). The same quantile, halved, is
# the j-failure factor F(j) = chi2_{C_b}(2j + 2) / 2, which for j = 0 equals L = ln(1/(1 - C_b)), the
# "rule of three" generalised to confidence C_b. Both are one-sided upper bounds, so each is wrong with
# probability at most 1 - C_b. The operation phase (Cl. 13) also needs the matching one-sided lower
# bound chi2_{1-C}(2k) / (2T), which shows that a rate is above a limit, and a Poisson likelihood-ratio
# e-process, which does the same while allowing the data to be looked at continuously. The logistic
# injury-risk curve is an optional way to set P_S per logical scenario (Cl. 6.4).

# %%
def poisson_upper_rate(N: int | np.ndarray, tau: float, conf: float) -> float | np.ndarray:
    """One-sided upper confidence bound on a Poisson rate.

    Computes   lambda^U = chi2_{conf}(2N + 2) / (2 tau)
    Parameters N: observed events [count]; tau: observation time [h]; conf: one-sided confidence [-].
    Returns    upper bound on the rate [1/h].
    Assumption Events form a homogeneous Poisson process over the observation time.
    Source     Garwood 1936, Biometrika 28:437-442, Sec. 4, p. 441 [checked]; stated explicitly in Porter 2025, arXiv:2509.02852, Sec. 5 Eq. 34 and Sec. 6.1 Eq. 38 [checked].
    """
    return chi2.ppf(conf, 2 * np.asarray(N) + 2) / (2.0 * tau)


def poisson_lower_rate(k: int, tau: float, conf: float) -> float:
    """One-sided lower confidence bound on a Poisson rate.

    Computes   lambda_L = chi2_{1 - conf}(2k) / (2 tau) for k >= 1;  lambda_L = 0 for k = 0.
    Parameters k: observed events [count]; tau: observation time [h]; conf: one-sided confidence [-].
    Returns    lower bound on the rate [1/h]. lambda_L > R holds exactly when P(X >= k | R tau) < 1 - conf,
               i.e. when k events would be unlikely if the true rate were R.
    Assumption Events form a homogeneous Poisson process over the observation time.
    Source     Garwood 1936, Biometrika 28:437-442, Sec. 4, p. 441 [checked]; stated explicitly in Porter 2025, arXiv:2509.02852, Sec. 5 Eq. 34 and Sec. 6.1 Eq. 38 [checked].
    """
    if k <= 0:
        return 0.0
    return float(chi2.ppf(1.0 - conf, 2 * int(k)) / (2.0 * tau))


def poisson_e_value(k: int, tau: float, rate0: float, rate1: float) -> float:
    """Poisson likelihood-ratio e-process of a count, rate1 against rate0.

    Computes   E(tau) = (rate1 / rate0)^k * exp(-(rate1 - rate0) * tau)
    Parameters k: events observed so far [count]; tau: observation time so far [h]; rate0: null rate [1/h];
               rate1: alternative rate [1/h], > rate0.
    Returns    the e-value [-]. Under any true rate <= rate0, E is a nonnegative supermartingale with
               E(0) = 1, so by Ville's inequality P(E ever reaches 1/alpha) <= alpha, however often it is
               looked at.
    Sources    Ramdas, Gruenwald, Vovk & Shafer 2023, Statistical Science 38(4), arXiv:2210.01948 [checked]
               (at abstract level); Wald 1945, sequential probability ratio test [location not checked].
    """
    return float((rate1 / rate0) ** int(k) * math.exp(-(rate1 - rate0) * tau))


def logistic_severity(beta0: float, beta1: float, impact_speed: float) -> float:
    """Injury probability from a logistic injury-risk curve.

    Computes   P(S | delta v) = 1 / (1 + exp(-(beta0 + beta1 * delta v)))
    Parameters beta0 [-]; beta1 [1/(speed unit)]; impact_speed delta v [speed unit of the fit].
    Returns    P(S | delta v) [-].
    Assumption The curve was fitted for the harm class and road-user group of the hazardous event, and one
               representative impact speed stands for the logical scenario.
    Source     Wang 2022, NHTSA DOT HS 813 219, Table 1-1 [location not checked] (occupant curves by delta-V).
    """
    return 1.0 / (1.0 + math.exp(-(beta0 + beta1 * impact_speed)))


def failure_factor(j: int | np.ndarray, conf: float) -> float | np.ndarray:
    """j-failure factor F(j) = chi2_{conf}(2j + 2) / 2; F(0) = ln(1/(1 - conf)) = L.

    F(j)/n is the Poisson upper bound on a per-trial failure probability after j failures in n
    trials. It is at least as large as the exact binomial (Clopper-Pearson) bound, so it is
    conservative; the self-test checks this numerically.
    Source  ISO 21448:2022 C.3, Formula (C.7), p. 137 for j = 0 [checked]; Garwood 1936 for
            j > 0 [location not checked].
    """
    return chi2.ppf(conf, 2 * np.asarray(j) + 2) / 2.0

# %% [markdown]
# ## Cl. 5 / 6.3 · Function and hazard identification (record)
#
# The chain starts from the hazard analysis. Clause 5 specifies the intended functionality and the
# ODD; 6.3 identifies the hazardous behaviours at vehicle level (no situation named) and combines each
# with operational situations into hazardous events, each with a harm class and severity and
# controllability ratings. ISO 21448 6.5 sets acceptance criteria per hazardous behaviour, and several
# hazardous events (of several behaviours) lead to the same harm class, so each hazardous event receives
# a share of its harm-class budget. This step records the tables and checks that, per harm class, the
# listed shares do not exceed 1. A sum below 1 is a warning, not an error: the rest of the budget belongs
# to hazardous events of other behaviours that are analysed elsewhere. Assumption to defend: across all
# files, the shares of one harm class add up to at most 1.

# %%
@dataclass(frozen=True)
class HazardIdentificationResult:
    selected: HazardousEvent
    selected_hb: HazardousBehaviour
    share_sums: dict[str, float]   # harm class -> sum of shares of the listed hazardous events [-]
    he_count: dict[str, int]       # HB id -> number of listed hazardous events
    hb_without_he: list[str]       # HB ids with no hazardous event in this file
    warnings: list[str]


def cl6_3_hazard_identification(inputs: WorkbookInputs) -> HazardIdentificationResult:
    """Cl. 5 / 6.3: record the function, the hazardous behaviours and the hazardous events.

    Computes   No new number; records and checks the hazard analysis the chain starts from.
    Formula    S_c = sum of share_of_harm_class_budget over the listed hazardous events of harm class c.
               Required S_c <= 1 (checked in the loader); S_c < 1 gives a warning.
    Parameters inputs.function (text: intended functionality and ODD); inputs.hazardous_behaviours
               (id, description); inputs.hazardous_events (id, hb_id, operational situation, harm class,
               severity and controllability text, share of the harm-class budget [-]);
               inputs.selected_hazardous_event (id).
    Returns    HazardIdentificationResult: selected HE and its HB, S_c per harm class, HEs per HB, HBs
               without HE in this file, warnings.
    Assumptions Hazardous behaviours are described at vehicle level without a situation; each hazardous
               event is one behaviour in one operational situation; hazardous events of other behaviours
               leading to the same harm class (analysed elsewhere) together use at most 1 - S_c.
    Sources    ISO 21448:2022 5.2 (specification of the functionality) [location not checked];
               6.3 (hazard identification) [location not checked]; acceptance criteria per hazardous
               behaviour: 6.5, pp. 30-31 [checked] and C.2.1, p. 126 [checked]; budgets must add up:
               Warg et al. 2020, Quantitative Risk Norm, Sec. III-B [location not checked].
    """
    sums = harm_class_share_sums(inputs.hazardous_events)
    count = {h.id: sum(1 for e in inputs.hazardous_events if e.hb_id == h.id) for h in inputs.hazardous_behaviours}
    without = [h for h, n in count.items() if n == 0]
    warnings: list[str] = []
    partial = {c: total for c, total in sums.items() if total < 1 - 1e-9}
    if partial:
        warnings.append(
            "WARNING: the listed hazardous events use only part of these harm-class budgets: "
            + ", ".join(f"{c} {t:.2f} (not assigned: {1 - t:.2f})" for c, t in partial.items())
            + ". This is expected when hazardous events of other hazardous behaviours leading to the same harm are "
              "analysed elsewhere; together they must not use more than the part not assigned here.")
    return HazardIdentificationResult(inputs.selected_he, inputs.selected_hb, sums, count, without, warnings)

# %% [markdown]
# ## Cl. 6.4 · Risk evaluation: the harm chain of the selected hazardous event
#
# Whether one occurrence of the behaviour turns into harm depends on the world: a pedestrian must be in
# the path (exposure), must fail to avoid the collision (controllability) and the collision must injure
# (severity). In the hazard analysis these are ratings (S2-S3, controllability "low"); for the
# quantitative chain they become three probabilities. Assumption to defend: the probabilities are
# consistent with the ratings, and the product treats the links as independent of how the behaviour
# happened (ISO 21448 C.2.1 Note 5); strictly each factor is conditional on everything before it.
#
# Option (full conditioning, Putze et al. 2023, Sec. IV-B(b)): a logical scenario may override P_E, P_C
# or P_S, e.g. a robotaxi turning in at 10-30 km/h injures less often than one approaching at 50 km/h.
# P_S may also come from a logistic injury-risk curve at a representative impact speed (Wang 2022). The
# curve must fit the harm class: Wang 2022 gives occupant curves by delta-V, so a pedestrian harm class
# needs a pedestrian impact-speed curve. With overrides, each logical scenario has its own G_k =
# P_E,k P_C,k P_S,k, and the budget (9.3 (d)) and the release claim (Cl. 12) are kept in harm units.
# Unknown scenarios use the common chain unless G_unknown is given. Default: no overrides, G_k = G.

# %%
@dataclass(frozen=True)
class RiskEvaluationResult:
    P_E: float              # P(E | HB) of the hazardous event [-]
    P_C: float              # P(not C | E) [-]
    P_S: float              # P(S | not C) [-]
    P_chain: float          # G = P_E * P_C * P_S: one HB occurrence in this HE causes the harm [-]
    P_E_k: np.ndarray       # per LS [-]
    P_C_k: np.ndarray       # per LS [-]
    P_S_k: np.ndarray       # per LS [-]
    P_S_from: list[str]     # per LS: "common", "input" or "curve"
    G_k: np.ndarray         # per LS harm chain [-]
    G_unk: float            # chain for unknown scenarios [-]
    per_ls: bool            # True if any LS chain differs from the common chain


def cl6_4_risk_evaluation(chain: HarmChain, scenarios: Sequence[LogicalScenario] = (),
                          G_unknown: Optional[float] = None) -> RiskEvaluationResult:
    """Cl. 6.4: the harm chain of the selected hazardous event, and optionally of each logical scenario.

    Computes   G = P_chain, the probability that one occurrence of the HB in this hazardous event leads to the
               harm of its harm class; G_k per logical scenario; G_unk for unknown scenarios.
    Formula    G   = P(E | HB) * P(not C | E) * P(S | not C)
               G_k = P_E,k * P_C,k * P_S,k, each factor defaulting to the common one;
               P_S,k from a curve: 1 / (1 + exp(-(beta0 + beta1 * impact_speed)))
               G_unk = G_unknown if given, else G
    Parameters chain.P_E, chain.P_C, chain.P_S [-], each in (0, 1]; scenarios (optional P_E, P_C, P_S,
               severity_curve); G_unknown [-] or None.
    Returns    RiskEvaluationResult.
    Assumptions The severity and controllability ratings of the HARA (classes) become probabilities here
               and must be consistent with them; each factor is conditioned on the whole history (HB, E,
               not C). Without overrides one chain holds for all logical scenarios of the event. Unknown
               scenarios: the common chain by default; the largest G_k is the conservative choice.
    Sources    ISO 21448:2022 6.4 (risk evaluation) [location not checked]; C.2.1, Formulas (C.1)-(C.2)
               and the meaning of P_C|E and P_S|C, pp. 126-127 [checked]; C.2.1 Notes 4-5, p. 127
               (consistency with the ISO 26262 HARA; independence simplification) [checked];
               full conditioning: Putze et al. 2023, arXiv:2304.10170, Sec. IV-B(b) [checked]; injury-risk
               curves: Wang 2022, NHTSA DOT HS 813 219, Table 1-1 [location not checked].
    """
    G = chain.P_E * chain.P_C * chain.P_S
    pe = np.array([chain.P_E if s.P_E is None else s.P_E for s in scenarios], float)
    pc = np.array([chain.P_C if s.P_C is None else s.P_C for s in scenarios], float)
    ps_from = ["curve" if s.severity_curve is not None else ("input" if s.P_S is not None else "common")
               for s in scenarios]
    ps = np.array([s.severity_curve.P_S if s.severity_curve is not None else (chain.P_S if s.P_S is None else s.P_S)
                   for s in scenarios], float)
    G_k = pe * pc * ps
    per_ls = bool(np.any(G_k != G))
    G_unk = G if G_unknown is None else float(G_unknown)
    return RiskEvaluationResult(chain.P_E, chain.P_C, chain.P_S, G, pe, pc, ps, ps_from, G_k, G_unk, per_ls)

# %% [markdown]
# ## Cl. 6.5 · Acceptance criterion
#
# Positive risk balance: the system should cause this harm less often than human drivers in the same
# ODD, by a margin factor. The human benchmark is a plain input: harm events of the harm class of the
# selected event over an exposure in hours, h = events / exposure hours, the unit of all exposure and
# fleet numbers (miles with an average speed are accepted instead; the speed then scales h one to one
# and needs its own source). The harm-class budget margin x h is shared among the hazardous events of
# that class; the selected event receives its share from the hazard analysis. Assumptions to defend:
# the benchmark matches the ODD (road types, speeds, time of day; a Berlin ODD needs a matched German
# or EU source such as GIDAS or national statistics); the margin is argued, not picked. The mock
# benchmark is a synthetic placeholder. Rounding A_H is optional (off in the mock); rounding down is
# conservative, and the report flags any rounding that makes A_H larger. As a plausibility check the
# report compares the harm-class budget with the vehicle-level targets proposed by Kroeger (2025).

# %%
@dataclass(frozen=True)
class CriterionResult:
    h_per_mile: Optional[float]  # human harm events per mile [1/mi], only if the benchmark is in miles
    h: float                     # human harm events per hour [1/h]
    share: float              # share of the harm-class budget for the selected HE [-]
    margin: float             # margin factor [-]
    A_H_raw: float            # share * margin * h before rounding [1/h]
    A_H: float                # acceptable harm rate used downstream [1/h]
    rounding_increased: bool  # True if rounding made A_H larger (less strict)


def cl6_5_acceptance_criterion(bench: Benchmark, crit: Criterion, share: float) -> CriterionResult:
    """Cl. 6.5: human benchmark rate and acceptable harm rate attributed to the selected hazardous event.

    Computes   h, the rate at which human drivers cause this harm class in the ODD per hour, and A_H.
    Formula    h = events / exposure_hours   (or events / miles * v_avg if the benchmark is in miles)
               A_H = share_of_harm_class_budget * margin_factor * h;
               optionally A_H := round(A_H / q) * q with q = round_A_H_to.
    Parameters bench.events [count]; bench.exposure_hours [h] (or bench.miles [mi] and
               bench.average_speed_mph [mi/h]); crit.margin_factor [-]; crit.round_A_H_to [1/h] or None;
               share [-] from the selected HE.
    Returns    CriterionResult(h_per_mile [1/mi] or None, h [1/h], share, margin, A_H_raw [1/h], A_H [1/h],
               rounding_increased).
    Assumptions Benchmark matched to the ODD and to the harm class; shares of all HEs of this harm class sum
               to <= 1; the margin is justified. In the mock the benchmark is synthetic.
    Sources    Acceptance criterion: ISO 21448:2022 3.1, p. 2 [checked]; acceptance criteria per hazardous
               behaviour with positive risk balance among the rationales: 6.5, pp. 30-31 [checked];
               A_H derived with a safety margin: C.2.1, p. 126 [checked]. Benchmark: input (synthetic in
               the mock). Plausibility: Kroeger 2025, Next Research 2:100238 [location not checked].
    Raises     InputError if rounding gives A_H = 0.
    """
    h = bench.events / bench.hours
    h_per_mile = None if bench.miles is None else bench.events / bench.miles
    raw = share * crit.margin_factor * h
    if crit.round_A_H_to is None:
        return CriterionResult(h_per_mile, h, share, crit.margin_factor, raw, raw, False)
    q = crit.round_A_H_to
    a_h = round(raw / q) * q
    if a_h <= 0:
        raise InputError(f"criterion.round_A_H_to = {q} rounds A_H = {raw:.4g} to zero; use a smaller value")
    return CriterionResult(h_per_mile, h, share, crit.margin_factor, raw, a_h, a_h > raw * (1 + 1e-12))

# %% [markdown]
# ## Annex C.2.1 · Tolerable behaviour rate
#
# The software only controls whether the behaviour happens; the harm chain of Cl. 6.4 decides how often
# it turns into harm. Dividing A_H by the chain probability gives R_HB, the rate at which the behaviour
# itself may occur in this hazardous event. R_HB is the quantity all validation targets are derived from.

# %%
@dataclass(frozen=True)
class ToleranceResult:
    P_chain: float  # P_E * P_C * P_S [-]
    R_HB: float     # tolerable rate of the hazardous behaviour in this HE [1/h]


def annexC2_1_tolerable_rate(A_H: float, P_chain: float) -> ToleranceResult:
    """Annex C.2.1: tolerable rate of the hazardous behaviour.

    Computes   R_HB, the rate at which the HB may occur so that its harm in this HE stays below A_H.
    Formula    R_HB = A_H / (P(E|HB) * P(not C|E) * P(S|not C)) = A_H / P_chain
    Parameters A_H [1/h] (Cl. 6.5); P_chain [-] (Cl. 6.4).
    Returns    ToleranceResult(P_chain [-], R_HB [1/h]).
    Assumptions As Cl. 6.4: each factor conditioned on the whole history; one chain for the whole HE.
    Sources    ISO 21448:2022 C.2.1, Formulas (C.1)-(C.2), pp. 126-127 [checked];
               conditioning caveat: Putze et al. 2023, arXiv:2304.10170, Sec. IV-B(b) [checked].
    """
    return ToleranceResult(P_chain=P_chain, R_HB=A_H / P_chain)

# %% [markdown]
# ## Annex C.3 · Naive validation target (for scale)
#
# The simplest validation target is to drive until the behaviour has not been seen for long enough.
# With zero events in tau hours, the rate is below R_HB at confidence C if tau = ln(1/(1-C)) / R_HB.
# Converted to fleet time, this shows why validation by driving alone is impractical: one event resets
# the clock and every software release needs new evidence. Assumption: events form a homogeneous
# Poisson process on one frozen release. The result is for scale only; Clause 12 does not use it.

# %%
@dataclass(frozen=True)
class NaiveTargetResult:
    L_single: float          # ln(1/(1-C)) [-]
    tau_h: float             # zero-event driving hours [h]
    fleet_hours_per_day: float
    fleet_days: float        # [days]
    fleet_years: float       # [years of days_per_year days]
    pilot_fleet_days: float
    conf_fleet_days: float


def annexC3_naive_target(R_HB: float, C: float, fleet: Fleet, driving: Driving,
                         days_per_year: float = 365.25) -> NaiveTargetResult:
    """Annex C.3: zero-failure driving target for the behaviour as a whole.

    Computes   Hours of driving with zero HB needed to show rate <= R_HB at confidence C.
    Formula    tau_naive = ln(1/(1 - C)) / R_HB;  days = tau_naive / (cars * hours_per_day_per_car);
               years = days / days_per_year.
    Parameters R_HB [1/h]; C [-]; fleet.cars [count]; fleet.hours_per_day_per_car [h/day];
               days_per_year [day/yr] (default 365.25).
    Returns    NaiveTargetResult with tau [h], fleet days and years; for comparison also the planned
               pilot and confirmatory driving in fleet days.
    Assumptions Homogeneous Poisson process, one release, zero events observed.
    Sources    ISO 21448:2022 C.3, Formula (C.7), p. 137 [checked], taken from Littlewood & Wright
               1997, IEEE TSE 23(11):673-683 [checked]; Kalra & Paddock 2016, RAND RR-1478, Eq. 2 [checked].
    """
    L1 = math.log(1.0 / (1.0 - C))
    tau = L1 / R_HB
    per_day = fleet.cars * fleet.hours_per_day_per_car
    days = tau / per_day
    return NaiveTargetResult(L1, tau, per_day, days, days / days_per_year,
                             driving.pilot_hours / per_day, driving.confirmatory_hours / per_day)

# %% [markdown]
# ## Cl. 7.3 · Logical scenarios and triggering conditions (record)
#
# The operational situation of the selected hazardous event is the functional scenario. Logical
# scenarios describe it with parameter ranges (Menzel et al. 2018); concrete scenarios are single
# parameter values. The logical scenarios must be mutually exclusive and collectively exhaustive (MECE)
# for the encounters of the hazardous event: each encounter belongs to exactly one of them. Triggering
# conditions (7.3) are regions of the parameter space inside one or more logical scenarios, e.g. "low
# light" inside all three, "occlusion by a stationary vehicle" defining LS-2. They are used for targeted
# cases (Clause 10) and to bias the importance sampling of the simulation runs (Annex C.5); they are not
# budget holders. 7.4 (acceptability of the system's response to the triggering conditions) is estimated
# by the Clause 10 targeted cases and, statistically, by the failure bounds of Clause 11.

# %%
@dataclass(frozen=True)
class TriggeringConditionResult:
    matrix: np.ndarray            # [number of TC, K], True where TC i lies in LS k
    tcs_per_ls: list[list[str]]   # TC ids per LS
    ls_without_tc: list[str]      # LS ids that contain no triggering condition


def cl7_3_triggering_conditions(inputs: WorkbookInputs) -> TriggeringConditionResult:
    """Cl. 7.3: record the triggering conditions as regions inside the logical scenarios.

    Computes   The TC x LS incidence matrix and the TCs of each LS.
    Formula    M[i, k] = True if triggering condition i is a region inside logical scenario k.
    Parameters inputs.triggering_conditions (id, description, parameter region, LS ids or "all");
               inputs.logical_scenarios (id, name, parameter ranges).
    Returns    TriggeringConditionResult.
    Assumptions The logical scenarios are MECE for the encounters of the hazardous event; the triggering
               conditions known so far are listed (unknown ones are the subject of Clause 11).
    Sources    ISO 21448:2022 7.3 (analysis of potential functional insufficiencies and triggering
               conditions) [location not checked]; 7.4 (acceptability of the response) [location not
               checked]; functional, logical and concrete scenarios: Menzel, Bagschik & Maurer 2018, IEEE IV,
               arXiv:1801.08598 [location not checked]; parameter distributions and importance sampling:
               ISO 21448:2022 C.5, pp. 146-151 [checked].
    """
    ids = inputs.ls_ids
    tcs = inputs.triggering_conditions
    M = np.zeros((len(tcs), len(ids)), dtype=bool)
    for i, t in enumerate(tcs):
        for lid in t.logical_scenarios:
            M[i, ids.index(lid)] = True
    per_ls = [[tcs[i].id for i in range(len(tcs)) if M[i, k]] for k in range(len(ids))]
    without = [ids[k] for k in range(len(ids)) if not per_ls[k]]
    return TriggeringConditionResult(M, per_ls, without)

# %% [markdown]
# ## Cl. 9.3 (a) · Joint confidence for m simultaneous bounds
#
# Clause 9 defines the verification and validation strategy, including the validation targets. The
# release claim of Clause 12 adds up m upper bounds: by default K exposure bounds, K failure bounds, one
# bound for unknown scenarios and one for the simulator spread (m = 2K + 2). Each bound can be wrong with
# a small probability; by the Bonferroni (union) bound, all m hold together with probability at least C if
# each is computed at C_b = 1 - (1 - C)/m. This needs no independence between the bounds. The price is
# mild: L = ln(1/(1 - C_b)) grows only with ln m. Assumption to defend: m counts every bound that enters
# the final claim, fixed before the data are seen.

# %%
@dataclass(frozen=True)
class JointConfidenceResult:
    m: int                                        # number of bounds used [-]
    m_default: int                                # 2K + 2
    C_b: float                                    # per-bound confidence [-]
    L: float                                      # ln(1/(1 - C_b)) [-]
    L_table: list[tuple[int, float, float]]       # (m, C_b, L) for several m
    F_table: list[tuple[int, float]]              # (j, F(j)) at C_b


def cl9_3a_joint_confidence(C: float, K: int, m_override: Optional[int] = None,
                            m_grid: Sequence[int] = (1, 2, 4, 6, 8, 10, 16, 20, 32, 64),
                            j_grid: Sequence[int] = (0, 1, 2, 3, 5)) -> JointConfidenceResult:
    """Cl. 9.3 (a): per-bound confidence and zero-failure factor.

    Computes   m, C_b and L; a table of L for several m; a table of the j-failure factor F(j).
    Formula    m = 2K + 2 (or override);  C_b = 1 - (1 - C)/m;  L = ln(1/(1 - C_b));
               F(j) = chi2_{C_b}(2j + 2) / 2.
    Parameters C [-]: joint confidence; K [-]: number of logical scenarios; m_override [-] or None.
    Returns    JointConfidenceResult.
    Assumptions m includes every bound in the final sum. An override smaller than 2K + 2 breaks the
               joint-confidence claim unless some bounds are not used; the report warns.
    Sources    V&V strategy includes validation targets: ISO 21448:2022 9.1 a)-b), p. 42 [checked];
               9.3 (specification of integration and testing) [location not checked]. Joint confidence via
               Bonferroni: ISO 21448:2022 C.6.3.2 Example 1, p. 156 [checked]; Dunn 1961, JASA 56:52-64
               [location not checked]. L as zero-failure factor: ISO 21448:2022 C.3, Formula (C.7),
               p. 137 [checked].
    """
    m_default = 2 * K + 2
    m = m_default if m_override is None else int(m_override)
    C_b = 1.0 - (1.0 - C) / m
    L = math.log(1.0 / (1.0 - C_b))
    grid = sorted(set(m_grid) | {m})
    L_table = [(mm, 1.0 - (1.0 - C) / mm, math.log(mm / (1.0 - C))) for mm in grid]
    F_table = [(j, float(failure_factor(j, C_b))) for j in j_grid]
    return JointConfidenceResult(m, m_default, C_b, L, L_table, F_table)

# %% [markdown]
# ## Cl. 9.3 (b) · Exposure per logical scenario (pilot driving)
#
# The behaviour rate of the hazardous event is a sum over logical scenarios, R = sum_k lambda_k p_k: how
# often the vehicle meets LS k per hour (a property of the world) times the probability that it fails in
# one such encounter (a property of the system). Encounters are common even when failures are rare, so
# lambda_k is measured with modest driving and p_k is tested in simulation. Here lambda_k^U is the Poisson
# upper bound from N_k encounters in the pilot hours, used only for planning. Assumption to defend: the
# logical scenarios are MECE, the pilot routes represent the ODD mix, and the auto-labelling finds the
# encounters it should.

# %%
@dataclass(frozen=True)
class ExposureResult:
    N: np.ndarray         # encounters counted [count]
    tau: float            # driving hours [h]
    point: np.ndarray     # N / tau [1/h]
    lambda_U: np.ndarray  # upper bound at C_b [1/h]


def cl9_3b_exposure_bounds(N: Sequence[int], tau: float, C_b: float) -> ExposureResult:
    """Cl. 9.3 (b): upper bounds on the encounter rate of each logical scenario.

    Computes   lambda_k^U for k = 1..K from counted encounters.
    Formula    lambda_k^U = chi2_{C_b}(2 N_k + 2) / (2 tau)
    Parameters N [count]: encounters per LS; tau [h]: driving hours; C_b [-]: per-bound confidence.
    Returns    ExposureResult(N, tau, point estimate N/tau [1/h], lambda_U [1/h]).
    Assumptions Encounters of each LS form a homogeneous Poisson process; MECE logical scenarios; driving
               representative of the ODD. Pilot bounds are for planning only and are not among the m
               bounds of the release claim; computing them at C_b keeps the plan consistent with Cl. 11.
    Sources    Garwood 1936, Biometrika 28:437-442, Sec. 4, p. 441 [checked]; stated explicitly in Porter 2025, arXiv:2509.02852, Sec. 5 Eq. 34 and Sec. 6.1 Eq. 38 [checked]; per-bound confidence:
               ISO 21448:2022 C.6.3.2 Example 1, p. 156 [checked].
    """
    N_arr = np.asarray(N, dtype=int)
    return ExposureResult(N_arr, tau, N_arr / tau, np.asarray(poisson_upper_rate(N_arr, tau, C_b), float))

# %% [markdown]
# ## Cl. 9.3 (c) · Reserve for unknown scenarios, and the budget for the logical scenarios
#
# Scenarios missing from the list of logical scenarios can still cause the behaviour (the unknown
# hazardous scenarios of ISO 21448 4.2.2, evaluated in Clause 11), so part of R_HB is kept as a reserve
# before the rest is split. The budgets must add up: sum_k b_k + b_unk = R_HB. The 10 % reserve is a
# choice; Clause 11 checks it against the discovery evidence. Assumption to defend: the reserve is large
# enough for what the discovery data allow.

# %%
@dataclass(frozen=True)
class ReserveResult:
    b_unk: float         # reserve for unknown scenarios, behaviour units [1/h]
    B: float             # budget for the K logical scenarios, behaviour units [1/h]
    reserve_harm: float  # reserve in harm units, f * A_H [1/h]
    A_prime: float       # harm budget for the K logical scenarios, (1 - f) * A_H [1/h]


def cl9_3c_reserve_for_unknown(R_HB: float, A_H: float, reserve_fraction: float) -> ReserveResult:
    """Cl. 9.3 (c): reserve for unknown scenarios (Cl. 11) and budget for the logical scenarios.

    Computes   b_unk and B in behaviour units, and the same split in harm units.
    Formula    b_unk = f * R_HB;  B = R_HB - b_unk;  reserve_harm = f * A_H;  A' = (1 - f) * A_H (= G * B)
    Parameters R_HB [1/h]; A_H [1/h]; reserve_fraction f [-] in [0, 1).
    Returns    ReserveResult(b_unk, B, reserve_harm, A_prime) [1/h].
    Assumptions The reserve covers unknown scenarios; budgets add up to R_HB.
    Sources    Known/unknown scenario areas: ISO 21448:2022 4.2.2, pp. 12-14 [checked]; residual risk of
               unknown scenarios with sufficient confidence: 11.1, p. 50 [checked]; budgets must add up:
               Warg et al. 2020, Quantitative Risk Norm, Sec. III-B [location not checked]; the 10 % value
               is a choice [derived in this course].
    """
    b_unk = reserve_fraction * R_HB
    return ReserveResult(b_unk=b_unk, B=R_HB - b_unk, reserve_harm=reserve_fraction * A_H,
                         A_prime=(1.0 - reserve_fraction) * A_H)

# %% [markdown]
# ## Cl. 9.3 (d) · Budget per logical scenario by a safety rule
#
# The harm budget A' = (1 - f) A_H is split into harm budgets a_k, one per logical scenario, and each is
# turned into a behaviour budget b_k = a_k / G_k. With one common chain G this is simply a split of B:
# b_k = B a_k / A'. The split decides how much risk the road users in each logical scenario carry, so it
# is set by a safety rule, never by test cost:
#
# * **equal_protection** (default): a_k = A' lambda_k^U / sum_j lambda_j^U. Then the harm probability per
#   encounter p_k* G_k = A' / sum_j lambda_j^U is the same in every logical scenario: every pedestrian at
#   the crossing is protected equally, whether in clear view, behind a bus or in front of a turning
#   robotaxi. Rare scenarios do not get a looser target because they are rare. With one common chain this
#   is b_k = B lambda_k^U / sum_j lambda_j^U, i.e. the same allowed failure probability p_k* = B / sum_j
#   lambda_j^U everywhere. With per-LS chains (full conditioning, Putze et al. 2023, Sec. IV-B(b)),
#   p_k* = A' / (G_k sum_j lambda_j^U): a scenario that injures less often per behaviour may fail more often
#   per encounter, by exactly that factor.
# * **proportional_to_human**: a_k = A' s_k with s_k the human share of this harm in LS k. Then the system
#   is better than human drivers by the same factor in every logical scenario.
# * **equal_split**: a_k = A' / K, for comparison only. It gives unequal protection per encounter: a rare
#   logical scenario receives the same budget as a common one, so its allowed failure probability per
#   encounter is much larger.
# * **fixed**: user-given harm shares (e.g. frozen from an earlier plan), summing to 1.
#
# After any rule comes the human cap: no logical scenario may be worse than human drivers in that
# scenario, b_k <= h_k (in harm units a_k <= h_k G_k). A budget above its cap is set to the cap and the
# rest is re-allocated to the uncapped logical scenarios in proportion to the rule's weights, until
# nothing changes. The report always compares all applicable rules, with the protection ratio, the
# largest over the smallest harm probability per encounter p_k* G_k (1 = equal protection).
#
# Budgets are frozen (Werling et al. 2025, Sec. 3.3, Remark 3.7): the shares are fixed before the
# confirmatory campaign and may only move between campaigns, with fresh evidence. Moving them after the
# confirmatory data are in would let the data choose the budget they are judged against.

# %%
@dataclass(frozen=True)
class TargetsResult:
    p_star: np.ndarray              # allowed failure probability per encounter [-]
    one_in: np.ndarray              # 1 / p_star [encounters]
    harm_per_encounter: np.ndarray  # p_star * G_k: allowed harm probability per encounter [-]
    n: np.ndarray                   # zero-failure simulation runs, exact [runs]
    n_ceil: np.ndarray              # rounded up [runs]
    n_total: float                  # [runs]
    protection_ratio: float         # max / min of p_k* G_k [-]; 1 = every LS protected equally


@dataclass(frozen=True)
class RuleOutcome:
    rule: str
    weights: np.ndarray      # v_k of the rule before the cap step
    harm: np.ndarray         # harm budgets a_k after the cap step [1/h]
    b: np.ndarray            # behaviour budgets b_k = a_k / G_k [1/h]
    share: np.ndarray        # a_k / A' [-] (= b_k / B with one common chain)
    clamped: np.ndarray      # True where the human cap binds
    passes: int              # clamp-and-redistribute passes
    unallocated_harm: float  # A' - sum(a), > 0 only if every LS is capped [1/h]
    unallocated: float       # unallocated_harm / G, in behaviour units of the common chain [1/h]
    targets: TargetsResult


@dataclass(frozen=True)
class AllocationResult:
    rule: str                                     # rule used downstream
    B: float                                      # behaviour budget for the logical scenarios [1/h]
    A_prime: float                                # harm budget for the logical scenarios [1/h]
    caps: np.ndarray                              # human caps h_k [1/h], inf = none
    G_k: np.ndarray                               # harm chain per LS [-]
    used: RuleOutcome                             # outcome of the rule used
    comparison: dict[str, Optional[RuleOutcome]]  # every rule; None where its inputs are missing


def rule_weights(rule: str, lambda_U: np.ndarray, scenarios: Sequence[LogicalScenario]) -> Optional[np.ndarray]:
    """Weights v_k of a budget rule: the harm budget a_k is proportional to v_k before the human-cap step.

    equal_protection        v_k = lambda_k^U  ->  p_k* G_k = A' / sum_j lambda_j^U in every LS
    proportional_to_human   v_k = s_k         ->  same improvement factor over human drivers in every LS
    equal_split             v_k = 1           ->  a_k = A' / K
    fixed                   v_k = fixed_share_k
    Returns None if the rule needs an input that is not given (human_share or fixed_share).
    """
    if rule == "equal_protection":
        return np.asarray(lambda_U, float).copy()
    if rule == "proportional_to_human":
        vals = [s.human_share for s in scenarios]
        return None if any(v is None for v in vals) else np.array(vals, float)
    if rule == "equal_split":
        return np.ones(len(scenarios))
    if rule == "fixed":
        vals = [s.fixed_share for s in scenarios]
        return None if any(v is None for v in vals) else np.array(vals, float)
    raise ValueError(f"unknown allocation rule {rule!r}")


def allocate_with_caps(B: float, weights: np.ndarray, caps: np.ndarray, max_iter: int = 1000
                       ) -> tuple[np.ndarray, np.ndarray, int]:
    """Proportional allocation with upper caps (clamp and redistribute).

    Formula    Repeat: b_k = B_free * v_k / sum_{j free} v_j over the free LS; every b_k > cap_k is set to
               cap_k and removed from the free set; B_free is reduced by the clamped amounts. Stop when no
               free budget exceeds its cap.
    Result     b_k = min(cap_k, theta * v_k) with theta such that sum_k b_k = B, if the caps allow it.
               Clamping only increases the free budgets, so a clamped LS never needs to be released and
               the loop ends after at most K + 1 passes. Works in any unit (behaviour or harm), as long as
               B and the caps are in the same unit.
    Parameters B [1/h]; weights v_k (> 0); caps [1/h] (inf = no cap).
    Returns    (b [1/h], clamped mask, number of passes). If every LS is clamped, sum(b) < B and the
               remainder is reported as unallocated.
    Source     Human caps with clamp-and-redistribute [derived in this course].
    """
    v = np.asarray(weights, float)
    caps = np.asarray(caps, float)
    K = len(v)
    b = np.zeros(K)
    free = np.ones(K, dtype=bool)
    remaining = B
    passes = 0
    for passes in range(1, max_iter + 1):
        idx = np.flatnonzero(free)
        if idx.size == 0:
            break
        trial = remaining * v[idx] / v[idx].sum()
        over = idx[trial > caps[idx]]
        if over.size == 0:
            b[idx] = trial
            break
        b[over] = caps[over]
        free[over] = False
        remaining -= float(caps[over].sum())
    return b, ~free, passes


def apply_budget_rule(rule: str, A_prime: float, L: float, lambda_U: np.ndarray,
                      scenarios: Sequence[LogicalScenario], caps: np.ndarray, G_k: np.ndarray,
                      G: float) -> Optional[RuleOutcome]:
    """One budget rule in harm units, the human-cap step and the Cl. 9.3 (e) targets; None if not applicable."""
    v = rule_weights(rule, lambda_U, scenarios)
    if v is None:
        return None
    a, clamped, passes = allocate_with_caps(A_prime, v, caps * G_k)
    b = a / G_k
    b[clamped] = caps[clamped]  # exact cap value, free of rounding in a / G_k
    w = np.array([s.importance_factor for s in scenarios], float)
    ua = A_prime - float(a.sum())
    if abs(ua) <= 1e-12 * A_prime:
        ua = 0.0  # rounding noise, not unallocated budget
    return RuleOutcome(rule, v, a, b, a / A_prime, clamped, passes, ua, ua / G,
                       cl9_3e_failure_targets(b, lambda_U, w, L, G_k))


def cl9_3d_budget_per_logical_scenario(A_prime: float, B: float, L: float, lambda_U: np.ndarray,
                                       scenarios: Sequence[LogicalScenario], rule: str, G_k: np.ndarray,
                                       G: float) -> AllocationResult:
    """Cl. 9.3 (d): budget per logical scenario by a safety rule, with human caps; all rules compared.

    Computes   Harm budgets a_k and behaviour budgets b_k for the chosen rule, then the human-cap step; the
               same for every applicable rule, for the comparison table.
    Formula    A' = (1 - f) A_H;  b_k = a_k / G_k
               equal_protection:      a_k = A' * lambda_k^U / sum_j lambda_j^U   (p_k* G_k equal for all k)
               proportional_to_human: a_k = A' * s_k                              (same factor over humans)
               equal_split:           a_k = A' / K                                (comparison only)
               fixed:                 a_k = A' * fixed_share_k
               cap step:              a_k = min(h_k G_k, theta * v_k), sum_k a_k = A'  (see allocate_with_caps)
               With one common chain G: A' = G B and b_k = B * v_k / sum_j v_j, the R_HB formulation.
    Parameters A_prime [1/h]; B [1/h]; L [-]; lambda_U [1/h] (pilot bounds, 9.3 (b)); scenarios (human_share
               s_k [-], human_cap_behaviour_rate h_k [1/h], fixed_share [-], importance_factor w_k [-]);
               rule; G_k [-] and G [-] (Cl. 6.4).
    Returns    AllocationResult (rule used, caps, outcome, comparison of all rules).
    Assumptions The rule is chosen and the split frozen before confirmatory data exist; shares move only
               between campaigns, with fresh evidence. Test cost plays no part: the split decides how much
               risk is accepted, cost may only decide how evidence is produced.
    Sources    Equal-protection rule [derived in this course]; full conditioning per LS: Putze et al. 2023,
               arXiv:2304.10170, Sec. IV-B(b) [checked]; split budgets to avoid concentrating residual
               risk, scenario-class criteria add up to the hazard-based criterion, one validation target per
               scenario class: Hofmeister & Kinalzyk (AVL, ca. 2023), Sec. 2.2 [location not checked];
               budgets add up: Warg et al. 2020, QRN, Sec. III-B [location not checked]; budgets frozen
               before the confirmatory campaign: Werling et al. 2025, arXiv:2503.20544, Sec. 3.3, Remark 3.7
               [location not checked]; more than one validation target can be needed for one acceptance
               criterion: ISO 21448:2022 3.33 Note 3, p. 10 [checked]. Proportional-to-human rule, equal
               split and caps [derived in this course].
    """
    caps = np.array([np.inf if s.human_cap_behaviour_rate is None else s.human_cap_behaviour_rate
                     for s in scenarios], float)
    G_k = np.asarray(G_k, float)
    comparison = {r: apply_budget_rule(r, A_prime, L, lambda_U, scenarios, caps, G_k, G) for r in ALLOCATION_RULES}
    used = comparison[rule]
    if used is None:
        raise InputError(f"budget.allocation_rule = {rule!r} needs inputs that are not given")
    return AllocationResult(rule, B, A_prime, caps, G_k, used, comparison)

# %% [markdown]
# ## Cl. 9.3 (e) · Allowed failure probability and simulation runs per logical scenario
#
# A budget b_k fixes the allowed failure probability per encounter, p_k* = b_k / lambda_k^U, and with it
# the number of simulation runs that must pass with zero failures, n_k = L w_k / p_k*. The runs sample the
# parameter distribution of the logical scenario with importance sampling biased towards the triggering-
# condition regions; w_k is the largest importance weight in the failure region (w_k = 1 for plain Monte
# Carlo). With equal protection and one chain, n_k = L w_k sum_j lambda_j^U / B no longer depends on how
# common the logical scenario is, only on how efficient its sampling is. Assumption to defend: w = p/q <=
# w_k everywhere in the failure region (a defensive mixture), and each run is an independent concrete
# scenario (see Cl. 11 on independent evidence units).

# %%
def cl9_3e_failure_targets(b: np.ndarray, lambda_U: np.ndarray, w: np.ndarray, L: float,
                           G_k: np.ndarray) -> TargetsResult:
    """Cl. 9.3 (e): allowed failure probability per encounter and zero-failure simulation runs per LS.

    Computes   p_k*, 1/p_k*, the harm probability per encounter p_k* G_k, n_k (exact and rounded up), their
               total, and the protection ratio.
    Formula    p_k* = b_k / lambda_k^U
               n_k  = L * w_k / p_k* = L * w_k * lambda_k^U / b_k
               protection ratio = max_k (p_k* G_k) / min_k (p_k* G_k)   (= max p* / min p* with one chain)
    Parameters b [1/h] (9.3 (d)); lambda_U [1/h] (9.3 (b)); w = importance factors w_k [-]; L [-] (9.3 (a));
               G_k [-] (Cl. 6.4).
    Returns    TargetsResult.
    Assumptions Zero failures are planned. Importance sampling: p_k = E_q[f w] <= w_k P_q(f = 1), so n_k
               weighted runs with no failure bound p_k like n_k / w_k plain encounters; this needs
               w = p/q <= w_k everywhere in the failure region of LS k. Run counts are planning values;
               Clause 11 uses them exactly unless runs_executed is given.
    Sources    Allowed failure probability p* = b / lambda^U [derived in this course]. Zero-failure bound:
               ISO 21448:2022 C.3, Formula (C.7), p. 137 [checked]. Importance sampling over parameter
               distributions: ISO 21448:2022 C.5, pp. 146-151 [checked]; Owen 2013, Monte Carlo theory,
               methods and examples, Ch. 9 [checked]; Zhao et al. 2017, IEEE T-ITS 18(3):595-607 [checked];
               using w_max inside the zero-failure bound [derived in this course].
    """
    b = np.asarray(b, float)
    p_star = b / lambda_U
    harm = p_star * np.asarray(G_k, float)
    n = L * np.asarray(w, float) / p_star
    return TargetsResult(p_star=p_star, one_in=1.0 / p_star, harm_per_encounter=harm, n=n, n_ceil=np.ceil(n),
                         n_total=float(n.sum()), protection_ratio=float(harm.max() / harm.min()))

# %% [markdown]
# ## Cl. 9.3 (f) / Annex C.1 · Simulator credibility
#
# ISO 21448 C.1 makes simulation accuracy part of the safety argument. A simulated pass is only evidence
# if the simulator is close enough to reality. Paired runs (same scenario on the proving ground and in
# simulation) give the error e = y_sim - y_real; its spread is bounded above with a chi-square interval at
# C_b. A simulated run counts as a pass only if it clears the critical value by delta = mu + z sigma^U; a
# real failure can then hide behind a simulated pass only if the error exceeds delta, with probability
# Phi(-z) under a Gaussian error model, and Phi(-z) is added to every failure bound in Clause 11. Choose z
# so that Phi(-z) is small against the smallest p_k* (auto mode: Phi(-z) = f min_k p_k*). Assumption to
# defend: this is the weakest link, since nobody can measure a Gaussian tail at 6 sigma from 180 pairs;
# place pairs near the pass/fail boundary and check the error per logical scenario.

# %%
@dataclass(frozen=True)
class SimulatorResult:
    chi2_lower: float           # chi2_{1-C_b}(m_pairs - 1) [-]
    sigma_U: float              # upper bound on sigma [m]
    se_mu: float                # sigma_hat / sqrt(m_pairs), standard error of mu_hat [m] (information)
    z_mode: str
    z: float                    # z used [-]
    delta: float                # margin used [m]
    p_miss: float               # Phi(-z) used [-]
    z_fixed: float
    delta_fixed: float
    p_miss_fixed: float
    z_auto: float
    delta_auto: float
    p_miss_auto: float
    p_miss_over_min_p_star: float  # Phi(-z) / min_k p_k* for the z used [-]


def annexC1_simulator_credibility(sim: Simulator, C_b: float, p_star: np.ndarray) -> SimulatorResult:
    """Cl. 9.3 (f) / Annex C.1: upper bound on simulator error spread, pass margin and miss probability.

    Computes   sigma^U, z (fixed or automatic), delta and Phi(-z); both z options are reported.
    Formula    sigma^U = sigma_hat * sqrt((m_pairs - 1) / chi2_{1 - C_b}(m_pairs - 1))
               delta   = mu_hat + z * sigma^U
               Phi(-z) = norm.sf(z)
               auto:   z = norm.isf(f * min_k p_k*), i.e. Phi(-z) = f * min_k p_k*
    Parameters sim.m_pairs [count]; sim.mu_hat [m]; sim.sigma_hat [m]; sim.z_mode; sim.z_fixed [-];
               sim.z_auto_fraction f [-]; C_b [-]; p_star [-] from 9.3 (e).
    Returns    SimulatorResult.
    Assumptions Errors e are independent, Gaussian, with the same mu and sigma in every logical scenario
               and near the pass/fail boundary. mu_hat is used as a point estimate; its standard error
               sigma_hat / sqrt(m_pairs) is reported for comparison with z sigma^U. A negative mu_hat
               (pessimistic simulator) reduces delta and should be checked for plausibility.
    Sources    Simulation accuracy is part of the safety argument: ISO 21448:2022 C.1, p. 125 [checked].
               Upper bound on sigma via chi-square: Casella & Berger 2002, Statistical Inference, Thm 5.3.1
               [location not checked]. Margin delta = mu + z sigma^U and adding Phi(-z) to the failure bound
               [derived in this course].
    """
    nu = sim.m_pairs - 1
    chi2_lo = float(chi2.ppf(1.0 - C_b, nu))
    sigma_U = sim.sigma_hat * math.sqrt(nu / chi2_lo)
    z_auto = float(norm.isf(sim.z_auto_fraction * float(np.min(p_star))))
    z_fixed = sim.z_fixed
    z = z_fixed if sim.z_mode == "fixed" else z_auto
    p_miss = float(norm.sf(z))
    return SimulatorResult(
        chi2_lower=chi2_lo, sigma_U=sigma_U, se_mu=sim.sigma_hat / math.sqrt(sim.m_pairs),
        z_mode=sim.z_mode, z=z, delta=sim.mu_hat + z * sigma_U, p_miss=p_miss,
        z_fixed=z_fixed, delta_fixed=sim.mu_hat + z_fixed * sigma_U, p_miss_fixed=float(norm.sf(z_fixed)),
        z_auto=z_auto, delta_auto=sim.mu_hat + z_auto * sigma_U, p_miss_auto=float(norm.sf(z_auto)),
        p_miss_over_min_p_star=p_miss / float(np.min(p_star)),
    )

# %% [markdown]
# ## Cl. 9.4 · Validation targets (work product)
#
# ISO 21448 3.33 Note 3 allows, and here requires, more than one validation target for one acceptance
# criterion. The work product of Clause 9 lists them all: the tolerable rate R_HB the release claim is
# judged against, the zero-failure simulation runs per logical scenario, the targeted cases per logical
# scenario, the confirmatory and discovery driving hours, and the simulator evidence (paired runs and the
# pass margin delta).

# %%
@dataclass(frozen=True)
class ValidationTarget:
    id: str        # e.g. "VT-runs-LS-1"
    what: str      # what has to be shown
    value: float
    unit: str
    evaluated_in: str  # clause that evaluates it


def cl9_4_validation_targets(inputs: WorkbookInputs, R_HB: float, targets: TargetsResult, sim: SimulatorResult,
                             fleet_hours_per_day: float) -> list[ValidationTarget]:
    """Cl. 9.4: the list of validation targets that together argue the acceptance criterion.

    Computes   Nothing new; collects the targets of 9.3 (a)-(f) into one work product.
    Returns    list of ValidationTarget (id, what, value, unit, clause that evaluates it).
    Sources    Validation target, more than one can be needed: ISO 21448:2022 3.33 Note 3, p. 10 [checked];
               V&V strategy includes validation targets: 9.1 a)-b), p. 42 [checked]; 9.4 (work products)
               [location not checked]; one validation target per scenario class: Hofmeister & Kinalzyk
               (AVL, ca. 2023), Sec. 2.2 [location not checked].
    """
    he = inputs.selected_he
    out = [ValidationTarget("VT-R", f"sum of upper bounds on the rate of {he.hb_id} in {he.id} stays below R_HB "
                            "(with per-LS chains: harm below A_H)", R_HB, "1/h", "Cl. 12")]
    for k, s in enumerate(inputs.logical_scenarios):
        out.append(ValidationTarget(
            f"VT-runs-{s.id}", f"simulation runs in {s.id} without failure (importance sampling, "
            f"w = {s.importance_factor:g}; p* = 1 in {targets.one_in[k]:,.0f})", float(targets.n_ceil[k]), "runs",
            "Cl. 11"))
    for s in inputs.logical_scenarios:
        out.append(ValidationTarget(f"VT-cases-{s.id}", f"targeted cases in {s.id} from the triggering "
                                    "conditions, all must pass", float(s.targeted_cases), "cases", "Cl. 10"))
    d = inputs.driving
    out.append(ValidationTarget("VT-conf", "confirmatory driving on the frozen release (exposure bounds; "
                                f"{d.confirmatory_hours / fleet_hours_per_day:.3g} fleet days)",
                                d.confirmatory_hours, "h", "Cl. 11"))
    out.append(ValidationTarget("VT-disc", "discovery driving searched for scenarios outside the logical "
                                f"scenarios ({d.discovery_hours / fleet_hours_per_day:.3g} fleet days)",
                                d.discovery_hours, "h", "Cl. 11"))
    out.append(ValidationTarget("VT-pairs", "paired simulation/real runs for the simulator error model",
                                float(inputs.simulator.m_pairs), "pairs", "Annex C.1"))
    out.append(ValidationTarget("VT-delta", f"pass margin: a simulated run passes only if it clears the critical "
                                f"value by delta (z = {sim.z:.4g})", sim.delta, "m", "Annex C.1"))
    return out

# %% [markdown]
# ## Cl. 10 · Evaluation of known scenarios
#
# Each triggering condition is infused into the logical scenarios it lies in, at the boundary of its
# region, as a set of targeted cases fixed before testing (for example light x road x pedestrian size x
# approach speed). The known-scenario evaluation passes only if every targeted case passes. This is
# verification: it shows that the known triggering conditions are handled, but it gives no failure rate,
# so it does not enter the sum of Clause 11 and 12. A logical scenario that contains a triggering
# condition but has no targeted case leaves the evaluation incomplete, which counts as not passed.
#
# Evidence units (Patel & Jung 2026, Sec. 3.5): a targeted case counts only as an independent concrete
# scenario, not as frames or time slices of one scene, and a performance shown under one triggering
# condition counts for another only after a test under that other condition. Each logical scenario can
# record how this is met in `independent_units_note`; the report prints it.

# %%
@dataclass(frozen=True)
class KnownScenarioResult:
    cases: np.ndarray          # targeted cases per LS [count]
    failures: np.ndarray       # failed targeted cases per LS [count]
    passed_per_ls: np.ndarray  # no failure and (cases > 0 or no TC in this LS)
    missing_cases: list[str]   # LS ids with a TC but no targeted case
    total_cases: int
    total_failures: int
    passed: bool


def cl10_known_scenarios(inputs: WorkbookInputs, tcs: TriggeringConditionResult) -> KnownScenarioResult:
    """Cl. 10: evaluation of known scenarios by targeted cases.

    Computes   Per LS: targeted cases run and failed, pass/fail; overall pass/fail.
    Formula    pass_k = (targeted_failures_k == 0) and (targeted_cases_k > 0 if LS k contains a TC)
               pass   = all_k pass_k
    Parameters inputs.logical_scenarios (targeted_cases, targeted_failures [count]); tcs (Cl. 7.3).
    Returns    KnownScenarioResult.
    Assumptions The targeted cases are built from the triggering conditions and fixed before testing; each
               case is an independent concrete scenario, and each triggering condition is tested itself
               rather than inferred from another. Verification only: passing gives no failure rate and does
               not enter the Clause 12 sum.
    Sources    ISO 21448:2022 10.7, pp. 49-50 (evaluation of the residual risk due to known hazardous
               scenarios) [checked]; 7.4 (acceptability of the response to the triggering conditions)
               [location not checked]; behavioural pass/fail criteria next to the statistical ones:
               Hofmeister & Kinalzyk (AVL, ca. 2023) [location not checked]; independent evidence units and
               evidence per triggering condition: Patel & Jung 2026, arXiv:2610.35092, Sec. 3.5
               [location not checked].
    """
    scen = inputs.logical_scenarios
    cases = np.array([s.targeted_cases for s in scen], int)
    fails = np.array([s.targeted_failures for s in scen], int)
    has_tc = np.array([bool(t) for t in tcs.tcs_per_ls], bool)
    missing = [s.id for k, s in enumerate(scen) if has_tc[k] and cases[k] == 0]
    passed_k = (fails == 0) & ~(has_tc & (cases == 0))
    return KnownScenarioResult(cases, fails, passed_k, missing, int(cases.sum()), int(fails.sum()),
                               bool(passed_k.all()))

# %% [markdown]
# ## Cl. 11 · Evaluation of unknown scenarios
#
# Failures inside the logical scenarios that no triggering condition predicted, and scenarios outside
# the logical scenarios, are the unknown hazardous scenarios of ISO 21448 4.2.2. Clause 11 evaluates them
# statistically with fresh data on the frozen release: exposure bounds from the confirmatory driving,
# failure bounds from the simulation runs sampled over each logical scenario (with j_k observed failures),
# and a term for scenarios outside the logical scenarios from the discovery driving (11.3 Table 11 lists
# fleet tests and random scenario simulation among the methods). Every term is an upper bound at C_b; with
# per-LS chains each term is also multiplied by its G_k to give a harm term.
#
# Three points from the literature apply here. The runs count only as independent concrete scenarios
# (Patel & Jung 2026): frames or slices of one simulated scene are not separate trials. Importance
# sampling and simulation reduce the field testing but do not replace it (Betschinske et al. 2025): the
# exposure bounds and the discovery term still need confirmatory driving. Scenario exploration such as
# dense reinforcement learning (Feng et al. 2023) or Bayesian safety validation (Moss et al. 2023) helps to
# find failures and new kinds of scenario before the campaign; the frozen campaign then counts them.

# %%
@dataclass(frozen=True)
class UnknownScenarioResult:
    lambda_U_conf: np.ndarray   # confirmatory exposure bounds [1/h]
    n_used: np.ndarray          # runs used [runs]
    F: np.ndarray               # j-failure factors [-]
    p_U: np.ndarray             # failure bounds incl. Phi(-z) [-]
    terms: np.ndarray           # lambda_U_conf * p_U, behaviour rate [1/h]
    harm_terms: np.ndarray      # terms * G_k, harm rate [1/h]
    lambda_new_U: float         # [1/h]
    unknown_term: float         # lambda_new_U * p_new, behaviour rate [1/h]
    unknown_harm: float         # unknown_term * G_unk, harm rate [1/h]
    good_turing: Optional[float]   # N1 / N, information only
    bk_epsilon: Optional[float]    # sqrt(ln(1/(1-C_b)) / N), information only


def cl11_unknown_scenarios(inputs: WorkbookInputs, C_b: float, n_planned: np.ndarray, p_miss: float,
                           G_k: np.ndarray, G_unk: float) -> UnknownScenarioResult:
    """Cl. 11: upper bounds on every term of the behaviour rate from fresh data on the frozen release.

    Computes   Confirmatory exposure bounds, failure bounds per LS, the unknown-scenario term, and the same
               terms in harm units.
    Formula    lambda_k^U,conf = chi2_{C_b}(2 N_k,conf + 2) / (2 tau_conf)
               p_k^U = F(j_k) * w_k / n_k + Phi(-z),   F(j) = chi2_{C_b}(2 j + 2) / 2,  F(0) = L
               lambda_new^U = chi2_{C_b}(2 N1 + 2) / (2 tau_disc)   (= L / tau_disc for N1 = 0)
               term_k = lambda_k^U,conf * p_k^U;  unknown term = lambda_new^U * p_new
               harm term_k = term_k * G_k;  unknown harm = unknown term * G_unk
               Good-Turing missing mass N1 / N and the Berend-Kontorovich deviation
               eps = sqrt(ln(1/(1 - C_b)) / N) are reported for information only.
    Parameters inputs (N_conf, j_k, w_k, runs_executed, tau_conf, tau_disc, N1, N_discovery, p_new);
               C_b [-]; n_planned [runs] (9.3 (e), exact, not rounded); p_miss = Phi(-z) [-] (Annex C.1);
               G_k [-], G_unk [-] (Cl. 6.4).
    Returns    UnknownScenarioResult.
    Assumptions n_k is the planned, unrounded run count unless runs_executed is given; each run is an
               independent concrete scenario. F(j)/n is the Poisson upper bound on the failure probability
               under the test density; it is at least the exact binomial bound. For N1 > 0 a new kind of
               scenario appeared: the bound then treats the N1 singletons as encounters with unknown
               scenarios (its point value N1/tau equals the Good-Turing missing mass N1/N times the
               encounter rate N/tau); the proper response is to add a logical scenario and re-plan, and the
               report says so. p_new is argued from a design rule (e.g. a Cl. 8.3.3 functional
               restriction), not tested statistically. Unknown scenarios use the chain G_unk (default: the
               common chain of the hazardous event).
    Sources    Unknown scenarios: ISO 21448:2022 11.1, p. 50 [checked]; methods incl. fleet test and random
               scenario simulation: 11.3, Table 11, p. 51 [checked]. Exposure: Garwood 1936 [location not
               checked]. Failure bound: Owen 2013 Ch. 9 [checked]; ISO 21448:2022 C.3, Formula (C.7),
               p. 137 [checked]; w_max inside the bound and adding Phi(-z) [derived in this course].
               Unknown-scenario term: zero-failure bound as above [checked]; Good 1953, Biometrika
               40:237-264 [location not checked]; Berend & Kontorovich 2013, arXiv:1210.3248, Theorem 1
               [checked]; the N1 > 0 extension [derived in this course]. 8.3.3 (functional restrictions)
               [location not checked]. Independent units: Patel & Jung 2026, arXiv:2610.35092, Sec. 3.5
               [location not checked]. Field testing not replaced: Betschinske et al. 2025,
               arXiv:2506.10363, Sec. VII [checked]. Harm terms per LS: Putze et al. 2023, Sec. IV-B(b)
               [checked].
    """
    scen = inputs.logical_scenarios
    N_conf = np.array([s.N_conf for s in scen], int)
    lam_conf = np.asarray(poisson_upper_rate(N_conf, inputs.driving.confirmatory_hours, C_b), float)
    j = np.array([s.failures for s in scen], int)
    w = np.array([s.importance_factor for s in scen], float)
    n_used = np.array([n_planned[k] if s.runs_executed is None else s.runs_executed for k, s in enumerate(scen)],
                      float)
    F = np.asarray(failure_factor(j, C_b), float)
    p_U = F * w / n_used + p_miss
    terms = lam_conf * p_U
    un = inputs.unknown
    lam_new = float(poisson_upper_rate(un.N1, inputs.driving.discovery_hours, C_b))
    gt = None if not un.N_discovery else un.N1 / un.N_discovery
    eps = None if not un.N_discovery else math.sqrt(math.log(1.0 / (1.0 - C_b)) / un.N_discovery)
    unknown_term = lam_new * un.p_new
    return UnknownScenarioResult(lam_conf, n_used, F, p_U, terms, terms * np.asarray(G_k, float), lam_new,
                                 unknown_term, unknown_term * G_unk, gt, eps)

# %% [markdown]
# ## Cl. 12 · Evaluation of the achievement of the SOTIF and recommendation for release
#
# The release claim is that the sum of all upper bounds on the harm rate is at most A_H:
# sum_k lambda_k^U p_k^U G_k + lambda_new^U p_new G_unk <= A_H. With one common chain G this is the same
# as the sum of the behaviour bounds being at most R_HB = A_H / G, the form used in the course. By
# Cl. 9.3 (a) the claim holds at joint confidence C. Release is recommended (12.4) only if, in addition,
# every Clause 10 targeted case passed and no term is above its human cap, so a good total cannot hide a
# logical scenario that is worse than human drivers. Each term is also shown against its budget b_k: the
# total decides, the per-budget view shows where the margin sits. If release is not recommended, the way
# back is Clause 8 (functional modifications, e.g. 8.3.3 functional restrictions such as a lower speed
# near crossings) and a new frozen campaign on the new release. Assumption to defend: the plan was frozen
# before the data, all evidence is from one release, runs are independent concrete scenarios, and p_new
# is argued by a tested design rule.

# %%
@dataclass(frozen=True)
class AchievementResult:
    total: float                    # sum of behaviour upper bounds [1/h]
    R_HB: float                     # [1/h]
    total_over_R_HB: float          # total / R_HB [-] (the criterion ratio when one chain is used)
    harm_total: float               # sum of harm upper bounds [1/h]
    A_H: float                      # [1/h]
    ratio: float                    # harm_total / A_H [-], the criterion ratio
    criterion_met: bool             # harm_total <= A_H (= total <= R_HB with one chain)
    term_over_budget: np.ndarray    # term_k / b_k [-]
    unknown_over_reserve: float     # unknown harm / reserve harm [-] (inf if no reserve)
    caps_met: np.ndarray            # term_k <= h_k (True where no cap)
    caps_all_met: bool
    known_passed: bool              # Clause 10
    recommended: bool               # all three conditions
    reasons: list[str]


def cl12_achievement(unk: UnknownScenarioResult, known: KnownScenarioResult, alloc: AllocationResult,
                     reserve: ReserveResult, R_HB: float, A_H: float, ls_ids: Sequence[str],
                     per_ls_chain: bool = False) -> AchievementResult:
    """Cl. 12: evaluation of the achievement of the SOTIF and the recommendation for release.

    Computes   Totals of the upper bounds (behaviour and harm units), the criterion ratio, each term against
               its budget and human cap, and the recommendation with its reasons.
    Formula    total      = sum_k lambda_k^U,conf p_k^U + lambda_new^U p_new
               harm total = sum_k lambda_k^U,conf p_k^U G_k + lambda_new^U p_new G_unk
               criterion met iff harm total <= A_H  (with one common chain: iff total <= R_HB)
               recommended  iff  criterion met  and  every Clause 10 targeted case passed
                                 and  term_k <= h_k for every k
    Parameters unk (Cl. 11); known (Cl. 10); alloc (budgets b_k, caps h_k); reserve (b_unk, reserve_harm);
               R_HB [1/h]; A_H [1/h]; ls_ids; per_ls_chain (True if the LS chains differ).
    Returns    AchievementResult.
    Assumptions As Cl. 11; the joint confidence C holds for the sum (m bounds at C_b each; the G_k are fixed
               numbers, not estimated bounds).
    Sources    Coverage of known scenarios and argument for unknown ones: ISO 21448:2022 12.3 c), p. 54
               [checked]; 12.4 (recommendation for SOTIF release) [location not checked]; residual risk
               with sufficient confidence: 11.1, p. 50 [checked]; sum of upper bounds and full conditioning:
               Putze et al. 2023, arXiv:2304.10170, Sec. IV-B(b), Eq. (2) [checked]; joint confidence:
               C.6.3.2 Example 1, p. 156 [checked]; human caps [derived in this course].
    """
    total = float(unk.terms.sum()) + unk.unknown_term
    harm_total = float(unk.harm_terms.sum()) + unk.unknown_harm
    ratio = harm_total / A_H
    criterion_met = bool(harm_total <= A_H)
    b = alloc.used.b
    with np.errstate(divide="ignore", invalid="ignore"):
        tob = np.where(b > 0, unk.terms / b, np.inf)
    uor = unk.unknown_harm / reserve.reserve_harm if reserve.reserve_harm > 0 else math.inf
    caps_met = unk.terms <= alloc.caps
    caps_all = bool(caps_met.all())
    if per_ls_chain:
        first = (f"{'met' if criterion_met else 'NOT met'}: sum of upper bounds on harm {harm_total:.4e} /h "
                 f"{'<=' if criterion_met else '>'} A_H = {A_H:.4e} /h ({100 * ratio:.1f} %; per-LS chains)")
    else:
        first = (f"{'met' if criterion_met else 'NOT met'}: sum of upper bounds {total:.4e} /h "
                 f"{'<=' if criterion_met else '>'} R_HB = {R_HB:.4e} /h ({100 * ratio:.1f} %; in harm units "
                 f"{harm_total:.4e} /h vs A_H = {A_H:.4e} /h)")
    reasons = [
        first,
        f"{'met' if known.passed else 'NOT met'}: Clause 10, {known.total_cases - known.total_failures} of "
        f"{known.total_cases} targeted cases passed"
        + (f"; no targeted cases for {', '.join(known.missing_cases)} although triggering conditions lie there"
           if known.missing_cases else ""),
        "met: every term is at or below its human cap" if caps_all else
        "NOT met: term above its human cap in " + ", ".join(i for i, ok in zip(ls_ids, caps_met) if not ok),
    ]
    return AchievementResult(total, R_HB, total / R_HB, harm_total, A_H, ratio, criterion_met, tob, uor, caps_met,
                             caps_all, known.passed, criterion_met and known.passed and caps_all, reasons)

# %% [markdown]
# ## Sensitivity: what if logical scenario k had j failures?
#
# The plan assumes zero failures in the simulation runs. With j failures in LS k, its failure bound grows
# by F(j)/L (1.41 for j = 1 at C_b = 0.99375), with everything else frozen. The table shows, per logical
# scenario, the total with one failure and the smallest j that would fail the statistical part of
# Clause 12 (harm total > A_H, i.e. total > R_HB with one chain, or a term above its cap). Use it while
# planning, to see where the margin is thin. After the campaign it must not be used to add runs until the
# bound fits: the stopping rule would then depend on the result. A real failure means analyse, fix
# (Clause 8), and run a new frozen campaign on the new release.

# %%
@dataclass(frozen=True)
class SensitivityRow:
    ls_id: str
    factor_j1: float                   # F(1) / F(j_k) [-]
    total_j1: float                    # behaviour total with j = 1 for this LS [1/h]
    ratio_j1: float                    # criterion ratio (harm total / A_H) with j = 1 [-]
    passed_j1: bool
    smallest_failing_j: Optional[int]  # None if not reached within j_max

# %% [markdown]
# ## Cl. 13 · Operation phase
#
# ISO 21448 13.1 asks for the field monitoring process to be defined before release. In operation the
# fleet drives T hours per year; at the limit R_HB it would show R_HB x T hazardous behaviours per year
# (0.365 in the mock). One year of driving cannot confirm the criterion (its zero-event upper bound is
# about eight times R_HB), but it can show that the criterion is violated: if the one-sided lower
# confidence bound lambda_L = chi2_{1-C}(2k) / (2T) for k observed behaviours exceeds R_HB, the data are
# unlikely under any rate at or below R_HB, and the SOTIF issue process of 13.4 is triggered. The step
# reports the smallest such k per year, its false-alarm probability at R_HB and the detection
# probability at higher true rates. Any field hazardous behaviour that cannot be attributed to a listed
# triggering condition counts against the reserve for unknown scenarios and triggers 13.4 by itself.
#
# The fixed one-year rule is valid for one look at the end of the year. Field data are watched
# continuously, and looking repeatedly with a fixed-sample rule inflates the false-alarm probability.
# The anytime-valid alternative (Ramdas et al. 2023; Wald's SPRT is its classical form) is a Poisson
# likelihood-ratio e-process, E(T) = a^k exp(-(a - 1) R_HB T) for k behaviours in T hours, testing R_HB
# against the alternative a R_HB. Under any true rate at or below R_HB it is a nonnegative supermartingale
# starting at 1, so by Ville's inequality the probability that it ever reaches 1/(1 - C) is at most
# 1 - C, however often it is checked. The alarm count grows slowly with time; the price of anytime
# validity is a higher count than the fixed rule at the one-year mark. With per-LS chains the monitoring
# limit R_HB assumes the field mix of logical scenarios matches the plan; otherwise monitor each logical
# scenario against its budget b_k.

# %%
@dataclass(frozen=True)
class OperationResult:
    T: float                                        # fleet hours per year [h/yr]
    C: float                                        # confidence of the monitoring test [-]
    expected_at_limit: float                        # R_HB * T [1/yr]
    expected_at_bound: float                        # Clause 12 total * T [1/yr]
    k_min: int                                      # smallest yearly count with lambda_L > R_HB
    lambda_L_k_min: float                           # [1/h]
    false_alarm_k_min: float                        # P(X >= k_min | R_HB T) [-]
    rows: list[tuple[int, float, bool, float]]      # (k, lambda_L, lambda_L > R_HB, P(X >= k | R_HB T))
    detection: list[tuple[float, float]]            # (true rate / R_HB, P(X >= k_min) in one year)
    zero_event_upper: float                         # ln(1/(1-C)) / T [1/h]
    alt_factor: float                               # a [-]
    e_threshold: float                              # 1 / (1 - C) [-]
    e_rows: list[tuple[float, float, float, int, float, float]]
    # (years, hours, R_HB x hours, alarm count k, E(k), E(k - 1))
    e_floor: int                                    # alarm count as T -> 0 (no alarm with fewer events)


def eprocess_alarm_count(R_HB: float, hours: float, a: float, C: float) -> int:
    """Smallest count k with E = a^k exp(-(a - 1) R_HB hours) >= 1/(1 - C).

    Formula    k = ceil((ln(1/(1 - C)) + (a - 1) R_HB hours) / ln a), checked against E directly.
    Source     Ramdas, Gruenwald, Vovk & Shafer 2023 [checked] (at abstract level); Wald 1945 [location not
               checked]; the closed form [derived in this course].
    """
    thr = 1.0 / (1.0 - C)
    k = max(0, math.ceil((math.log(thr) + (a - 1.0) * R_HB * hours) / math.log(a)))
    while k > 0 and poisson_e_value(k - 1, hours, R_HB, a * R_HB) >= thr:
        k -= 1
    while poisson_e_value(k, hours, R_HB, a * R_HB) < thr:
        k += 1
    return k


def cl13_operation_monitoring(R_HB: float, total: float, C: float, T: float, alt_factor: float = 2.0,
                              multiples: Sequence[float] = (1, 2, 5, 10),
                              years: Sequence[float] = (0.5, 1, 2, 5)) -> OperationResult:
    """Cl. 13: field monitoring thresholds, fixed one-year rule and anytime-valid e-process.

    Computes   Expected hazardous behaviours per year at R_HB and at the Clause 12 bound; the smallest yearly
               count k_min whose lower confidence bound exceeds R_HB; false-alarm and detection probabilities;
               the zero-event upper bound after one year; the e-process alarm count after several periods.
    Formula    E[X] = R * T
               lambda_L(k) = chi2_{1-C}(2k) / (2T)  (k >= 1; 0 for k = 0)
               k_min = min { k : lambda_L(k) > R_HB }, equivalently P(X >= k_min | R_HB T) < 1 - C
               detection probability at true rate r: P(X >= k_min | r T)
               zero-event upper bound: ln(1/(1 - C)) / T
               e-process: E(t) = a^k(t) exp(-(a - 1) R_HB t);  alarm when E(t) >= 1/(1 - C)
    Parameters R_HB [1/h]; total [1/h] (Cl. 12); C [-] (the monitoring tests are not among the m bounds of the
               release claim); T = operation.fleet_hours_per_year [h/yr]; alt_factor a [-] > 1; multiples of
               R_HB for the detection table; years for the e-process table.
    Returns    OperationResult.
    Assumptions Field hazardous behaviours are counted by a defined detection rule (on-board monitoring) and
               form a Poisson process; the software release does not change during the monitoring period (a
               new release restarts the count and the e-process).
    Sources    Field monitoring process defined before release: ISO 21448:2022 13.1, p. 55 [checked];
               topics for observation incl. on-board monitoring and near-triggering events: 13.3,
               pp. 56-57 [checked]; SOTIF issue evaluation and resolution: 13.4 [location not checked];
               lower Poisson limit: Garwood 1936 [location not checked]; the k_min rule and the reserve rule
               [derived in this course]; e-process and Ville's inequality: Ramdas, Gruenwald, Vovk & Shafer
               2023, Statistical Science 38(4), arXiv:2210.01948 [checked] (at abstract level); sequential
               probability ratio test: Wald 1945 [location not checked].
    """
    mu = R_HB * T
    rows: list[tuple[int, float, bool, float]] = []
    k = 0
    while True:
        k += 1
        lam_L = poisson_lower_rate(k, T, C)
        rows.append((k, lam_L, lam_L > R_HB, float(poisson.sf(k - 1, mu))))
        if lam_L > R_HB or k > 10 ** 7:
            break
    k_min = k
    detection = [(float(r), float(poisson.sf(k_min - 1, r * R_HB * T))) for r in multiples]
    a = float(alt_factor)
    e_rows = []
    for y in years:
        hours = float(y) * T
        ka = eprocess_alarm_count(R_HB, hours, a, C)
        e_rows.append((float(y), hours, R_HB * hours, ka, poisson_e_value(ka, hours, R_HB, a * R_HB),
                       poisson_e_value(max(ka - 1, 0), hours, R_HB, a * R_HB)))
    return OperationResult(T, C, mu, total * T, k_min, rows[-1][1], rows[-1][3], rows, detection,
                           math.log(1.0 / (1.0 - C)) / T, a, 1.0 / (1.0 - C), e_rows,
                           eprocess_alarm_count(R_HB, 0.0, a, C))

# %% [markdown]
# ## Run the whole chain
#
# `run_chain` calls the steps in clause order and returns all results in one `ChainResults` object.
# `what_if_failures` and `sensitivity_failures` re-run Clauses 11 and 12 with changed failure counts.

# %%
@dataclass(frozen=True)
class ChainResults:
    hazards: HazardIdentificationResult
    risk: RiskEvaluationResult
    crit: CriterionResult
    tol: ToleranceResult
    naive: NaiveTargetResult
    tcs: TriggeringConditionResult
    joint: JointConfidenceResult
    expo: ExposureResult
    reserve: ReserveResult
    alloc: AllocationResult
    targets: TargetsResult
    sim: SimulatorResult
    validation_targets: list[ValidationTarget]
    known: KnownScenarioResult
    unknown: UnknownScenarioResult
    achievement: AchievementResult
    operation: OperationResult
    sensitivity: list[SensitivityRow] = field(default_factory=list)


def what_if_failures(inputs: WorkbookInputs, res: ChainResults, ls_id: str, j: int) -> AchievementResult:
    """Clause 12 result if logical scenario `ls_id` had j failures, with the frozen plan unchanged.

    Formula    p_k^U = F(j) w_k / n_k + Phi(-z) for that LS; all other terms as in Cl. 11.
    Parameters inputs; res (planning results: n_k, b_k, z, Clause 10); ls_id; j [count] >= 0.
    Returns    AchievementResult for the modified input.
    Source     As Cl. 11 and 12 [see there].
    """
    if j < 0:
        raise ValueError("j must be >= 0")
    if ls_id not in inputs.ls_ids:
        raise KeyError(f"unknown logical scenario {ls_id!r}; known: {inputs.ls_ids}")
    new = tuple(replace(s, failures=int(j)) if s.id == ls_id else s for s in inputs.logical_scenarios)
    mod = replace(inputs, logical_scenarios=new)
    unk = cl11_unknown_scenarios(mod, res.joint.C_b, res.targets.n, res.sim.p_miss, res.risk.G_k, res.risk.G_unk)
    return cl12_achievement(unk, res.known, res.alloc, res.reserve, res.tol.R_HB, res.crit.A_H, inputs.ls_ids,
                            res.risk.per_ls)


def sensitivity_failures(inputs: WorkbookInputs, res: ChainResults, j_max: int = 100) -> list[SensitivityRow]:
    """Sensitivity (planning aid): one-failure what-if and the smallest failing j, per logical scenario.

    Computes   For each LS k (others unchanged): total with j_k = 1, and the smallest j for which the
               statistical part of Clause 12 fails (harm total > A_H, i.e. total > R_HB with one chain, or a
               term above its cap), up to j_max.
    Formula    see `what_if_failures`; factor = F(1) / F(j_k) with j_k the observed count.
    Returns    list of SensitivityRow.
    Assumptions Planning aid only; must not drive post-hoc changes to the frozen campaign.
    Sources    As Cl. 11; the j-failure factor via Garwood 1936 [location not checked].
    """
    rows: list[SensitivityRow] = []
    for k, s in enumerate(inputs.logical_scenarios):
        a1 = what_if_failures(inputs, res, s.id, 1)
        smallest: Optional[int] = None
        for jj in range(0, j_max + 1):
            a = what_if_failures(inputs, res, s.id, jj)
            if not (a.criterion_met and a.caps_all_met):
                smallest = jj
                break
        rows.append(SensitivityRow(
            ls_id=s.id, factor_j1=float(failure_factor(1, res.joint.C_b) / res.unknown.F[k]),
            total_j1=a1.total, ratio_j1=a1.ratio, passed_j1=a1.criterion_met and a1.caps_all_met,
            smallest_failing_j=smallest))
    return rows


def run_chain(inputs: WorkbookInputs) -> ChainResults:
    """Run every step in clause order for one set of inputs and return all intermediate results."""
    he = inputs.selected_he
    scen = inputs.logical_scenarios
    hazards = cl6_3_hazard_identification(inputs)
    risk = cl6_4_risk_evaluation(inputs.chain, scen, inputs.unknown.G_unknown)
    crit = cl6_5_acceptance_criterion(inputs.benchmark, inputs.criterion, he.share_of_harm_class_budget)
    tol = annexC2_1_tolerable_rate(crit.A_H, risk.P_chain)
    naive = annexC3_naive_target(tol.R_HB, inputs.confidence.C, inputs.fleet, inputs.driving)
    tcs = cl7_3_triggering_conditions(inputs)
    joint = cl9_3a_joint_confidence(inputs.confidence.C, inputs.K, inputs.confidence.m_bounds)
    expo = cl9_3b_exposure_bounds([s.N_pilot for s in scen], inputs.driving.pilot_hours, joint.C_b)
    reserve = cl9_3c_reserve_for_unknown(tol.R_HB, crit.A_H, inputs.budget.reserve_fraction)
    alloc = cl9_3d_budget_per_logical_scenario(reserve.A_prime, reserve.B, joint.L, expo.lambda_U, scen,
                                               inputs.budget.allocation_rule, risk.G_k, risk.P_chain)
    w = np.array([s.importance_factor for s in scen], float)
    targets = cl9_3e_failure_targets(alloc.used.b, expo.lambda_U, w, joint.L, risk.G_k)
    sim = annexC1_simulator_credibility(inputs.simulator, joint.C_b, targets.p_star)
    vts = cl9_4_validation_targets(inputs, tol.R_HB, targets, sim, naive.fleet_hours_per_day)
    known = cl10_known_scenarios(inputs, tcs)
    unknown = cl11_unknown_scenarios(inputs, joint.C_b, targets.n, sim.p_miss, risk.G_k, risk.G_unk)
    ach = cl12_achievement(unknown, known, alloc, reserve, tol.R_HB, crit.A_H, inputs.ls_ids, risk.per_ls)
    op = cl13_operation_monitoring(tol.R_HB, ach.total, inputs.confidence.C, inputs.operation.fleet_hours_per_year,
                                   inputs.operation.alt_factor)
    res = ChainResults(hazards, risk, crit, tol, naive, tcs, joint, expo, reserve, alloc, targets, sim, vts,
                       known, unknown, ach, op)
    return replace(res, sensitivity=sensitivity_failures(inputs, res))

# %% [markdown]
# ## Work-product map
#
# The last part of the report maps the workbook outputs to the work-product subclauses of ISO 21448:
# 6.6, 7.5, 9.4, 10.8, 11.4, 12.5 and 13.5. The clause numbers come from the table of contents; what each
# subclause lists as work products was not checked page by page.

# %%
def work_product_map(inputs: WorkbookInputs, res: ChainResults) -> list[tuple[str, str]]:
    """Map the workbook outputs to the ISO 21448 work-product subclauses (one line each).

    Returns    list of (subclause, outputs that belong to it).
    Source     ISO 21448:2022 6.6, 7.5, 9.4, 10.8, 11.4, 12.5, 13.5 (work products) [location not checked].
    """
    he, ach, op = res.hazards.selected, res.achievement, res.operation
    ls = ", ".join(inputs.ls_ids)
    tc = ", ".join(t.id for t in inputs.triggering_conditions) or "none"
    return [
        ("6.6", f"function and ODD (Cl. 5); {len(inputs.hazardous_behaviours)} hazardous behaviours; "
                f"{len(inputs.hazardous_events)} hazardous events with harm class, S, C and share; selected "
                f"{he.id}; harm chain P_E, P_C, P_S (6.4); h = {res.crit.h:.4e} /h and A_H = {res.crit.A_H:.4e} /h "
                f"(6.5); R_HB = {res.tol.R_HB:.4e} /h (C.2.1)"),
        ("7.5", f"logical scenarios {ls} with parameter ranges; triggering conditions {tc} with parameter "
                "regions; TC x LS matrix; acceptability of the response (7.4) -> targeted cases of Cl. 10"),
        ("9.4", f"{len(res.validation_targets)} validation targets (VT-R, runs and targeted cases per LS, "
                f"confirmatory and discovery driving, paired runs, delta); budget rule {res.alloc.rule} with b_k "
                f"and p_k*; joint confidence m = {res.joint.m}, C_b = {res.joint.C_b:.5g}; reserve b_unk; naive "
                "target for scale (C.3)"),
        ("10.8", f"targeted-case results per LS: {res.known.total_cases - res.known.total_failures} of "
                 f"{res.known.total_cases} passed"),
        ("11.4", "confirmatory exposure bounds, failure bounds p_k^U, unknown-scenario term, discovery evidence "
                 "(N1, N, Good-Turing, Berend-Kontorovich)"),
        ("12.5", f"sum of upper bounds {100 * ach.ratio:.1f} % of the criterion (R_HB, or A_H in harm units); "
                 f"terms against budgets and human caps; sensitivity table; recommendation for SOTIF release "
                 f"(12.4): {'recommended' if ach.recommended else 'not recommended'}"),
        ("13.5", f"monitoring plan: expected {op.expected_at_limit:.3g} HB per year at R_HB; {op.k_min} or more "
                 f"HB in one year ({op.T:,.0f} h) show a violation at C = {op.C:g} (one look per year); "
                 f"anytime-valid e-process (a = {op.alt_factor:g}) alarms at "
                 + ", ".join(f"{r[3]} after {r[0]:g} yr" for r in op.e_rows)
                 + "; both trigger 13.4; field HB not attributable to a listed triggering condition count against "
                   "the reserve and trigger 13.4"),
    ]

# %% [markdown]
# ## Report and export
#
# `build_sections` turns the results into report sections, each with the formula in words, the
# quantities (name, symbol, value, unit, source), tables and notes. The same quantities, flattened, are
# the rows of the CSV/XLSX export. Printed output is plain ASCII so it survives any terminal and Excel
# (text from the input file is printed as given).

# %%
@dataclass(frozen=True)
class Quantity:
    name: str
    symbol: str
    value: float
    unit: str
    step: str
    source: str
    show: bool = True  # printed as a line in the report (per-LS values are printed in tables)


@dataclass
class Section:
    step: str
    title: str
    formulas: list[str]
    quantities: list[Quantity] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)  # sources not tied to a quantity


def _src(text: str, status: str) -> str:
    allowed = ("checked", "location not checked", "derived in this course")
    if status not in allowed:
        raise ValueError(f"source status must be one of {allowed}, got {status!r}")
    return f"{text} [{status}]"


def _source_catalogue() -> dict[str, str]:
    ok, nc, dc = "checked", "location not checked", "derived in this course"
    iso = "ISO 21448:2022"
    return {
        "iso31": _src(f"{iso} 3.1, p. 2 (acceptance criterion)", ok),
        "iso333": _src(f"{iso} 3.33 and Note 3, p. 10 (validation target; more than one can be needed)", ok),
        "iso422": _src(f"{iso} 4.2.2, pp. 12-14 (known/unknown, hazardous/non-hazardous scenario areas)", ok),
        "iso52": _src(f"{iso} 5.2 (specification of the functionality)", nc),
        "iso63": _src(f"{iso} 6.3 (hazard identification)", nc),
        "iso64": _src(f"{iso} 6.4 (risk evaluation)", nc),
        "iso65": _src(f"{iso} 6.5, pp. 30-31 (acceptance criteria per hazardous behaviour; positive risk "
                      "balance among the rationales)", ok),
        "iso_c21_hb": _src(f"{iso} C.2.1, p. 126 (each HB linked to its own criterion; A_H with a safety margin)", ok),
        "iso_c21": _src(f"{iso} C.2.1, Formulas (C.1)-(C.2), pp. 126-127", ok),
        "iso_c21_notes": _src(f"{iso} C.2.1 Notes 4-5, p. 127 (consistency with the ISO 26262 HARA; independence "
                              "simplification)", ok),
        "putze_cond": _src("Putze et al. 2023, arXiv:2304.10170, Sec. IV-B(b) (conditioning caveat)", ok),
        "iso_c3": _src(f"{iso} C.3, Formula (C.7), p. 137", ok),
        "lw97": _src("Littlewood & Wright 1997, IEEE TSE 23(11):673-683", ok),
        "kp16": _src("Kalra & Paddock 2016, RAND RR-1478, Eq. 2", ok),
        "menzel": _src("Menzel, Bagschik & Maurer 2018, IEEE IV, arXiv:1801.08598 (functional, logical, concrete "
                       "scenarios)", nc),
        "iso73": _src(f"{iso} 7.3 (analysis of potential functional insufficiencies and triggering conditions)", nc),
        "iso74": _src(f"{iso} 7.4 (acceptability of the system's response to the triggering conditions)", nc),
        "iso_c5": _src(f"{iso} C.5, pp. 146-151 (parameter distributions; importance sampling biased to riskier "
                       "areas)", ok),
        "iso91": _src(f"{iso} 9.1 a)-b), p. 42 (V&V strategy includes validation targets)", ok),
        "iso93": _src(f"{iso} 9.3 (specification of integration and testing)", nc),
        "iso94": _src(f"{iso} 9.4 (work products of Clause 9)", nc),
        "iso_c632": _src(f"{iso} C.6.3.2 Example 1, p. 156 (joint confidence)", ok),
        "dunn": _src("Dunn 1961, JASA 56:52-64 (Bonferroni)", nc),
        "garwood": _src("Garwood 1936, Biometrika 28:437-442, Sec. 4, p. 441 (Poisson limits via chi-square); Porter 2025, arXiv:2509.02852, Sec. 5 Eq. 34, Sec. 6.1 Eq. 38", ok),
        "iso111": _src(f"{iso} 11.1, p. 50 (unknown scenarios: residual risk meets the acceptance criteria with "
                       "sufficient confidence)", ok),
        "warg": _src("Warg et al. 2020, Quantitative Risk Norm, Sec. III-B (budgets add up)", nc),
        "hofmeister": _src("Hofmeister & Kinalzyk (AVL), thematic paper ca. 2023, Sec. 2.2 (split budgets to avoid "
                           "concentrating residual risk; scenario-class criteria add up to the hazard-based "
                           "criterion; one validation target per scenario class)", nc),
        "hofmeister_behav": _src("Hofmeister & Kinalzyk (AVL), thematic paper ca. 2023 (behavioural pass/fail "
                                 "criteria of test cases next to the statistical criteria)", nc),
        "reserve_choice": _src("reserve fraction is a choice", dc),
        "rule_ep": _src("equal-protection rule a_k = A' lambda_k^U / sum_j lambda_j^U (one chain: b_k = B lambda_k^U / "
                         "sum_j lambda_j^U)", dc),
        "rule_ph": _src("proportional-to-human rule a_k = A' s_k (one chain: b_k = B s_k)", dc),
        "rule_eq": _src("equal split a_k = A' / K (one chain: b_k = B / K), for comparison", dc),
        "rule_fixed": _src("fixed rule a_k = A' fixed_share_k (shares given in the input)", dc),
        "caps": _src("human caps with clamp-and-redistribute", dc),
        "pstar": _src("allowed failure probability p* = b / lambda^U", dc),
        "owen": _src("Owen 2013, Monte Carlo theory, methods and examples, Ch. 9 (importance sampling)", ok),
        "wmax": _src("w_max inside the zero-failure bound", dc),
        "iso_c1": _src(f"{iso} C.1, p. 125 (simulation accuracy is part of the safety argument)", ok),
        "casella": _src("Casella & Berger 2002, Statistical Inference, Thm 5.3.1", nc),
        "margin": _src("margin delta = mu + z sigma^U and adding Phi(-z) to the failure bound", dc),
        "iso107": _src(f"{iso} 10.7, pp. 49-50 (evaluation of the residual risk due to known hazardous "
                       "scenarios)", ok),
        "iso_t11": _src(f"{iso} 11.3, Table 11, p. 51 (fleet test, random scenario simulation among the "
                        "methods)", ok),
        "putze_sum": _src("Putze et al. 2023, arXiv:2304.10170, Sec. IV-B(b), Eq. (2) (sum of upper bounds)", ok),
        "good": _src("Good 1953, Biometrika 40:237-264 (Good-Turing)", nc),
        "bk": _src("Berend & Kontorovich 2013, arXiv:1210.3248, Theorem 1", ok),
        "unknown_ext": _src("Poisson bound with N1 > 0 for unknown scenarios", dc),
        "iso833": _src(f"{iso} 8.3.3 (functional restrictions)", nc),
        "iso123c": _src(f"{iso} 12.3 c), p. 54 (coverage of known scenarios and argument for unknown ones)", ok),
        "iso124": _src(f"{iso} 12.4 (recommendation for SOTIF release)", nc),
        "iso131": _src(f"{iso} 13.1, p. 55 (field monitoring process defined before release)", ok),
        "iso133": _src(f"{iso} 13.3, pp. 56-57 (topics for observation: on-board monitoring, near-triggering "
                       "events)", ok),
        "iso134": _src(f"{iso} 13.4 (SOTIF issue evaluation and resolution process)", nc),
        "garwood_lower": _src("Garwood 1936, Biometrika 28:437-442 (lower Poisson limit)", nc),
        "monitor": _src("monitoring threshold k_min and the reserve rule for field events", dc),
        "sens": _src("what-if sensitivity on failure counts", dc),
        "iso_wp": _src(f"{iso} 6.6, 7.5, 9.4, 10.8, 11.4, 12.5, 13.5 (contents of the work-product subclauses)", nc),
        "putze_full": _src("Putze et al. 2023, arXiv:2304.10170, Sec. IV-B(b) (full conditioning: harm chain per "
                           "logical scenario)", ok),
        "harm_units": _src("budget and release claim in harm units, equal harm probability per encounter", dc),
        "wang": _src("Wang 2022, NHTSA DOT HS 813 219, Table 1-1 (logistic injury-risk curves by delta-V)", nc),
        "kroeger": _src("Kroeger 2025, How safe should automated vehicles be?, Next Research 2:100238 (about 3e-9 "
                        "fatalities/h and 4e-8 fatalities or serious injuries/h for automated vehicles)", nc),
        "werling": _src("Werling, Faller, Betz & Straub 2025, arXiv:2503.20544, Sec. 3.3, Remark 3.7 (budgets fixed "
                        "before the confirmatory campaign, moved only between campaigns)", nc),
        "patel": _src("Patel & Jung 2026, arXiv:2610.35092, Sec. 3.5 (independent evidence units; evidence per "
                      "triggering condition)", nc),
        "betschinske": _src("Betschinske et al. 2025, arXiv:2506.10363, Sec. VII (no efficiency method fully "
                            "replaces field testing)", ok),
        "zhao": _src("Zhao et al. 2017, IEEE T-ITS 18(3):595-607 (importance sampling for accelerated evaluation)", ok),
        "explore": _src("Feng et al. 2023, Nature 615:620-627 and Moss et al. 2023, Bayesian safety validation "
                        "(scenario exploration; checked at abstract level)", ok),
        "ramdas": _src("Ramdas, Gruenwald, Vovk & Shafer 2023, Statistical Science 38(4), arXiv:2210.01948 "
                       "(anytime-valid inference, e-processes, Ville's inequality; checked at abstract level)", ok),
        "wald": _src("Wald 1945, sequential probability ratio test", nc),
        "eproc": _src("Poisson likelihood-ratio e-process for field monitoring and its alarm count", dc),
        "input": "input",
    }


def _f(x: Optional[float], sig: int = 4) -> str:
    """Compact number format for the report."""
    if x is None:
        return "-"
    if isinstance(x, (bool, np.bool_)):
        return "yes" if x else "no"
    x = float(x)
    if math.isinf(x):
        return "inf"
    if x == 0:
        return "0"
    ax = abs(x)
    if 1e-3 <= ax < 1e5:
        return f"{x:.{sig}g}"
    return f"{x:.{sig - 1}e}"


def _int(x: float) -> str:
    return f"{x:,.0f}"


def _sci(x: float) -> str:
    """Short scientific format, e.g. 3e-9."""
    m, e = f"{x:.0e}".split("e")
    return f"{m}e{int(e)}"


def _pct(x: float, d: int = 2) -> str:
    return f"{100 * x:.{d}f} %"


def _cap(x: float) -> str:
    return "-" if math.isinf(x) else f"{x:.3g}"


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]], align: str = "", indent: int = 4) -> str:
    """Plain-text table. `align` holds one 'l' or 'r' per column (default: all left)."""
    al = (align or "").ljust(len(headers), "l")
    cells = [[str(c) for c in r] for r in rows]
    widths = [max([len(h)] + [len(r[i]) for r in cells]) for i, h in enumerate(headers)]

    def fmt(r: Sequence[str]) -> str:
        parts = [c.rjust(wd) if a == "r" else c.ljust(wd) for c, wd, a in zip(r, widths, al)]
        return (" " * indent + "  ".join(parts)).rstrip()

    return "\n".join([fmt(list(headers))] + [fmt(r) for r in cells])


def build_sections(inputs: WorkbookInputs, res: ChainResults) -> list[Section]:
    """Assemble the report sections and the export rows (one Quantity per number)."""
    S = _source_catalogue()
    ids = inputs.ls_ids
    scen = inputs.logical_scenarios
    he, hb = res.hazards.selected, res.hazards.selected_hb
    sections: list[Section] = []

    def q(sec: Section, name: str, symbol: str, value: float, unit: str, *srcs: str, show: bool = True) -> None:
        sec.quantities.append(Quantity(name, symbol, float(value), unit, f"{sec.step} {sec.title}",
                                       "; ".join(srcs) if srcs else "input", show))

    # Cl. 5 / 6.3 ------------------------------------------------------------------------------------
    hz = res.hazards
    s = Section("Cl. 5 / 6.3", "Function and hazard identification (record)", [
        "S_c = sum of share_of_harm_class_budget over the listed hazardous events of harm class c;  S_c <= 1"])
    q(s, "hazardous_behaviours", "#HB", len(inputs.hazardous_behaviours), "count", S["iso63"])
    q(s, "hazardous_events", "#HE", len(inputs.hazardous_events), "count", S["iso63"])
    for c, v in hz.share_sums.items():
        q(s, f"share_sum[{c}]", f"S[{c}]", v, "-", S["iso63"], S["warg"], show=False)
    lines = [f"  Function (Cl. 5): {inputs.function}", "",
             "  Hazardous behaviours (vehicle level, no situation named):",
             _table(["id", "HEs listed", "description"],
                    [[h.id, hz.he_count[h.id], h.description] for h in inputs.hazardous_behaviours], "lrl"),
             "", "  Hazardous events (one behaviour in one operational situation):",
             _table(["id", "HB", "harm class", "S", "C", "share", "operational situation"],
                    [[e.id, e.hb_id, e.harm_class, e.severity or "-", e.controllability or "-",
                      f"{e.share_of_harm_class_budget:.2f}",
                      e.operational_situation + ("   <- selected" if e.id == he.id else "")]
                     for e in inputs.hazardous_events], "lllllrl"),
             "", "  Shares of each harm-class budget used by the listed hazardous events:",
             _table(["harm class", "sum of shares S_c", "not assigned in this file"],
                    [[c, f"{v:.2f}", f"{max(0.0, 1.0 - v):.2f}"] for c, v in hz.share_sums.items()], "lrr")]
    s.tables.append("\n".join(lines))
    s.sources += [S["iso52"], S["iso65"], S["iso_c21_hb"]]
    s.notes.append(f"Selected: {he.id}, i.e. {hb.id} ({hb.description}) in the operational situation "
                   f"'{he.operational_situation}'; harm class {he.harm_class!r}, share "
                   f"{he.share_of_harm_class_budget:g} of its budget. Each other hazardous event needs its own run of "
                   "this workbook with its own harm class, benchmark and share.")
    s.notes += hz.warnings
    if hz.hb_without_he:
        s.notes.append("Hazardous behaviours without a hazardous event in this file: " + ", ".join(hz.hb_without_he)
                       + ". Their events are analysed elsewhere; their shares of each harm class count against "
                         "the unassigned part above.")
    sections.append(s)

    # Cl. 6.4 ----------------------------------------------------------------------------------------
    rk = res.risk
    s = Section("Cl. 6.4", f"Risk evaluation: harm chain of {he.id}", [
        "G = P_chain = P(E|HB) x P(not C|E) x P(S|not C)  (one occurrence of the HB in this event causes the harm)",
        "optional per LS: G_k = P_E,k x P_C,k x P_S,k (default: the common factors); "
        "P_S,k from a curve = 1 / (1 + exp(-(beta0 + beta1 x impact speed)))"])
    q(s, "P_E", "P(E|HB)", rk.P_E, "-", "input")
    q(s, "P_C", "P(notC|E)", rk.P_C, "-", "input")
    q(s, "P_S", "P(S|notC)", rk.P_S, "-", "input")
    q(s, "P_chain", "G", rk.P_chain, "-", S["iso_c21"], S["putze_cond"])
    for k, i in enumerate(ids):
        src_k = S["putze_full"] if rk.G_k[k] != rk.P_chain else S["iso_c21"]
        q(s, f"P_S[{i}]", f"P_S,{k + 1}", rk.P_S_k[k], "-",
          S["wang"] if rk.P_S_from[k] == "curve" else ("input" if rk.P_S_from[k] == "input" else S["iso_c21"]),
          show=False)
        q(s, f"G[{i}]", f"G_{k + 1}", rk.G_k[k], "-", src_k, show=False)
    q(s, "G_unknown", "G_unk", rk.G_unk, "-", "input" if inputs.unknown.G_unknown is not None else S["iso_c21"])
    q(s, "per_ls_chain", "per-LS chains", float(rk.per_ls), "bool", S["putze_full"])
    rows = [[i, f"{rk.P_E_k[k]:g}", f"{rk.P_C_k[k]:g}", f"{rk.P_S_k[k]:.4g}", rk.P_S_from[k], f"{rk.G_k[k]:.4g}"]
            for k, i in enumerate(ids)]
    rows.append(["unknown", "", "", "", "input" if inputs.unknown.G_unknown is not None else "common",
                 f"{rk.G_unk:.4g}"])
    s.tables.append(_table(["LS", "P_E,k", "P_C,k", "P_S,k", "P_S from", "G_k"], rows, "lrrrlr"))
    s.sources += [S["iso64"], S["iso_c21_notes"], S["putze_full"]]
    s.notes.append(f"The HARA rates {he.id} with severity {he.severity or '-'} and controllability "
                   f"{he.controllability or '-'}. These are classes; the quantitative chain needs probabilities, "
                   f"so here they become P(not C|E) = {rk.P_C:g} and P(S|not C) = {rk.P_S:g}. Both must be "
                   "consistent with the ratings (C.2.1 Note 4).")
    s.notes.append("The product treats the links as independent of how the behaviour happened (C.2.1 Note 5); "
                   "strictly each factor is conditional on everything before it (a fast failure to yield injures "
                   "more than a slow one).")
    if rk.per_ls:
        s.notes.append("Per-LS chains are used (full conditioning, Putze et al. 2023): the budget (9.3 (d)) and the "
                       "release claim (Cl. 12) are kept in harm units. Unknown scenarios use G_unk = "
                       f"{rk.G_unk:.4g}; the largest G_k ({float(rk.G_k.max()):.4g}) would be the conservative choice.")
    else:
        s.notes.append("No logical scenario overrides the chain, so one chain G holds for all of them and the budget "
                       "and release claim take the R_HB form. Per-LS P_E, P_C, P_S (or a severity curve) are "
                       "optional inputs.")
    if any(f == "curve" for f in rk.P_S_from):
        s.sources.append(S["wang"])
        s.notes.append("P_S from an injury-risk curve for: " + ", ".join(
            f"{sc.id} (beta0 = {sc.severity_curve.beta0:g}, beta1 = {sc.severity_curve.beta1:g}, impact speed "
            f"{sc.severity_curve.impact_speed:g})" for sc in scen if sc.severity_curve is not None)
            + ". The curve must fit the harm class: Wang 2022 gives occupant curves by delta-V; a pedestrian harm "
              "class needs a pedestrian impact-speed curve.")
    sections.append(s)

    # Cl. 6.5 ----------------------------------------------------------------------------------------
    cr = res.crit
    bm = inputs.benchmark
    bl = bm.label
    s = Section("Cl. 6.5", f"Acceptance criterion for {he.id} (harm class: {he.harm_class})", [
        "h = events / exposure hours  (human harm events per hour of driving)" if bm.exposure_hours is not None
        else "h = events / (miles / average speed)  (human harm events per hour of driving)",
        f"A_H = share of the harm-class budget ({he.id}) x margin factor x h",
        "optionally rounded to the nearest multiple of round_A_H_to"])
    q(s, "events", "events", bm.events, "count", bl)
    if bm.exposure_hours is not None:
        q(s, "exposure_hours", "T_human", bm.exposure_hours, "h", bl)
    else:
        q(s, "miles", "miles", bm.miles, "mi", bl)
        q(s, "average_speed_mph", "v_avg", bm.average_speed_mph, "mi/h", bl)
        q(s, "exposure_hours", "miles/v_avg", bm.hours, "h", bl)
        q(s, "h_per_mile", "h_mi", cr.h_per_mile, "1/mi", bl)
    q(s, "h", "h", cr.h, "1/h", bl)
    q(s, "margin_factor", "margin", cr.margin, "-", "input")
    q(s, "share_of_harm_class_budget", "share", cr.share, "-", f"input (hazardous event {he.id})")
    q(s, "harm_class_budget", "margin x h", cr.margin * cr.h, "1/h", S["iso65"])
    q(s, "A_H_raw", "A_H,raw", cr.A_H_raw, "1/h", S["iso31"], S["iso65"], S["iso_c21_hb"])
    q(s, "A_H", "A_H", cr.A_H, "1/h", S["iso31"], S["iso65"], S["iso_c21_hb"])
    q(s, "kroeger_fatal_or_serious_per_h", "FSI target", KROEGER_FATAL_OR_SERIOUS_PER_H, "1/h", S["kroeger"])
    q(s, "kroeger_fatalities_per_h", "fatality target", KROEGER_FATALITIES_PER_H, "1/h", S["kroeger"])
    ratio_k = cr.margin * cr.h / KROEGER_FATAL_OR_SERIOUS_PER_H
    q(s, "class_budget_over_fsi", "(margin x h)/FSI", ratio_k, "-", S["kroeger"])
    s.notes.append(f"Benchmark (harm class {bm.harm_class}, label '{bl}'): {bm.source_note or 'no source note given'}")
    if bm.exposure_hours is None:
        s.notes.append(f"h_per_mile x 1e6 = {cr.h_per_mile * 1e6:.3f} human harm events per million miles; the "
                       "average speed converts miles to hours and scales h one to one, so it needs its own source.")
    if inputs.criterion.round_A_H_to is not None:
        s.notes.append(f"A_H rounded to a multiple of {_f(inputs.criterion.round_A_H_to)} /h "
                       f"({_f(cr.A_H_raw)} -> {_f(cr.A_H)}).")
        if cr.rounding_increased:
            s.notes.append("WARNING: rounding made A_H larger than computed, i.e. the criterion less strict.")
    else:
        s.notes.append("A_H is not rounded (round_A_H_to = null).")
    s.notes.append(f"Plausibility: Kroeger (2025) proposes about {_sci(KROEGER_FATALITIES_PER_H)} fatalities/h and "
                   f"{_sci(KROEGER_FATAL_OR_SERIOUS_PER_H)} fatalities or serious injuries/h for automated vehicles "
                   f"[location not checked]. Those targets cover all harm to all road users; the harm-class budget "
                   f"margin x h = {cr.margin * cr.h:.2e} /h covers every {he.harm_class} of any severity. It is "
                   f"{ratio_k:.3g} x the serious-injury target, so it fits that target only if fewer than 1 in "
                   f"{ratio_k:.3g} of these injuries is serious or fatal, before the other harm classes are counted "
                   f"(A_H alone is {cr.A_H / KROEGER_FATAL_OR_SERIOUS_PER_H:.3g} x). Check the severity mix of the "
                   "benchmark before relying on the margin.")
    sections.append(s)

    # Annex C.2.1 ------------------------------------------------------------------------------------
    s = Section("Annex C.2.1", "Tolerable behaviour rate", ["R_HB = A_H / (P(E|HB) x P(not C|E) x P(S|not C))"])
    q(s, "R_HB", "R_HB", res.tol.R_HB, "1/h", S["iso_c21"], S["putze_cond"])
    s.notes.append(f"In words: {hb.id} may occur in {he.id} at most once per {_int(1 / res.tol.R_HB)} hours of "
                   "driving.")
    sections.append(s)

    # Annex C.3 --------------------------------------------------------------------------------------
    nv = res.naive
    s = Section("Annex C.3", "Naive validation target (for scale)", [
        "tau_naive = ln(1/(1-C)) / R_HB  (zero events observed)",
        "fleet days = tau_naive / (cars x hours per day per car); years = days / 365.25"])
    q(s, "C", "C", inputs.confidence.C, "-", "input")
    q(s, "ln_1_over_1mC", "ln(1/(1-C))", nv.L_single, "-", S["iso_c3"])
    q(s, "tau_naive_h", "tau_naive", nv.tau_h, "h", S["iso_c3"], S["lw97"], S["kp16"])
    q(s, "fleet_hours_per_day", "fleet h/day", nv.fleet_hours_per_day, "h/day", "input")
    q(s, "tau_naive_fleet_days", "days", nv.fleet_days, "day", S["iso_c3"])
    q(s, "tau_naive_fleet_years", "years", nv.fleet_years, "yr", S["iso_c3"])
    s.notes.append(f"For comparison, the planned driving: pilot {_int(inputs.driving.pilot_hours)} h "
                   f"({_f(nv.pilot_fleet_days)} fleet days), confirmatory {_int(inputs.driving.confirmatory_hours)} h "
                   f"({_f(nv.conf_fleet_days)} fleet days). Clause 12 does not use tau_naive.")
    sections.append(s)

    # Cl. 7.3 ----------------------------------------------------------------------------------------
    tr = res.tcs
    s = Section("Cl. 7.3", "Logical scenarios and triggering conditions (record)", [
        f"functional scenario = operational situation of {he.id}; logical scenario = its parameter ranges; "
        "concrete scenario = one parameter value",
        "triggering condition = region of the parameter space inside one or more logical scenarios (no budget)"])
    q(s, "logical_scenarios", "K", inputs.K, "count", "input")
    q(s, "triggering_conditions", "#TC", len(inputs.triggering_conditions), "count", S["iso73"])
    lines = [f"  Logical scenarios of {he.id} ({he.operational_situation}):"]
    for sc in scen:
        lines.append(f"    {sc.id}  {sc.name}")
        if sc.parameters:
            lines.append(f"          parameters: {sc.parameters}")
        if sc.description:
            lines.append(f"          {sc.description}")
    lines += ["", "  Triggering conditions (regions inside the logical scenarios):"]
    for t in inputs.triggering_conditions:
        lines.append(f"    {t.id}  {t.description}")
        where = "all logical scenarios" if t.applies_to_all else ", ".join(t.logical_scenarios)
        lines.append(f"          region: {t.parameter_region or '-'};  lies in: {where}")
    if inputs.triggering_conditions:
        lines += ["", "  TC x LS matrix (x = the triggering condition is a region inside the logical scenario):",
                  _table(["TC"] + ids, [[t.id] + ["x" if tr.matrix[i, k] else "." for k in range(inputs.K)]
                                        for i, t in enumerate(inputs.triggering_conditions)], "l" + "c" * inputs.K)]
    s.tables.append("\n".join(lines))
    s.sources += [S["menzel"], S["iso74"], S["iso_c5"]]
    s.notes.append("Triggering conditions are not budget holders: an encounter with several of them present "
                   "(a child at night on a wet road) is counted once, in its logical scenario. They define the "
                   "targeted cases (Cl. 10) and bias the importance sampling (Annex C.5).")
    s.notes.append("7.4 (acceptability of the system's response to the triggering conditions) is estimated by the "
                   "Clause 10 targeted cases and, statistically, by the failure bounds of Clause 11.")
    if tr.ls_without_tc:
        s.notes.append("Logical scenarios without a triggering condition: " + ", ".join(tr.ls_without_tc)
                       + ". Check whether the analysis of 7.3 is complete for them.")
    sections.append(s)

    # Cl. 9.3 (a) ------------------------------------------------------------------------------------
    j = res.joint
    s = Section("Cl. 9.3 (a)", "Joint confidence", [
        f"m = 2K + 2 = {j.m_default} (K exposure, K failure, 1 unknown-scenario, 1 simulator-spread bound)"
        + ("" if inputs.confidence.m_bounds is None else f"; overridden to m = {j.m}"),
        "C_b = 1 - (1 - C)/m;  L = ln(1/(1 - C_b));  F(j) = chi2_{C_b}(2j + 2)/2"])
    q(s, "K", "K", inputs.K, "-", "input")
    q(s, "m", "m", j.m, "-", S["iso_c632"], S["dunn"])
    q(s, "C_b", "C_b", j.C_b, "-", S["iso_c632"], S["dunn"])
    q(s, "L", "L", j.L, "-", S["iso_c3"])
    lines = ["  Zero-failure factor L for several m (C = %s):" % _f(inputs.confidence.C),
             _table(["m", "C_b", "L", "L / ln(1/(1-C))", ""],
                    [[mm, f"{cb:.6f}", f"{LL:.4f}", f"{LL / nv.L_single:.3f}", "<- used" if mm == j.m else ""]
                     for mm, cb, LL in j.L_table], "rrrrl"),
             "  j-failure factor F(j) at C_b (F(0) = L):",
             _table(["j", "F(j)", "F(j)/L"], [[jj, f"{FF:.4f}", f"{FF / j.L:.3f}"] for jj, FF in j.F_table], "rrr")]
    s.tables.append("\n".join(lines))
    s.sources += [S["iso91"], S["iso93"]]
    if j.m < j.m_default:
        s.notes.append(f"WARNING: m = {j.m} is smaller than 2K + 2 = {j.m_default}. The joint confidence C holds "
                       "only if fewer bounds enter the final claim.")
    sections.append(s)

    # Cl. 9.3 (b) ------------------------------------------------------------------------------------
    e = res.expo
    s = Section("Cl. 9.3 (b)", "Exposure per logical scenario (pilot driving)", [
        "lambda_k^U = chi2_{C_b}(2 N_k + 2) / (2 tau_pilot)   (one-sided Poisson upper bound)"])
    q(s, "tau_pilot", "tau_pilot", inputs.driving.pilot_hours, "h", "input")
    for k, i in enumerate(ids):
        q(s, f"N_pilot[{i}]", f"N_{k + 1},pilot", e.N[k], "count", "input", show=False)
        q(s, f"lambda_U_pilot[{i}]", f"lambda_{k + 1}^U", e.lambda_U[k], "1/h", S["garwood"], S["iso_c632"], show=False)
    s.tables.append(_table(["LS", "N_pilot", "N/tau [1/h]", "lambda^U [1/h]", "name"],
                           [[i, f"{e.N[k]:,d}", f"{e.point[k]:.4g}", f"{e.lambda_U[k]:.5g}", scen[k].name]
                            for k, i in enumerate(ids)], "lrrrl"))
    s.notes.append("Planning values only; Clause 11 recomputes the exposure from the confirmatory driving.")
    sections.append(s)

    # Cl. 9.3 (c) ------------------------------------------------------------------------------------
    rv = res.reserve
    s = Section("Cl. 9.3 (c)", "Reserve for unknown scenarios (Cl. 11) and budget for the logical scenarios",
                ["b_unk = reserve fraction x R_HB;  B = R_HB - b_unk",
                 "in harm units: reserve f x A_H;  A' = (1 - f) x A_H  (= G x B)"])
    q(s, "reserve_fraction", "f", inputs.budget.reserve_fraction, "-", "input")
    q(s, "b_unk", "b_unk", rv.b_unk, "1/h", S["iso422"], S["iso111"], S["reserve_choice"])
    q(s, "B", "B", rv.B, "1/h", S["iso111"], S["warg"])
    q(s, "reserve_harm", "f x A_H", rv.reserve_harm, "1/h", S["iso111"], S["harm_units"])
    q(s, "A_prime", "A'", rv.A_prime, "1/h", S["iso111"], S["harm_units"])
    sections.append(s)

    # Cl. 9.3 (d) ------------------------------------------------------------------------------------
    al, u = res.alloc, res.alloc.used
    rule_src = {"equal_protection": S["rule_ep"], "proportional_to_human": S["rule_ph"],
                "equal_split": S["rule_eq"], "fixed": S["rule_fixed"]}
    s = Section("Cl. 9.3 (d)", f"Budget per logical scenario (safety rule: {al.rule})", [
        "harm budget a_k per LS, behaviour budget b_k = a_k / G_k  (one common chain: b_k = B x a_k / A')",
        "equal_protection (default): a_k = A' x lambda_k^U / sum_j lambda_j^U  ->  p_k* G_k = A' / sum_j lambda_j^U "
        "in every LS (one chain: p_k* = B / sum_j lambda_j^U)",
        "proportional_to_human: a_k = A' x s_k  (same improvement factor over human drivers in every LS)",
        "equal_split (comparison only): a_k = A' / K;  fixed: a_k = A' x fixed_share_k",
        "human cap: b_k <= h_k (a_k <= h_k G_k); a budget above its cap is set to the cap and the rest re-allocated "
        "to the uncapped LS in proportion to the rule's weights, until stable"])
    for k, i in enumerate(ids):
        q(s, f"weight[{i}]", f"v_{k + 1}", u.weights[k], "-" if al.rule != "equal_protection" else "1/h",
          rule_src[al.rule], show=False)
        q(s, f"harm_budget[{i}]", f"a_{k + 1}", u.harm[k], "1/h", rule_src[al.rule], S["caps"], S["harm_units"],
          show=False)
        q(s, f"b[{i}]", f"b_{k + 1}", u.b[k], "1/h", rule_src[al.rule], S["caps"], S["hofmeister"], show=False)
        q(s, f"share[{i}]", f"a_{k + 1}/A'", u.share[k], "-", rule_src[al.rule], S["caps"], show=False)
        if not math.isinf(al.caps[k]):
            q(s, f"human_cap[{i}]", f"h_{k + 1}", al.caps[k], "1/h", "input", show=False)
        q(s, f"cap_binds[{i}]", f"cap_{k + 1} binds", float(u.clamped[k]), "bool", S["caps"], show=False)
    q(s, "caps_binding", "#caps binding", int(u.clamped.sum()), "count", S["caps"])
    q(s, "unallocated", "(A' - sum a_k)/G", u.unallocated, "1/h", S["caps"])
    wh = "weight v_k [1/h]" if al.rule == "equal_protection" else "weight v_k"
    lines = [f"  Budgets under the rule used ({al.rule}):",
             _table(["LS", wh, "G_k", "a_k [1/h]", "b_k [1/h]", "share", "human cap h_k [1/h]", "cap binds"],
                    [[i, f"{u.weights[k]:.5g}", f"{al.G_k[k]:.4g}", f"{u.harm[k]:.4e}", f"{u.b[k]:.4e}",
                      _pct(u.share[k]), _cap(al.caps[k]), _f(bool(u.clamped[k]))] for k, i in enumerate(ids)],
                    "lrrrrrrl"),
             "", "  Comparison of the budget rules (each followed by the human-cap step; p* = b/lambda^U; "
                 "n = L w / p*; share = a_k / A'):"]
    rows = []
    for r in ALLOCATION_RULES:
        oc = al.comparison[r]
        if oc is None:
            continue
        for k, i in enumerate(ids):
            rows.append([(r + (" (used)" if r == al.rule else "")) if k == 0 else "", i, _pct(oc.share[k]),
                         f"{oc.targets.p_star[k]:.4e}", _int(oc.targets.one_in[k]), f"{oc.targets.n[k]:,.1f}",
                         _f(bool(oc.clamped[k]))])
            q(s, f"compare_share[{r}][{i}]", f"a_{k + 1}/A' ({r})", oc.share[k], "-", rule_src[r], S["caps"],
              show=False)
            q(s, f"compare_p_star[{r}][{i}]", f"p_{k + 1}* ({r})", oc.targets.p_star[k], "-", rule_src[r],
              S["pstar"], show=False)
            q(s, f"compare_n[{r}][{i}]", f"n_{k + 1} ({r})", oc.targets.n[k], "runs", rule_src[r], S["iso_c3"],
              show=False)
        q(s, f"compare_n_total[{r}]", f"sum n_k ({r})", oc.targets.n_total, "runs", rule_src[r], show=False)
        q(s, f"compare_protection_ratio[{r}]", f"protection ratio ({r})", oc.targets.protection_ratio, "-",
          rule_src[r], show=False)
        q(s, f"compare_caps_binding[{r}]", f"#caps binding ({r})", int(oc.clamped.sum()), "count", S["caps"],
          show=False)
    lines.append(_table(["rule", "LS", "share", "p_k*", "1 in ...", "n_k [runs]", "cap binds"], rows, "llrrrrl"))
    lines += ["", _table(["rule", "total runs", "protection ratio max(p*G)/min(p*G)", "caps binding"],
                         [[r, f"{oc.targets.n_total:,.1f}", f"{oc.targets.protection_ratio:.3f}", int(oc.clamped.sum())]
                          if (oc := al.comparison[r]) is not None else
                          [r, "not applicable", f"(no {'human_share' if r == 'proportional_to_human' else 'fixed_share'} "
                              "given)", ""]
                          for r in ALLOCATION_RULES], "lrrr")]
    s.tables.append("\n".join(lines))
    s.sources += [S["warg"], S["werling"], S["iso333"]] + ([S["putze_full"]] if res.risk.per_ls else [])
    s.notes.append("Why the split is a safety rule and not a cost rule: the budget decides how much risk the road "
                   "users in each logical scenario carry and fixes the validation targets. Letting test cost or "
                   "test effort decide it would accept more risk exactly where testing is harder. Cost may decide "
                   "how evidence is produced, never how much risk is accepted.")
    s.notes.append("Budgets are frozen: the shares are fixed before the confirmatory campaign and may only move "
                   "between campaigns, with fresh evidence (Werling et al. 2025, Sec. 3.3, Remark 3.7). Moving them "
                   "after the confirmatory data are in would let the data choose the budget they are judged against.")
    if al.rule == "equal_protection" and not res.risk.per_ls:
        s.notes.append("Equal protection: every logical scenario has the same allowed failure probability per "
                       f"encounter, 1 in {_int(res.targets.one_in[0])}. The protection ratio of the other rules "
                       "shows how unequal they would be.")
    elif al.rule == "equal_protection":
        s.notes.append("Equal protection with per-LS chains: every logical scenario has the same harm probability "
                       f"per encounter, p_k* G_k = {res.targets.harm_per_encounter[0]:.4e}; p_k* itself is larger "
                       "where G_k is smaller, by exactly G / G_k.")
    if not res.risk.per_ls:
        s.notes.append("One harm chain is used for the whole hazardous event, so a_k = G b_k and equal harm per "
                       "encounter is equal p_k*. With per-LS chains (Cl. 6.4, Putze et al. 2023) the same rule "
                       "equalises p_k* G_k instead: b_k = A' lambda_k^U / (G_k sum_j lambda_j^U).")
    if u.clamped.any():
        s.notes.append("Human caps bind for: " + ", ".join(i for i, c in zip(ids, u.clamped) if c)
                       + f" (clamp-and-redistribute passes: {u.passes}). Their allowed failure probability is lower "
                         "than under the rule alone; the others receive the remainder.")
    else:
        s.notes.append("No human cap binds under the rule used.")
    if u.unallocated_harm > 1e-15 * rv.A_prime:
        s.notes.append(f"WARNING: all logical scenarios are capped; {_f(u.unallocated_harm)} /h of the harm budget A' "
                       "is not allocated (it stays unused, which is conservative).")
    sections.append(s)

    # Cl. 9.3 (e) ------------------------------------------------------------------------------------
    t = res.targets
    s = Section("Cl. 9.3 (e)", "Allowed failure probability and zero-failure simulation runs", [
        "p_k* = b_k / lambda_k^U   (allowed failure probability per encounter)",
        "n_k = L x w_k / p_k* = L x w_k x lambda_k^U / b_k   (runs that must pass without failure)",
        "protection ratio = max_k (p_k* G_k) / min_k (p_k* G_k)   (= max p* / min p* with one chain)"])
    for k, i in enumerate(ids):
        q(s, f"importance_factor[{i}]", f"w_{k + 1}", scen[k].importance_factor, "-", "input", show=False)
        q(s, f"p_star[{i}]", f"p_{k + 1}*", t.p_star[k], "-", S["pstar"], show=False)
        q(s, f"one_in[{i}]", f"1/p_{k + 1}*", t.one_in[k], "encounters", S["pstar"], show=False)
        q(s, f"harm_per_encounter[{i}]", f"p_{k + 1}* G_{k + 1}", t.harm_per_encounter[k], "-", S["harm_units"],
          show=False)
        q(s, f"n[{i}]", f"n_{k + 1}", t.n[k], "runs", S["iso_c3"], S["iso_c5"], S["owen"], S["wmax"], show=False)
        q(s, f"n_ceil[{i}]", f"ceil(n_{k + 1})", t.n_ceil[k], "runs", S["iso_c3"], show=False)
    q(s, "n_total", "sum n_k", t.n_total, "runs", S["iso_c3"], S["iso_c5"], S["owen"], S["zhao"], S["wmax"])
    q(s, "protection_ratio", "max(p*G)/min(p*G)", t.protection_ratio, "-", S["pstar"])
    rows = [[i, f"{u.b[k]:.4e}", f"{res.expo.lambda_U[k]:.5g}", f"{t.p_star[k]:.4e}", _int(t.one_in[k]),
             f"{t.harm_per_encounter[k]:.4e}", f"{scen[k].importance_factor:g}", f"{t.n[k]:,.1f}", _int(t.n_ceil[k])]
            for k, i in enumerate(ids)]
    rows.append(["total", "", "", "", "", "", "", f"{t.n_total:,.1f}", _int(t.n_ceil.sum())])
    s.tables.append(_table(["LS", "b_k [1/h]", "lambda_k^U [1/h]", "p_k*", "1 in ...", "p_k* G_k", "w_k",
                            "n_k (exact)", "n_k (rounded up)"], rows, "lrrrrrrrr"))
    if al.rule == "equal_protection" and not res.risk.per_ls:
        s.notes.append("With equal protection n_k = L w_k sum_j lambda_j^U / B: the runs depend only on the sampling "
                       "efficiency w_k, not on how common the logical scenario is.")
    s.notes.append("Each run must be an independent concrete scenario (own parameter draw and seed); frames or slices "
                   "of one simulated scene are not separate trials (Patel & Jung 2026, Sec. 3.5).")
    s.sources += [S["patel"]]
    sections.append(s)

    # Cl. 9.3 (f) / Annex C.1 ------------------------------------------------------------------------
    sm = res.sim
    s = Section("Cl. 9.3 (f) / Annex C.1", "Simulator credibility", [
        "sigma^U = sigma_hat x sqrt((m_pairs - 1) / chi2_{1-C_b}(m_pairs - 1))",
        "delta = mu_hat + z x sigma^U;  miss probability Phi(-z)",
        "auto z: Phi(-z) = f x min_k p_k*  ->  z = norm.isf(f x min_k p_k*)"])
    sim_in = inputs.simulator
    q(s, "m_pairs", "m_pairs", sim_in.m_pairs, "count", "input")
    q(s, "mu_hat", "mu_hat", sim_in.mu_hat, "m", "input")
    q(s, "sigma_hat", "sigma_hat", sim_in.sigma_hat, "m", "input")
    q(s, "chi2_lower", "chi2_{1-C_b}(m-1)", sm.chi2_lower, "-", S["casella"])
    q(s, "sigma_U", "sigma^U", sm.sigma_U, "m", S["casella"], S["iso_c1"])
    q(s, "z", "z", sm.z, "-", S["margin"])
    q(s, "delta", "delta", sm.delta, "m", S["margin"], S["iso_c1"])
    q(s, "p_miss", "Phi(-z)", sm.p_miss, "-", S["margin"])
    q(s, "p_miss_over_min_p_star", "Phi(-z)/min p*", sm.p_miss_over_min_p_star, "-", S["margin"])
    other = "auto" if sm.z_mode == "fixed" else "fixed"
    oz, od, op_ = ((sm.z_auto, sm.delta_auto, sm.p_miss_auto) if other == "auto"
                   else (sm.z_fixed, sm.delta_fixed, sm.p_miss_fixed))
    q(s, f"z_{other}", f"z ({other})", oz, "-", S["margin"])
    q(s, f"delta_{other}", f"delta ({other})", od, "m", S["margin"])
    q(s, f"p_miss_{other}", f"Phi(-z) ({other})", op_, "-", S["margin"])
    s.notes.append(f"z mode used: {sm.z_mode}; Phi(-z) = {_pct(sm.p_miss_over_min_p_star, 3)} of the smallest p*. "
                   f"Alternative ({other}" + (f", f = {sim_in.z_auto_fraction:g}" if other == "auto" else "")
                   + f"): z = {oz:.4f}, delta = {od:.4f} m, Phi(-z) = {op_:.3e}.")
    s.notes.append(f"Standard error of mu_hat = {sm.se_mu:.4f} m (not included in delta; compare z x sigma^U = "
                   f"{sm.z * sm.sigma_U:.3f} m).")
    s.notes.append("A simulated run counts as a pass only if y_sim >= y_crit + delta.")
    sections.append(s)

    # Cl. 9.4 ----------------------------------------------------------------------------------------
    s = Section("Cl. 9.4", "Validation targets (work product)", [
        "several validation targets for one acceptance criterion (ISO 21448 3.33 Note 3)"])
    q(s, "validation_targets", "#VT", len(res.validation_targets), "count", S["iso333"], S["iso94"])
    q(s, "targeted_cases_planned", "sum cases_k", sum(sc.targeted_cases for sc in scen), "cases", "input")
    q(s, "tau_conf_fleet_days", "tau_conf / fleet h/day", inputs.driving.confirmatory_hours / nv.fleet_hours_per_day,
      "day", "input")
    s.tables.append(_table(["id", "validation target", "value", "unit", "evaluated in"],
                           [[vt.id, vt.what, _int(vt.value) if vt.unit in ("runs", "cases", "h", "pairs")
                             else _f(vt.value, 5), vt.unit, vt.evaluated_in] for vt in res.validation_targets],
                           "llrll"))
    s.sources += [S["iso91"], S["hofmeister"]]
    sections.append(s)

    # Cl. 10 -----------------------------------------------------------------------------------------
    kn = res.known
    s = Section("Cl. 10", "Evaluation of known scenarios (targeted cases)", [
        "pass_k = no targeted case of LS k failed (and LS k has cases if a triggering condition lies in it);  "
        "pass = all LS pass"])
    for k, i in enumerate(ids):
        q(s, f"targeted_cases[{i}]", f"cases_{k + 1}", kn.cases[k], "count", "input", show=False)
        q(s, f"targeted_failures[{i}]", f"failed_{k + 1}", kn.failures[k], "count", "input", show=False)
    q(s, "targeted_cases_total", "sum cases", kn.total_cases, "count", "input")
    q(s, "targeted_failures_total", "sum failed", kn.total_failures, "count", "input")
    q(s, "known_passed", "Cl. 10 passed", float(kn.passed), "bool", S["iso107"])
    s.tables.append(_table(["LS", "cases", "failed", "result", "triggering conditions", "case design"],
                           [[i, kn.cases[k], kn.failures[k], "pass" if kn.passed_per_ls[k] else "FAIL",
                             ", ".join(res.tcs.tcs_per_ls[k]) or "-", scen[k].targeted_case_design or "-"]
                            for k, i in enumerate(ids)], "lrrlll"))
    s.sources += [S["iso74"], S["hofmeister_behav"], S["patel"]]
    s.notes.append(f"Known-scenario evaluation: {'PASSED' if kn.passed else 'NOT PASSED'} "
                   f"({kn.total_cases - kn.total_failures} of {kn.total_cases} targeted cases passed).")
    s.notes.append("This is verification: it shows that the known triggering conditions are handled but gives no "
                   "failure rate, so it does not enter the sum of Clauses 11 and 12. Release needs it in addition.")
    s.notes.append("Evidence units (Patel & Jung 2026): a targeted case counts only as an independent concrete "
                   "scenario, not as frames or slices of one scene, and a pass under one triggering condition counts "
                   "for another only after a test under that other condition.")
    if kn.missing_cases:
        s.notes.append("WARNING: no targeted cases for " + ", ".join(kn.missing_cases) + " although triggering "
                       "conditions lie there; the evaluation is incomplete and counts as not passed.")
    sections.append(s)

    # Cl. 11 -----------------------------------------------------------------------------------------
    un = res.unknown
    rk = res.risk
    s = Section("Cl. 11", "Evaluation of unknown scenarios (upper bounds from fresh data)", [
        "lambda_k^U,conf = chi2_{C_b}(2 N_k,conf + 2) / (2 tau_conf)",
        "p_k^U = F(j_k) x w_k / n_k + Phi(-z);  F(j) = chi2_{C_b}(2j + 2)/2, F(0) = L;  n_k = runs executed "
        "(default: planned n_k, exact)",
        "lambda_new^U = chi2_{C_b}(2 N1 + 2) / (2 tau_disc)  (= L / tau_disc when N1 = 0);  "
        "unknown term = lambda_new^U x p_new",
        "harm term_k = term_k x G_k;  unknown harm = unknown term x G_unk"])
    q(s, "tau_conf", "tau_conf", inputs.driving.confirmatory_hours, "h", "input")
    q(s, "tau_disc", "tau_disc", inputs.driving.discovery_hours, "h", "input")
    for k, i in enumerate(ids):
        sc = scen[k]
        q(s, f"N_conf[{i}]", f"N_{k + 1},conf", sc.N_conf, "count", "input", show=False)
        q(s, f"lambda_U_conf[{i}]", f"lambda_{k + 1}^U,conf", un.lambda_U_conf[k], "1/h", S["garwood"], show=False)
        q(s, f"failures[{i}]", f"j_{k + 1}", sc.failures, "count", "input", show=False)
        q(s, f"n_used[{i}]", f"n_{k + 1},used", un.n_used[k], "runs",
          "input" if sc.runs_executed is not None else S["iso_c3"], show=False)
        q(s, f"p_U[{i}]", f"p_{k + 1}^U", un.p_U[k], "-", S["owen"], S["iso_c3"], S["garwood"], S["wmax"], S["margin"],
          show=False)
        q(s, f"term[{i}]", f"lambda_{k + 1}^U p_{k + 1}^U", un.terms[k], "1/h", S["putze_sum"], show=False)
        q(s, f"harm_term[{i}]", f"term_{k + 1} G_{k + 1}", un.harm_terms[k], "1/h", S["putze_full"], show=False)
    q(s, "p_new", "p_new", inputs.unknown.p_new, "-", "input (argued from a design rule, not tested)")
    q(s, "N1", "N1", inputs.unknown.N1, "count", "input")
    q(s, "lambda_new_U", "lambda_new^U", un.lambda_new_U, "1/h", S["iso_c3"], S["lw97"],
      *([S["unknown_ext"]] if inputs.unknown.N1 > 0 else []))
    q(s, "unknown_term", "lambda_new^U p_new", un.unknown_term, "1/h", S["putze_sum"], S["iso111"])
    q(s, "unknown_harm", "unknown x G_unk", un.unknown_harm, "1/h", S["putze_full"], S["harm_units"])
    if un.good_turing is not None:
        q(s, "N_discovery", "N", inputs.unknown.N_discovery, "count", "input")
        q(s, "good_turing_missing_mass", "N1/N", un.good_turing, "-", S["good"])
        q(s, "bk_epsilon", "sqrt(ln(1/(1-C_b))/N)", un.bk_epsilon, "-", S["bk"])
    s.tables.append(_table(["LS", "N_conf", "lambda^U,conf [1/h]", "j", "F(j)", "n_k used", "p_k^U", "term [1/h]",
                            "G_k", "harm term [1/h]"],
                           [[i, f"{scen[k].N_conf:,d}", f"{un.lambda_U_conf[k]:.5g}", scen[k].failures,
                             f"{un.F[k]:.4f}", f"{un.n_used[k]:,.1f}" + (" (executed)" if scen[k].runs_executed
                                                                        is not None else ""),
                             f"{un.p_U[k]:.4e}", f"{un.terms[k]:.4e}", f"{rk.G_k[k]:.4g}", f"{un.harm_terms[k]:.4e}"]
                            for k, i in enumerate(ids)]
                           + [["unknown", "", f"{un.lambda_new_U:.5g}", "", "", "", f"p_new = {inputs.unknown.p_new:g}",
                               f"{un.unknown_term:.4e}", f"{rk.G_unk:.4g}", f"{un.unknown_harm:.4e}"]],
                           "lrrrrrrrrr"))
    s.sources += [S["iso111"], S["iso_t11"], S["iso422"], S["iso833"], S["patel"], S["betschinske"], S["zhao"],
                  S["explore"]]
    if inputs.unknown.p_new_rationale:
        s.notes.append(f"p_new is argued, not tested: {inputs.unknown.p_new_rationale}")
    s.notes.append("Independent evidence units (Patel & Jung 2026): the runs count only as independent concrete "
                   "scenarios, not frames or slices of one scene; evidence under one triggering condition counts for "
                   "another only after a test under it. Per logical scenario: " + "; ".join(
                       f"{sc.id}: {sc.independent_units_note or 'NOT DOCUMENTED'}" for sc in scen))
    s.notes.append("Importance sampling and simulation reduce the field testing but do not replace it (Betschinske et "
                   "al. 2025): the exposure bounds and the unknown-scenario term still rest on confirmatory and "
                   "discovery driving. Scenario exploration (Feng et al. 2023; Moss et al. 2023) helps to find failures "
                   "and new kinds of scenario before the campaign; the frozen campaign then counts them.")
    if inputs.unknown.N1 > 0:
        s.notes.append(f"WARNING: N1 = {inputs.unknown.N1} > 0, so at least one kind of scenario outside the logical "
                       "scenarios appeared. Add a logical scenario, re-plan and re-run the campaign; the bound above "
                       "is a stopgap.")
    if un.good_turing is not None:
        s.notes.append(f"Good-Turing missing mass N1/N = {_f(un.good_turing)} (point estimate, information only). "
                       f"Berend-Kontorovich: P(U > E[U] + eps) <= exp(-N eps^2); at C_b, eps = {_f(un.bk_epsilon)}, "
                       "much weaker than the count bound and not used in Clause 12.")
    sections.append(s)

    # Cl. 12 -----------------------------------------------------------------------------------------
    ach = res.achievement
    s = Section("Cl. 12", "Evaluation of the achievement of the SOTIF and recommendation for release", [
        "harm total = sum_k lambda_k^U,conf x p_k^U x G_k + lambda_new^U x p_new x G_unk;  criterion met if "
        "harm total <= A_H",
        "with one common chain G this is: total = sum_k lambda_k^U,conf x p_k^U + lambda_new^U x p_new <= R_HB",
        "release recommended (12.4) if: criterion met AND every Clause 10 targeted case passed AND "
        "every term <= its human cap"])
    for k, i in enumerate(ids):
        q(s, f"term_over_budget[{i}]", f"term_{k + 1}/b_{k + 1}", ach.term_over_budget[k], "-", S["putze_sum"],
          show=False)
        q(s, f"cap_met[{i}]", f"term_{k + 1}<=h_{k + 1}", float(ach.caps_met[k]), "bool", S["caps"], show=False)
    q(s, "total", "R^U", ach.total, "1/h", S["putze_sum"], S["iso111"], S["iso_c632"])
    q(s, "R_HB_limit", "R_HB", ach.R_HB, "1/h", S["iso_c21"])
    q(s, "total_over_R_HB", "R^U/R_HB", ach.total_over_R_HB, "-", S["putze_sum"])
    q(s, "harm_total", "H^U", ach.harm_total, "1/h", S["putze_full"], S["iso111"], S["iso_c632"])
    q(s, "A_H_limit", "A_H", ach.A_H, "1/h", S["iso65"])
    q(s, "harm_total_over_A_H", "H^U/A_H", ach.ratio, "-", S["putze_full"])
    q(s, "unknown_over_reserve", "unknown/reserve", ach.unknown_over_reserve, "-", S["putze_sum"])
    q(s, "criterion_met", "H^U<=A_H", float(ach.criterion_met), "bool", S["putze_sum"], S["iso111"])
    q(s, "caps_all_met", "all terms<=cap", float(ach.caps_all_met), "bool", S["caps"])
    q(s, "release_recommended", "recommended", float(ach.recommended), "bool", S["iso123c"], S["iso124"])
    rows = [[i, f"{un.terms[k]:.4e}", f"{u.b[k]:.4e}", _pct(ach.term_over_budget[k], 1), f"{un.harm_terms[k]:.4e}",
             _cap(al.caps[k]), _f(bool(ach.caps_met[k]))] for k, i in enumerate(ids)]
    rows.append(["unknown", f"{un.unknown_term:.4e}", f"{res.reserve.b_unk:.4e}",
                 _pct(ach.unknown_over_reserve, 1) if math.isfinite(ach.unknown_over_reserve) else "inf",
                 f"{un.unknown_harm:.4e}", "", ""])
    rows.append(["total", f"{ach.total:.4e}", f"{ach.R_HB:.4e}", _pct(ach.total_over_R_HB, 1), f"{ach.harm_total:.4e}",
                 "", ""])
    rows.append(["criterion", "", "", "", f"A_H = {ach.A_H:.4e}", "", ""])
    s.tables.append(_table(["term", "upper bound [1/h]", "budget [1/h]", "bound/budget", "harm bound [1/h]",
                            "human cap [1/h]", "bound <= cap"], rows, "lrrrrrl"))
    rec = "recommended" if ach.recommended else "NOT recommended"
    s.notes += [f"Condition {n + 1}: {r}." for n, r in enumerate(ach.reasons)]
    s.notes.append(f"RECOMMENDATION FOR SOTIF RELEASE (12.4): {rec}. Joint confidence C = {_f(inputs.confidence.C)} "
                   f"for the sum (m = {res.joint.m} bounds at C_b = {res.joint.C_b:.5g}); margin "
                   f"{_pct(1 - ach.ratio, 1)} of the criterion.")
    s.notes.append("Terms against budgets: " + ", ".join(
        f"{i} {'within' if r <= 1 else 'ABOVE'} its budget" for i, r in zip(ids, ach.term_over_budget))
        + f"; unknown term {'within' if ach.unknown_over_reserve <= 1 else 'ABOVE'} the reserve. The total decides; "
          "the per-budget view shows where the margin sits.")
    if not ach.recommended:
        s.notes.append("Way back: analyse the cause, modify the function (Clause 8, e.g. 8.3.3 functional restrictions "
                       "such as a lower speed near crossings) and run a new frozen campaign on the new release.")
    s.sources += [S["iso833"]]
    sections.append(s)

    # Sensitivity ------------------------------------------------------------------------------------
    s = Section("Sensitivity", "What if logical scenario k had j failures (planning aid)", [
        "p_k^U = F(j) x w_k / n_k + Phi(-z) for that LS, all else frozen; factor F(1)/F(j_k); "
        "fails if harm total > A_H (total > R_HB with one chain) or a term exceeds its cap"])
    rows = []
    for k, row in enumerate(res.sensitivity):
        sj = ">100" if row.smallest_failing_j is None else str(row.smallest_failing_j)
        rows.append([row.ls_id, f"{row.factor_j1:.4f}", f"{row.total_j1:.4e}", _pct(row.ratio_j1, 1),
                     "pass" if row.passed_j1 else "FAIL", sj])
        q(s, f"sensitivity_factor_j1[{row.ls_id}]", f"F(1)/F(j_{k + 1})", row.factor_j1, "-", S["garwood"], show=False)
        q(s, f"sensitivity_total_j1[{row.ls_id}]", f"R^U(j_{k + 1}=1)", row.total_j1, "1/h", S["putze_sum"],
          S["sens"], show=False)
        q(s, f"sensitivity_ratio_j1[{row.ls_id}]", f"H^U/A_H(j_{k + 1}=1)", row.ratio_j1, "-", S["sens"], show=False)
        q(s, f"sensitivity_passed_j1[{row.ls_id}]", f"pass(j_{k + 1}=1)", float(row.passed_j1), "bool", S["sens"],
          show=False)
        q(s, f"sensitivity_min_failing_j[{row.ls_id}]", f"min failing j_{k + 1}",
          math.inf if row.smallest_failing_j is None else row.smallest_failing_j, "count", S["sens"], show=False)
    s.tables.append(_table(["LS", "factor F(1)/F(j)", "total with j=1 [1/h]", "of criterion", "result",
                            "smallest failing j"], rows, "lrrrlr"))
    s.notes.append("Planning aid only. After the campaign a failure means analyse, fix (Clause 8) and re-run a frozen "
                   "campaign on the new release; adding runs until the bound fits makes the stopping rule depend on "
                   "the result.")
    sections.append(s)

    # Cl. 13 -----------------------------------------------------------------------------------------
    op = res.operation
    s = Section("Cl. 13", "Operation phase: field monitoring thresholds", [
        "expected hazardous behaviours per year = R x T",
        "fixed one-year rule: lambda_L(k) = chi2_{1-C}(2k) / (2T);  k_min = smallest k with lambda_L(k) > R_HB  "
        "(equivalently P(X >= k_min | R_HB T) < 1 - C)",
        "detection probability at true rate r: P(X >= k_min | r T)",
        "anytime-valid e-process: E(t) = a^k(t) x exp(-(a - 1) x R_HB x t);  alarm when E(t) >= 1/(1 - C)"])
    q(s, "fleet_hours_per_year", "T", op.T, "h/yr", "input")
    q(s, "expected_HB_per_year_at_limit", "R_HB x T", op.expected_at_limit, "1/yr", S["iso131"])
    q(s, "expected_HB_per_year_at_bound", "R^U x T", op.expected_at_bound, "1/yr", S["iso131"])
    q(s, "k_min", "k_min", op.k_min, "count", S["garwood_lower"], S["monitor"])
    q(s, "lambda_L_at_k_min", "lambda_L(k_min)", op.lambda_L_k_min, "1/h", S["garwood_lower"])
    q(s, "false_alarm_at_k_min", "P(X>=k_min|R_HB T)", op.false_alarm_k_min, "-", S["garwood_lower"], S["monitor"])
    q(s, "zero_event_upper_one_year", "ln(1/(1-C))/T", op.zero_event_upper, "1/h", S["iso_c3"])
    q(s, "zero_event_upper_over_R_HB", "(ln(1/(1-C))/T)/R_HB", op.zero_event_upper / res.tol.R_HB, "-", S["iso_c3"])
    q(s, "alt_factor", "a", op.alt_factor, "-", "input")
    q(s, "e_threshold", "1/(1-C)", op.e_threshold, "-", S["ramdas"])
    q(s, "eprocess_floor", "k as T -> 0", op.e_floor, "count", S["eproc"])
    for y, hours, mu0, ka, e_k, e_km1 in op.e_rows:
        q(s, f"eprocess_alarm_k[{y:g}yr]", f"k_alarm({y:g} yr)", ka, "count", S["ramdas"], S["wald"], S["eproc"],
          show=False)
    lines = [f"  Fixed one-year rule: count k of {hb.id} in one year ({_int(op.T)} h) and its lower bound at "
             f"C = {_f(op.C)}:",
             _table(["k", "lambda_L(k) [1/h]", "lambda_L > R_HB", "P(X >= k | R_HB T)"],
                    [[kk, f"{lam:.4e}", "yes -> 13.4" if ex else "no", f"{pp:.4g}"] for kk, lam, ex, pp in op.rows],
                    "rrll"),
             f"  Probability that one year reaches k_min = {op.k_min} if the true rate is a multiple of R_HB:",
             _table(["true rate", "P(X >= k_min) in one year"],
                    [[f"{mm:g} x R_HB", f"{pp:.4g}"] for mm, pp in op.detection], "rr"),
             "",
             f"  Anytime-valid e-process (R_HB against {op.alt_factor:g} x R_HB; alarm at E >= {op.e_threshold:g}): "
             "alarm if the count observed by then reaches k",
             _table(["fleet operation", "hours", "R_HB x hours", "alarm count k", "E(k)", "E(k - 1)",
                     "fixed one-year rule"],
                    [[f"{y:g} yr", _int(hours), f"{mu0:.4g}", ka, f"{e_k:.4g}", f"{e_km1:.4g}",
                      f"{op.k_min} (end of year 1 only)" if y == 1 else "-"]
                     for y, hours, mu0, ka, e_k, e_km1 in op.e_rows], "rrrrrrl")]
    s.tables.append("\n".join(lines))
    s.sources += [S["iso133"], S["iso134"], S["wald"]]
    s.notes.append(f"At the limit the fleet would show {op.expected_at_limit:.3g} {hb.id} per year; at the Clause 12 "
                   f"bound {op.expected_at_bound:.3g}. Observing {op.k_min} or more in one year shows the criterion "
                   f"violated at C = {_f(op.C)} (false-alarm probability {op.false_alarm_k_min:.2g} at R_HB) and "
                   "triggers the SOTIF issue evaluation and resolution process (13.4).")
    e1 = next((r[3] for r in op.e_rows if r[0] == 1), None)
    s.notes.append("The fixed one-year rule is valid for one look at the end of the year; re-computing and checking "
                   "it every month inflates its false-alarm probability, which can then exceed 1 - C. The e-process may "
                   "be checked at any time: by "
                   f"Ville's inequality its false-alarm probability stays at or below {1 - op.C:g} over any horizon. "
                   "The price is a higher count"
                   + (f" ({e1} instead of {op.k_min} at one year)" if e1 is not None else "")
                   + f", and no alarm is possible with fewer than {op.e_floor} events. Choose a, the rate it is tuned to "
                     "detect, before operation starts.")
    s.notes.append(f"One year cannot confirm the criterion: with zero events the upper bound is "
                   f"{op.zero_event_upper:.3e} /h, {op.zero_event_upper / res.tol.R_HB:.1f} x R_HB. Field monitoring "
                   "detects violations; the release evidence of Clauses 10-12 carries the claim.")
    s.notes.append("Any field hazardous behaviour that cannot be attributed to a listed triggering condition counts "
                   "against the reserve for unknown scenarios (b_unk) and triggers 13.4 by itself; it is also a new "
                   "kind of scenario for N1 in the next release.")
    if inputs.operation.hb_detection_rule:
        s.notes.append(f"Field detection rule: {inputs.operation.hb_detection_rule}")
    s.notes.append("Both tests use C (not C_b): they monitor operation and are not among the m bounds of the release "
                   "claim. A new release restarts the count and the e-process.")
    if res.risk.per_ls:
        s.notes.append("With per-LS chains the limit R_HB assumes the field mix of logical scenarios matches the plan; "
                       "otherwise monitor each logical scenario against its budget b_k.")
    sections.append(s)

    # Work-product map -------------------------------------------------------------------------------
    s = Section("Work products", "ISO 21448 work-product map", ["which workbook outputs belong to which subclause"])
    s.tables.append(_table(["subclause", "workbook outputs"], work_product_map(inputs, res), "ll"))
    s.sources += [S["iso_wp"]]
    sections.append(s)
    return sections


_SOURCE_SPLIT = re.compile(r"(?<=\]); |(?<=input); ")


def format_report(inputs: WorkbookInputs, res: ChainResults, sections: list[Section]) -> str:
    """Render the sections as a plain-text report."""
    W = 100
    he, hb, ach = res.hazards.selected, res.hazards.selected_hb, res.achievement
    out = ["=" * W,
           f"SOTIF validation workbook (ISO 21448:2022)  |  case: {inputs.case_name}  |  {he.id} of {hb.id}  |  "
           f"K = {inputs.K} logical scenarios",
           "=" * W,
           f"Function: {inputs.function}",
           f"Hazardous behaviour: {hb.id} {hb.description}",
           f"Selected hazardous event: {he.id} {he.operational_situation} (harm class: {he.harm_class}; "
           f"severity {he.severity or '-'}; controllability {he.controllability or '-'})",
           f"Budget rule: {inputs.budget.allocation_rule}. Test cost is not an input: cost may decide how evidence "
           "is produced, never how much risk is accepted.",
           "Source labels: [checked] location confirmed in the course verification log; [location not checked]; "
           "[derived in this course]; 'input' = value from the input file."]
    for sec in sections:
        out += ["", "-" * W, f"{sec.step}  |  {sec.title}", "-" * W]
        for fml in sec.formulas:
            out.append(f"Formula: {fml}")
        shown = [x for x in sec.quantities if x.show]
        if shown:
            out.append("")
        for x in shown:
            out.append(f"  {x.name:<30s} {x.symbol:<22s} = {_f(x.value, 5):>12s}  {x.unit}")
        for t in sec.tables:
            out += ["", t]
        srcs: list[str] = []
        # Sources are joined with "; "; split only after a status label "]" (or after "input"), so that a
        # "; " inside a source's own parentheses stays on its line.
        for part in [p for x in sec.quantities for p in _SOURCE_SPLIT.split(x.source)] + sec.sources:
            if not part.startswith("input") and part not in srcs:
                srcs.append(part)
        if srcs:
            out += ["", "Sources:"] + [f"  - {p}" for p in srcs]
        if sec.notes:
            out.append("")
            out += [f"Note: {n}" for n in sec.notes]
    op = res.operation
    out += ["", "=" * W, "SUMMARY",
            (f"  A_H = {ach.A_H:.4e} /h; sum of upper bounds on harm = {ach.harm_total:.4e} /h "
             f"({_pct(ach.ratio, 1)} of A_H; per-LS chains); " if res.risk.per_ls else
             f"  R_HB = {ach.R_HB:.4e} /h; sum of upper bounds = {ach.total:.4e} /h ({_pct(ach.ratio, 1)} of R_HB); ")
            + f"Clause 10: {res.known.total_cases - res.known.total_failures}/{res.known.total_cases} targeted cases "
              f"passed; human caps: {'met' if ach.caps_all_met else 'NOT met'}.",
            f"  Recommendation for SOTIF release (12.4): {'recommended' if ach.recommended else 'NOT recommended'}.",
            f"  Operation (Cl. 13): {op.k_min} or more {hb.id} in one year ({_int(op.T)} h) show the criterion violated "
            f"at C = {_f(op.C)} (one look per year); the anytime-valid e-process alarms at "
            + ", ".join(f"{r[3]} by {r[0]:g} yr" for r in op.e_rows) + "; both trigger 13.4.",
            "=" * W]
    return "\n".join(out)


def per_logical_scenario_table(inputs: WorkbookInputs, res: ChainResults) -> list[dict[str, Any]]:
    """One row per logical scenario with the main planning and evaluation numbers."""
    u, t, un, ach, kn = res.alloc.used, res.targets, res.unknown, res.achievement, res.known
    rows = []
    for k, s in enumerate(inputs.logical_scenarios):
        rows.append({
            "LS": s.id, "name": s.name, "N_pilot": s.N_pilot, "lambda_U_pilot_per_h": float(res.expo.lambda_U[k]),
            "importance_factor": s.importance_factor, "human_share": s.human_share,
            "human_cap_per_h": None if math.isinf(res.alloc.caps[k]) else float(res.alloc.caps[k]),
            "G_k": float(res.risk.G_k[k]), "P_S_from": res.risk.P_S_from[k],
            "rule": res.alloc.rule, "weight": float(u.weights[k]), "harm_budget_per_h": float(u.harm[k]),
            "b_per_h": float(u.b[k]), "share": float(u.share[k]), "cap_binds": bool(u.clamped[k]),
            "p_star": float(t.p_star[k]), "one_in": float(t.one_in[k]),
            "harm_per_encounter": float(t.harm_per_encounter[k]), "n_planned": float(t.n[k]),
            "n_planned_ceil": int(t.n_ceil[k]),
            "targeted_cases": int(kn.cases[k]), "targeted_failures": int(kn.failures[k]),
            "targeted_passed": bool(kn.passed_per_ls[k]), "triggering_conditions": ", ".join(res.tcs.tcs_per_ls[k]),
            "independent_units_note": s.independent_units_note,
            "N_conf": s.N_conf, "lambda_U_conf_per_h": float(un.lambda_U_conf[k]), "failures": s.failures,
            "n_used": float(un.n_used[k]), "p_U": float(un.p_U[k]), "term_per_h": float(un.terms[k]),
            "harm_term_per_h": float(un.harm_terms[k]),
            "term_over_budget": float(ach.term_over_budget[k]), "term_le_cap": bool(ach.caps_met[k]),
        })
    return rows


def rule_comparison_table(inputs: WorkbookInputs, res: ChainResults) -> list[dict[str, Any]]:
    """One row per (rule, logical scenario) for every applicable budget rule."""
    rows = []
    for r in ALLOCATION_RULES:
        oc = res.alloc.comparison[r]
        if oc is None:
            continue
        for k, i in enumerate(inputs.ls_ids):
            rows.append({"rule": r, "used": r == res.alloc.rule, "LS": i, "weight": float(oc.weights[k]),
                         "harm_budget_per_h": float(oc.harm[k]), "b_per_h": float(oc.b[k]),
                         "share": float(oc.share[k]),
                         "cap_binds": bool(oc.clamped[k]), "p_star": float(oc.targets.p_star[k]),
                         "one_in": float(oc.targets.one_in[k]), "n": float(oc.targets.n[k]),
                         "n_total_rule": oc.targets.n_total, "protection_ratio_rule": oc.targets.protection_ratio})
    return rows


def export_results(inputs: WorkbookInputs, res: ChainResults, sections: list[Section], out_dir: str | Path
                   ) -> list[Path]:
    """Write results_<case>.csv (always) and results_<case>.xlsx (if pandas and openpyxl are installed)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = [x for sec in sections for x in sec.quantities]
    cols = ["name", "symbol", "value", "unit", "step", "source"]
    csv_path = out / f"results_{inputs.case_name}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(cols)
        for x in rows:
            wr.writerow([x.name, x.symbol, repr(x.value), x.unit, x.step, x.source])
    written = [csv_path]
    if importlib.util.find_spec("pandas") and importlib.util.find_spec("openpyxl"):
        import pandas as pd
        xlsx_path = out / f"results_{inputs.case_name}.xlsx"
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as xw:
            pd.DataFrame([{c: getattr(x, c) for c in cols} for x in rows]).to_excel(xw, sheet_name="results", index=False)
            pd.DataFrame(per_logical_scenario_table(inputs, res)).to_excel(xw, sheet_name="per_logical_scenario",
                                                                           index=False)
            pd.DataFrame(rule_comparison_table(inputs, res)).to_excel(xw, sheet_name="rule_comparison", index=False)
            pd.DataFrame([vars(vt) for vt in res.validation_targets]).to_excel(xw, sheet_name="validation_targets",
                                                                               index=False)
        written.append(xlsx_path)
    else:
        print("pandas and/or openpyxl not installed: skipping the .xlsx export (CSV written).")
    return written

# %% [markdown]
# ## Self-test
#
# `--check` reproduces the reference numbers of the robotaxi example (relative tolerance 1 % unless
# noted; budget shares within 0.05 percentage points) and checks invariants that must hold for any
# input: budgets add up under every rule, equal protection gives the same p* in every logical scenario,
# the equal split does not, caps are respected after clamping and the remainder is redistributed, F(0) =
# L, the Poisson failure bound is at least the exact binomial bound, the operation threshold matches the
# Poisson tail, the JSON round trip is lossless, the chain runs for K = 1 and K = 5, and the loader
# rejects bad input including old cost keys. For the literature options it checks that per-LS chains
# equal to the common chain reproduce the R_HB formulation exactly, that a lower P_S in LS-3 raises its p*
# by G / G_3, that a severity curve reproduces a given P_S, and that the e-process keeps its false-alarm
# guarantee under continuous monitoring. Reference values were computed independently of this code with
# scipy; the Cl. 13 threshold k_min = 3 and the e-process alarm counts 5, 5, 6, 7 were also checked by
# hand.

# %%
REFERENCE: dict[str, tuple[float, str, float, str]] = {
    # name: (reference value, tolerance kind "rel" | "abs" | "exact", tolerance, note)
    "h": (5.0e-6, "rel", 0.01, "synthetic benchmark: 50 events / 1.0e7 h"),
    "A_H_raw": (1.0e-7, "rel", 0.01, ""),
    "A_H": (1.0e-7, "rel", 0.01, "no rounding (round_A_H_to = null)"),
    "class_budget_over_fsi": (12.5, "rel", 0.01, "5.0e-7 / 4e-8"),
    "R_HB": (5.0e-7, "rel", 0.01, ""),
    "tau_naive_h": (5.9915e6, "rel", 0.01, ""),
    "tau_naive_fleet_days": (2995.7, "rel", 0.01, ""),
    "tau_naive_fleet_years": (8.20, "rel", 0.01, "365.25-day years"),
    "m": (8, "exact", 0, ""),
    "C_b": (0.99375, "rel", 0.01, ""),
    "L": (5.07517, "rel", 0.01, ""),
    "lambda_U_pilot[LS-1]": (4.16073, "rel", 0.01, ""),
    "lambda_U_pilot[LS-2]": (0.55865, "rel", 0.01, ""),
    "lambda_U_pilot[LS-3]": (0.34608, "rel", 0.01, ""),
    "b_unk": (5e-8, "rel", 0.01, ""),
    "B": (4.5e-7, "rel", 0.01, ""),
    "share[LS-1]": (0.8214, "abs", 0.0005, "82.14 %, +-0.05 pp"),
    "share[LS-2]": (0.1103, "abs", 0.0005, "11.03 %, +-0.05 pp"),
    "share[LS-3]": (0.0683, "abs", 0.0005, "6.83 %, +-0.05 pp"),
    "b[LS-1]": (3.6963e-7, "rel", 0.01, ""),
    "b[LS-2]": (4.9629e-8, "rel", 0.01, ""),
    "b[LS-3]": (3.0744e-8, "rel", 0.01, ""),
    "p_star[LS-1]": (8.8837e-8, "rel", 0.01, ""),
    "p_star[LS-2]": (8.8837e-8, "rel", 0.01, ""),
    "p_star[LS-3]": (8.8837e-8, "rel", 0.01, ""),
    "one_in[LS-1]": (11256577, "rel", 0.01, "1 in 11,256,577"),
    "n[LS-1]": (571290.8, "rel", 0.01, ""),
    "n[LS-2]": (2856454.2, "rel", 0.01, ""),
    "n[LS-3]": (5712908.5, "rel", 0.01, ""),
    "n_total": (9.1407e6, "rel", 0.01, ""),
    "protection_ratio": (1.000, "rel", 0.01, ""),
    "caps_binding": (0, "exact", 0, "no human cap binds under equal protection"),
    "compare_p_star[proportional_to_human][LS-1]": (5.4077e-8, "rel", 0.01, ""),
    "compare_p_star[proportional_to_human][LS-2]": (2.8193e-7, "rel", 0.01, ""),
    "compare_p_star[proportional_to_human][LS-3]": (1.9504e-7, "rel", 0.01, ""),
    "compare_n_total[proportional_to_human]": (4.4407e6, "rel", 0.01, ""),
    "compare_p_star[equal_split][LS-1]": (3.6051e-8, "rel", 0.01, ""),
    "compare_p_star[equal_split][LS-2]": (2.6850e-7, "rel", 0.01, ""),
    "compare_p_star[equal_split][LS-3]": (4.3343e-7, "rel", 0.01, ""),
    "compare_n_total[equal_split]": (3.5238e6, "rel", 0.01, ""),
    "compare_protection_ratio[equal_split]": (12.02, "rel", 0.01, ""),
    "sigma_U": (0.17257, "rel", 0.01, ""),
    "delta": (1.1717, "rel", 0.01, "z = 6.5"),
    "p_miss": (4.016e-11, "rel", 0.01, "Phi(-6.5)"),
    "p_miss_over_min_p_star": (4.5e-4, "rel", 0.01, "0.045 % of p*"),
    "z_auto": (6.0170, "rel", 0.01, "f = 0.01"),
    "lambda_U_conf[LS-1]": (4.03546, "rel", 0.01, ""),
    "lambda_U_conf[LS-2]": (0.51263, "rel", 0.01, ""),
    "lambda_U_conf[LS-3]": (0.30981, "rel", 0.01, ""),
    "term[LS-1]": (3.5866e-7, "rel", 0.01, "includes lambda^U x Phi(-z)"),
    "term[LS-2]": (4.5561e-8, "rel", 0.01, "includes lambda^U x Phi(-z)"),
    "term[LS-3]": (2.7535e-8, "rel", 0.01, "includes lambda^U x Phi(-z)"),
    "unknown_term": (2.5376e-8, "rel", 0.01, ""),
    "total": (4.5713e-7, "rel", 0.01, ""),
    "total_over_R_HB": (0.914, "abs", 0.001, "91.4 %"),
    "criterion_met": (1.0, "exact", 0, ""),
    "targeted_cases_total": (240, "exact", 0, "48 + 144 + 48"),
    "known_passed": (1.0, "exact", 0, ""),
    "release_recommended": (1.0, "exact", 0, ""),
    "sensitivity_total_j1[LS-1]": (6.0556e-7, "rel", 0.01, ""),
    "sensitivity_passed_j1[LS-1]": (0.0, "exact", 0, "one failure in LS-1 fails"),
    "sensitivity_total_j1[LS-2]": (4.7599e-7, "rel", 0.01, ""),
    "sensitivity_passed_j1[LS-2]": (1.0, "exact", 0, ""),
    "sensitivity_total_j1[LS-3]": (4.6853e-7, "rel", 0.01, ""),
    "sensitivity_passed_j1[LS-3]": (1.0, "exact", 0, ""),
    "sensitivity_min_failing_j[LS-1]": (1, "exact", 0, ""),
    "sensitivity_min_failing_j[LS-2]": (3, "exact", 0, ""),
    "sensitivity_min_failing_j[LS-3]": (5, "exact", 0, ""),
    "expected_HB_per_year_at_limit": (0.365, "rel", 0.01, "5e-7 /h x 730,000 h"),
    "k_min": (3, "exact", 0, "by hand: lambda_L(2) = 4.87e-7 < R_HB < lambda_L(3) = 1.12e-6; "
                             "P(X>=2|0.365) = 0.052 > 0.05 > P(X>=3|0.365) = 0.0062"),
    "harm_total": (9.1426e-8, "rel", 0.01, "total x G = 4.5713e-7 x 0.2"),
    "harm_total_over_A_H": (0.914, "abs", 0.001, "equals total / R_HB with one chain"),
    "per_ls_chain": (0.0, "exact", 0, "mock uses the common chain"),
    "e_threshold": (20.0, "rel", 0.01, "1 / (1 - 0.95)"),
    "eprocess_floor": (5, "exact", 0, "2^5 = 32 >= 20 > 2^4 = 16"),
    "eprocess_alarm_k[0.5yr]": (5, "exact", 0, "by hand: E(5) = 32 e^-0.1825 = 26.7, E(4) = 13.3"),
    "eprocess_alarm_k[1yr]": (5, "exact", 0, "by hand: E(5) = 32 e^-0.365 = 22.2, E(4) = 11.1"),
    "eprocess_alarm_k[2yr]": (6, "exact", 0, "by hand: E(6) = 64 e^-0.73 = 30.8, E(5) = 15.4"),
    "eprocess_alarm_k[5yr]": (7, "exact", 0, "by hand: E(7) = 128 e^-1.825 = 20.6, E(6) = 10.3"),
}


def _mock_copy() -> dict[str, Any]:
    return json.loads(json.dumps(MOCK_INPUTS_ROBOTAXI))


def _invariant_checks(inputs: WorkbookInputs, res: ChainResults) -> list[tuple[str, bool, str]]:
    """Checks that must hold for any valid input, plus generalisation and loader checks."""
    out: list[tuple[str, bool, str]] = []
    B, R, lam = res.reserve.B, res.tol.R_HB, res.expo.lambda_U

    # Budgets add up under every rule (fixed shares added so that all four rules apply).
    raw = _mock_copy()
    for ls, fs in zip(raw["logical_scenarios"], (0.6, 0.25, 0.15)):
        ls["fixed_share"] = fs
    rf = run_chain(inputs_from_dict(raw))
    ok = all(oc is not None and math.isclose(float(oc.b.sum()) + oc.unallocated + rf.reserve.b_unk, rf.tol.R_HB,
                                             rel_tol=1e-12) for oc in rf.alloc.comparison.values())
    out.append(("budgets add up under every rule: sum b_k + b_unk = R_HB", ok, ", ".join(rf.alloc.comparison)))

    ep = res.alloc.comparison["equal_protection"]
    ps = ep.targets.p_star
    out.append(("equal_protection gives identical p* for all LS", float(ps.max() / ps.min() - 1) < 1e-12,
                f"p* = {np.array2string(ps, precision=6)}"))
    eq = res.alloc.comparison["equal_split"]
    out.append(("protection ratio of equal_split > 1", eq.targets.protection_ratio > 1,
                f"{eq.targets.protection_ratio:.3f}"))
    ph = res.alloc.comparison["proportional_to_human"]
    s_k = np.array([s.human_share for s in inputs.logical_scenarios])
    out.append(("proportional_to_human: b_k / s_k identical (same factor over humans)",
                float(np.ptp(ph.b / s_k) / (ph.b / s_k).mean()) < 1e-12, f"b/s = {(ph.b / s_k)[0]:.4e}"))

    caps = np.array([np.inf, np.inf, 2.0e-8])
    b2, cl2, it2 = allocate_with_caps(B, lam, caps)
    ok = (math.isclose(float(b2.sum()), B, rel_tol=1e-12) and b2[2] == 2.0e-8 and cl2.tolist() == [False, False, True]
          and math.isclose(b2[0] / b2[1], lam[0] / lam[1], rel_tol=1e-12) and it2 == 2)
    out.append(("cap clamp-and-redistribute (LS-3 cap 2.0e-8 binds)", ok,
                f"b = {np.array2string(b2, precision=4)}, passes = {it2}"))
    # Cascade: the LS-2 cap (5.1e-8) does not bind at first (4.96e-8) but binds after LS-3 is clamped and its
    # excess re-allocated (5.21e-8); LS-1 then receives the rest, 3.89e-7.
    caps3 = np.array([np.inf, 5.1e-8, 1.0e-8])
    b3, cl3, it3 = allocate_with_caps(B, lam, caps3)
    ok3 = (np.allclose(b3, [B - 6.1e-8, 5.1e-8, 1.0e-8], rtol=1e-12) and cl3.tolist() == [False, True, True]
           and it3 == 3)
    out.append(("cascading clamps (second cap binds only after the first)", ok3,
                f"b = {np.array2string(b3, precision=4)}, passes = {it3}"))
    b4, cl4, _ = allocate_with_caps(B, lam, np.array([1e-8, 1e-8, 1e-8]))
    out.append(("all LS capped: remainder left unallocated", bool(cl4.all()) and math.isclose(float(b4.sum()), 3e-8),
                f"sum b = {float(b4.sum()):.2e} of B = {B:.2e}"))
    raw = _mock_copy()
    raw["logical_scenarios"][0]["human_cap_behaviour_rate"] = 1.0e-7
    rc = run_chain(inputs_from_dict(raw))
    pc = rc.targets.p_star
    okc = (bool(rc.alloc.used.clamped[0]) and math.isclose(float(rc.alloc.used.b.sum()), rc.reserve.B, rel_tol=1e-12)
           and rc.alloc.used.b[0] == 1.0e-7 and pc[0] < pc[1] and math.isclose(pc[1], pc[2], rel_tol=1e-12))
    out.append(("full chain with a binding human cap in LS-1 (1e-7)", okc,
                f"b_1 = {rc.alloc.used.b[0]:.2e}, p* = {np.array2string(pc, precision=4)}"))

    # Full conditioning per LS (Putze et al. 2023). (1) Per-LS chains equal to the common chain must reproduce the
    # R_HB formulation exactly.
    raw = _mock_copy()
    for ls in raw["logical_scenarios"]:
        ls.update(P_E=raw["chain"]["P_E"], P_C=raw["chain"]["P_C"], P_S=raw["chain"]["P_S"])
    re_ = run_chain(inputs_from_dict(raw))
    b_rhb = B * lam / lam.sum()  # the R_HB formulation of equal protection, written out directly
    oke = ((not re_.risk.per_ls) and np.allclose(re_.alloc.used.b, res.alloc.used.b, rtol=1e-12, atol=0)
           and np.allclose(res.alloc.used.b, b_rhb, rtol=1e-12, atol=0)
           and np.allclose(re_.targets.n, res.targets.n, rtol=1e-12, atol=0)
           and math.isclose(re_.achievement.total, res.achievement.total, rel_tol=1e-12)
           and math.isclose(res.achievement.ratio, res.achievement.total_over_R_HB, rel_tol=1e-12)
           and re_.achievement.criterion_met == (res.achievement.total <= R))
    out.append(("per-LS chains equal to the common chain reproduce the R_HB form", oke,
                f"H/A_H = {res.achievement.ratio:.6f} = total/R_HB = {res.achievement.total_over_R_HB:.6f}"))
    # (2) LS-3 (turning, lower speed) with P_S = 0.5: its allowed p* rises by G / G_3 = 0.2 / 0.125 = 1.6; the
    # others are unchanged; the harm probability per encounter p* G is the same everywhere; harm budgets add up.
    raw = _mock_copy()
    raw["logical_scenarios"][2]["P_S"] = 0.5
    r3 = run_chain(inputs_from_dict(raw))
    p3, G3 = r3.targets.p_star, r3.risk.G_k
    ok3s = (r3.risk.per_ls and math.isclose(p3[2] / p3[0], 1.6, rel_tol=1e-12)
            and np.allclose(p3[:2], res.targets.p_star[:2], rtol=1e-12, atol=0)
            and float(np.ptp(p3 * G3) / (p3 * G3).mean()) < 1e-12
            and math.isclose(float(r3.alloc.used.harm.sum()), r3.reserve.A_prime, rel_tol=1e-12)
            and math.isclose(p3[2], 1.42139e-7, rel_tol=1e-4))
    out.append(("LS-3 with P_S = 0.5: p*_3 rises by G/G_3 = 1.6, harm per encounter equal", ok3s,
                f"p* = {np.array2string(p3, precision=5)}, harm ratio {r3.achievement.ratio:.4f}"))
    # (3) The same P_S from a logistic injury-risk curve (beta0 = -3, beta1 = 0.1, impact speed 30 -> 0.5).
    raw = _mock_copy()
    raw["logical_scenarios"][2]["severity_curve"] = {"beta0": -3.0, "beta1": 0.1, "impact_speed": 30.0}
    rcv = run_chain(inputs_from_dict(raw))
    okcv = (rcv.risk.P_S_from[2] == "curve" and math.isclose(rcv.risk.P_S_k[2], 0.5, rel_tol=1e-12)
            and np.allclose(rcv.targets.p_star, p3, rtol=1e-12, atol=0))
    out.append(("severity curve at its midpoint gives P_S = 0.5 and the same p*", okcv,
                f"P_S,3 = {rcv.risk.P_S_k[2]:.6f}"))
    # (4) Harm budgets add up under every rule with per-LS chains.
    raw = _mock_copy()
    raw["logical_scenarios"][2]["P_S"] = 0.5
    for ls, fs in zip(raw["logical_scenarios"], (0.6, 0.25, 0.15)):
        ls["fixed_share"] = fs
    rh = run_chain(inputs_from_dict(raw))
    okh = all(oc is not None and math.isclose(float(oc.harm.sum()) + oc.unallocated_harm + rh.reserve.reserve_harm,
                                              rh.crit.A_H, rel_tol=1e-12) for oc in rh.alloc.comparison.values())
    out.append(("harm budgets add up under every rule (per-LS chains): sum a_k + reserve = A_H", okh,
                ", ".join(rh.alloc.comparison)))

    out.append(("F(0) = L", math.isclose(float(failure_factor(0, res.joint.C_b)), res.joint.L, rel_tol=1e-10),
                f"{float(failure_factor(0, res.joint.C_b)):.6f}"))
    cons = all(float(failure_factor(jj, res.joint.C_b)) / nn >= float(beta.ppf(res.joint.C_b, jj + 1, nn - jj)) * (1 - 1e-9)
               for nn in (20, 100, 1000, 10**5, 10**6) for jj in (0, 1, 2, 5))
    out.append(("Poisson failure bound >= Clopper-Pearson bound", cons, "n in 20..1e6, j in 0..5"))

    a0 = what_if_failures(inputs, res, inputs.ls_ids[0], inputs.logical_scenarios[0].failures)
    out.append(("what-if with observed j reproduces Clause 12", math.isclose(a0.total, res.achievement.total,
                rel_tol=1e-12), f"{a0.total:.6e}"))

    raw = _mock_copy()
    raw["logical_scenarios"][1]["targeted_failures"] = 1
    r10 = run_chain(inputs_from_dict(raw))
    out.append(("a failed targeted case blocks the release recommendation",
                (not r10.known.passed) and r10.achievement.criterion_met and not r10.achievement.recommended,
                r10.achievement.reasons[1][:60]))
    raw = _mock_copy()
    raw["logical_scenarios"][2]["targeted_cases"] = 0
    r10b = run_chain(inputs_from_dict(raw))
    out.append(("LS with triggering conditions but no targeted case: Cl. 10 incomplete",
                (not r10b.known.passed) and r10b.known.missing_cases == ["LS-3"], str(r10b.known.missing_cases)))

    op = res.operation
    mu, a = R * op.T, 1 - inputs.confidence.C
    okop = (float(poisson.sf(op.k_min - 1, mu)) < a <= float(poisson.sf(op.k_min - 2, mu))
            and poisson_lower_rate(op.k_min, op.T, inputs.confidence.C) > R
            >= poisson_lower_rate(op.k_min - 1, op.T, inputs.confidence.C))
    out.append(("Cl. 13: k_min matches the Poisson tail test", okop,
                f"P(X>={op.k_min}) = {float(poisson.sf(op.k_min - 1, mu)):.4f} < {a:g} <= "
                f"P(X>={op.k_min - 1}) = {float(poisson.sf(op.k_min - 2, mu)):.4f}"))
    oke1 = all(e_k >= op.e_threshold > e_km1 for _, _, _, ka, e_k, e_km1 in op.e_rows if ka > 0)
    out.append(("Cl. 13: e-process alarm count is the smallest k with E >= 1/(1-C)", oke1,
                ", ".join(f"{y:g} yr: k = {ka}" for y, _, _, ka, _, _ in op.e_rows)))
    # Ville's inequality: under the null rate, watched continuously over five years, the e-process raises a false
    # alarm with probability <= 1 - C. Monte Carlo over Poisson paths (an alarm can only start at an event).
    rng = np.random.default_rng(7)
    horizon, n_paths, a_f = 5 * op.T, 100_000, op.alt_factor
    counts = rng.poisson(R * horizon, n_paths)
    alarms = 0
    for c in counts[counts >= op.e_floor]:
        times = np.sort(rng.uniform(0.0, horizon, int(c)))
        e_vals = a_f ** np.arange(1, int(c) + 1) * np.exp(-(a_f - 1.0) * R * times)
        alarms += int(np.any(e_vals >= op.e_threshold))
    fa = alarms / n_paths
    out.append(("Cl. 13: e-process false-alarm rate <= 1 - C under continuous monitoring (5 yr, MC)",
                fa <= 1 - inputs.confidence.C, f"{fa:.4f} over {n_paths:,} paths"))

    with tempfile.TemporaryDirectory() as td:
        p = write_mock_inputs(Path(td) / "mock.json")
        res2 = run_chain(load_inputs(p))
    out.append(("JSON round trip (write_mock_inputs -> load_inputs)", math.isclose(res2.achievement.total,
                res.achievement.total, rel_tol=1e-12), f"{res2.achievement.total:.6e}"))

    for K_new in (1, 5):
        raw = _mock_copy()
        base = raw["logical_scenarios"]
        raw["logical_scenarios"] = [dict(base[i % 3], id=f"LS-{i + 1}", human_share=1.0 / K_new) for i in range(K_new)]
        for tc in raw["triggering_conditions"]:
            tc["logical_scenarios"] = "all"
        rK = run_chain(inputs_from_dict(raw))
        okK = (rK.joint.m == 2 * K_new + 2 and math.isclose(float(rK.alloc.used.b.sum()), rK.reserve.B, rel_tol=1e-12)
               and abs(rK.targets.protection_ratio - 1) < 1e-12)
        out.append((f"generalises to K = {K_new}", okK, f"m = {rK.joint.m}, total = {rK.achievement.total:.4e}"))

    def mv(r: dict, src: str, dst: str) -> None:
        r[dst] = r.pop(src)

    bad_cases: dict[str, tuple[Any, str]] = {
        "P_E > 1": (lambda r: r["chain"].__setitem__("P_E", 1.5), "chain.P_E"),
        "duplicate logical scenario ids": (lambda r: r["logical_scenarios"][1].__setitem__("id", "LS-1"), "unique"),
        "non-integer count": (lambda r: r["logical_scenarios"][0].__setitem__("N_pilot", 4000.5), "integer"),
        "unknown key": (lambda r: r["fleet"].__setitem__("carz", 1), "unknown key"),
        "old cost key cost_per_run": (lambda r: r["logical_scenarios"][0].__setitem__("cost_per_run", 0.002),
                                      "cost is no longer an input"),
        "old cost key compute_price_eur_per_h": (
            lambda r: r["logical_scenarios"][2].__setitem__("compute_price_eur_per_h", 2.4), "cost is no longer an input"),
        "old key situation_types": (lambda r: mv(r, "logical_scenarios", "situation_types"),
                                    "renamed to 'logical_scenarios'"),
        "HE shares sum > 1 in one harm class": (
            lambda r: r["hazardous_events"][2].__setitem__("share_of_harm_class_budget", 0.95), "sum to 1.05 > 1"),
        "unknown LS id in a triggering condition": (
            lambda r: r["triggering_conditions"][0].__setitem__("logical_scenarios", ["LS-9"]),
            "unknown logical scenario id"),
        "HE names an unknown HB": (lambda r: r["hazardous_events"][0].__setitem__("hb_id", "HB-9"),
                                   "no hazardous behaviour"),
        "selected HE not listed": (lambda r: r.__setitem__("selected_hazardous_event", "HE-9.9"),
                                   "selected_hazardous_event"),
        "benchmark harm class differs from the selected HE": (
            lambda r: r["benchmark"].__setitem__("harm_class", "cyclist injury"), "harm class"),
        "human shares do not sum to 1": (lambda r: r["logical_scenarios"][0].__setitem__("human_share", 0.6),
                                         "sum to 1"),
        "unknown allocation rule": (lambda r: r["budget"].__setitem__("allocation_rule", "cheapest_test"),
                                    "allocation_rule"),
        "rule 'fixed' without fixed shares": (lambda r: r["budget"].__setitem__("allocation_rule", "fixed"),
                                              "fixed_share"),
        "targeted failures > targeted cases": (
            lambda r: r["logical_scenarios"][0].__setitem__("targeted_failures", 49), "targeted_failures"),
        "z_mode invalid": (lambda r: r["simulator"].__setitem__("z_mode", "maybe"), "z_mode"),
        "benchmark with both exposure_hours and miles": (
            lambda r: r["benchmark"].update(miles=1e8, average_speed_mph=15.5), "exactly one exposure"),
        "benchmark without an exposure": (lambda r: r["benchmark"].pop("exposure_hours"), "exactly one exposure"),
        "benchmark miles without average speed": (
            lambda r: (r["benchmark"].pop("exposure_hours"), r["benchmark"].update(miles=1e8)), "together"),
        "old benchmark key 'source'": (lambda r: r["benchmark"].__setitem__("source", "x"), "source_note"),
        "LS gives both P_S and severity_curve": (
            lambda r: r["logical_scenarios"][2].update(
                P_S=0.5, severity_curve={"beta0": -3.0, "beta1": 0.1, "impact_speed": 30.0}), "not both"),
        "per-LS P_S > 1": (lambda r: r["logical_scenarios"][0].__setitem__("P_S", 1.2), "P_S"),
        "alt_factor <= 1": (lambda r: r["operation"].__setitem__("alt_factor", 1.0), "alt_factor"),
    }
    for label, (mutate, expect) in bad_cases.items():
        raw = _mock_copy()
        mutate(raw)
        try:
            inputs_from_dict(raw)
            out.append((f"loader rejects: {label}", False, "accepted"))
        except InputError as exc:
            msg = str(exc)
            out.append((f"loader rejects: {label}", expect in msg, msg[:70]))
    return out


def self_test() -> bool:
    """Reproduce REFERENCE for the mock inputs and run invariant checks. Prints a table; returns pass/fail."""
    inputs = inputs_from_dict(MOCK_INPUTS_ROBOTAXI)
    res = run_chain(inputs)
    values = {x.name: x.value for sec in build_sections(inputs, res) for x in sec.quantities}
    all_ok = True
    print("Self-test 1/2: reference values (robotaxi mock, equal_protection)")
    print(f"  {'quantity':<46s} {'computed':>13s} {'reference':>13s} {'deviation':>10s}  {'tol':<7s} result")
    for name, (ref, kind, tol, note) in REFERENCE.items():
        if name not in values:
            all_ok = False
            print(f"  {name:<46s} {'missing':>13s}  FAIL")
            continue
        got = values[name]
        if kind == "rel":
            dev = abs(got - ref) / abs(ref)
            ok, dev_s, tol_s = dev <= tol, f"{100 * dev:.3f} %", f"{100 * tol:g} %"
        elif kind == "abs":
            dev = abs(got - ref)
            ok, dev_s, tol_s = dev <= tol, f"{dev:.5f}", f"{tol:g}"
        else:
            ok, dev_s, tol_s = got == ref, "-", "exact"
        all_ok &= ok
        print(f"  {name:<46s} {_f(got, 5):>13s} {_f(ref, 5):>13s} {dev_s:>10s}  {tol_s:<7s} {'ok' if ok else 'FAIL'}"
              + (f"   ({note})" if note else ""))
    print("\nSelf-test 2/2: invariants, generalisation and input validation")
    for label, ok, detail in _invariant_checks(inputs, res):
        all_ok &= ok
        print(f"  {'ok  ' if ok else 'FAIL'}  {label:<66s} {detail}")
    print(f"\nSelf-test {'PASSED' if all_ok else 'FAILED'}.")
    return all_ok

# %% [markdown]
# ## Command line
#
# `main()` parses the options, runs the chain, prints the report and writes the exports. In a notebook
# the last cell instead runs the mock example and prints the report, without writing files.

# %%
def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="SOTIF (ISO 21448:2022) quantitative validation chain for one hazardous event, "
                    "structured along the clauses of the standard.")
    parser.add_argument("--inputs", type=Path, help="JSON input file (default: built-in robotaxi mock)")
    parser.add_argument("--write-mock", type=Path, metavar="PATH", help="write the mock inputs as JSON to PATH")
    parser.add_argument("--check", action="store_true", help="run the self-test; exit code 1 on failure")
    parser.add_argument("--out-dir", type=Path, default=Path("."), help="directory for results_<case>.csv/.xlsx")
    args = parser.parse_args(argv)

    if args.write_mock:
        print(f"Mock inputs written to {write_mock_inputs(args.write_mock)}")
        if not args.inputs and not args.check:
            return 0
    if args.check:
        if args.inputs:
            print("Note: --check always uses the built-in mock inputs; --inputs is ignored.")
        return 0 if self_test() else 1

    try:
        inputs = load_inputs(args.inputs) if args.inputs else inputs_from_dict(MOCK_INPUTS_ROBOTAXI)
    except InputError as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2
    res = run_chain(inputs)
    sections = build_sections(inputs, res)
    print(format_report(inputs, res, sections))
    for p in export_results(inputs, res, sections, args.out_dir):
        print(f"Written: {p}")
    return 0


def _running_in_notebook() -> bool:
    try:
        from IPython import get_ipython  # type: ignore
    except ImportError:
        return False
    shell = get_ipython()
    return shell is not None and shell.__class__.__name__ == "ZMQInteractiveShell"


# %%
if __name__ == "__main__":
    if _running_in_notebook():
        _inputs = inputs_from_dict(MOCK_INPUTS_ROBOTAXI)
        _res = run_chain(_inputs)
        print(format_report(_inputs, _res, build_sections(_inputs, _res)))
    else:
        sys.exit(main())
