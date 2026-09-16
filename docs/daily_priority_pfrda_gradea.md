# Daily priority — PFRDA Officer Grade 'A' (Assistant Manager) (`pfrda_gradea`)

> coverage_depth is real where it exists: scripts/quiz.py logs attempts to user_attempts and recomputes topic_coverage (accuracy-based depth) after each session. A topic with no topic_coverage row has never been quizzed — it falls back to coverage_depth = 0.0, the layered-coverage skill's prescribed value for untested items (untested = max urgency, never a fabricated default), not a sign the signal is missing entirely. Most topics still have no row (only a handful have been quizzed so far) — expect a mix of real accuracy-driven ranking and weight-only ranking until more sessions are run.

## Common (all streams) — `phase1_p1` (Phase I, Paper 1 — English/Quant Aptitude/Reasoning/GA (all streams))

- Total items in scope: 46
- Uncovered items (coverage = 0, never quizzed): 46 of 46
- At-risk items (weight > median AND coverage < 50%): 23

Showing top 15 of 46:

| Rank | topic_id | name | weight | priority_score |
|---|---|---|---|---|
| 1 | pfrda_english_language | English Language (PFRDA) | 31.1220 | 31.1220 |
| 2 | pfrda_general_awareness_financial | General Awareness incl. Financial Sector (PFRDA) | 31.1220 | 31.1220 |
| 3 | pfrda_quantitative_aptitude | Quantitative Aptitude (PFRDA) | 31.1220 | 31.1220 |
| 4 | pfrda_reasoning | Test of Reasoning (PFRDA) | 31.1220 | 31.1220 |
| 5 | pfrda_quant_data_interpretation | Data Interpretation (Bar/Line Chart, Caselet) | 10.4805 | 10.4805 |
| 6 | pfrda_eng_reading_comprehension | Reading Comprehension (incl. Vocabulary-in-Context) | 7.3683 | 7.3683 |
| 7 | pfrda_quant_quadratic_equations | Quadratic Equations (Quantity/Data Comparison) | 7.1244 | 7.1244 |
| 8 | pfrda_reasoning_puzzle_matching | Puzzle — Matching-Based (incl. Date & Attribute Matching) | 7.1244 | 7.1244 |
| 9 | pfrda_reasoning_puzzle_seating | Puzzle — Linear/Floor Seating Arrangement | 7.1244 | 7.1244 |
| 10 | pfrda_eng_error_spotting | Error Spotting | 6.8805 | 6.8805 |
| 11 | pfrda_ga_banking_finance_current | Banking/Finance Current Affairs (incl. Abbreviations, Regulatory Framework, Digital Payments/Fintech) | 6.4683 | 6.4683 |
| 12 | pfrda_ga_govt_schemes | Government Schemes/Apps & Policy Targets | 6.2244 | 6.2244 |
| 13 | pfrda_reasoning_puzzle_scheduling | Puzzle — Date/Month/Day-of-Week Scheduling | 5.2488 | 5.2488 |
| 14 | pfrda_reasoning_coding_decoding | Coding-Decoding (Letter/Word/Number/Machine Input-Output) | 5.1561 | 5.1561 |
| 15 | pfrda_eng_synonyms_vocab | Synonyms & Word Usage (Vocabulary) | 3.9366 | 3.9366 |

## General stream — `phase1_p2_general` (Phase I, Paper 2 — General stream)

- Total items in scope: 63
- Uncovered items (coverage = 0, never quizzed): 63 of 63
- At-risk items (weight > median AND coverage < 50%): 28

Showing top 15 of 63:

| Rank | topic_id | name | weight | priority_score |
|---|---|---|---|---|
| 1 | pfrda_costing | Costing — Cost/Management Accounting, Lean/Six Sigma (PFRDA) | 32.8464 | 32.8464 |
| 2 | pfrda_companies_act | Companies Act 2013 — Chapters III/IV/VIII/X/XI/XII/XXVII | 32.1047 | 32.1047 |
| 3 | pfrda_finance | Finance — Financial System/Markets/Derivatives/Fiscal Policy (PFRDA) | 31.8523 | 31.8523 |
| 4 | pfrda_pension_sector | Pension Sector — NPS, APY, Annuities (PFRDA) | 30.6427 | 30.6427 |
| 5 | pfrda_commerce_accountancy | Commerce & Accountancy (PFRDA) | 28.0084 | 28.0084 |
| 6 | pfrda_management | Management — Processes, Leadership, HRD, Motivation Theories (PFRDA) | 27.3523 | 27.3523 |
| 7 | pfrda_economics_basic | Economics — UG-level (PFRDA General; NOT linked to postgrad-depth canonical Macro Theory topics) | 27.0713 | 27.0713 |
| 8 | pfrda_ca_cashflow_ratio | Cash Flow Statement, Fund Flow Statement, Financial Statement & Ratio Analysis | 11.0139 | 11.0139 |
| 9 | pfrda_pen_nps | National Pension System (NPS) | 10.9769 | 10.9769 |
| 10 | pfrda_cost_control_analysis | Cost Control & Analysis — Standard Costing, Marginal Costing, Budget & Budgetary Control | 9.8330 | 9.8330 |
| 11 | pfrda_fin_regulatory_bodies | Role & Functions of Regulatory Bodies in the Financial Sector | 8.5493 | 8.5493 |
| 12 | pfrda_ca_standards | Accounting Standards — Depreciation, Inventories, Revenue Recognition, Fixed Assets, Foreign Exchange Transactions, Investments | 8.4081 | 8.4081 |
| 13 | pfrda_mgmt_leadership_styles | Leadership Styles & Theories; Successful vs. Effective Leader | 7.1615 | 7.1615 |
| 14 | pfrda_pen_apy | Atal Pension Yojana (APY) | 7.0588 | 7.0588 |
| 15 | pfrda_ca2013_ch3 | Chapter III — Prospectus & Allotment of Securities | 6.3742 | 6.3742 |

## Research stream — `phase1_p2_research` (Phase I, Paper 2 — Research stream)

> CAVEAT (Research stream): every topic here carries a flat placeholder weight of 1.0 (DECIDE-30). Zero real PYQ content has been ingested for this stream — DECIDE-31's ingestion only covered the General stream — and per docs/research.md#research-11 (6 coaching sources checked, none cover it), likely never will from a coaching source. Ranking within this stream is currently meaningless: treat it as an unordered topic checklist, not a real priority order.

- Total items in scope: 11
- Uncovered items (coverage = 0, never quizzed): 11 of 11
- At-risk items (weight > median AND coverage < 50%): 0

Showing top 11 of 11:

| Rank | topic_id | name | weight | priority_score |
|---|---|---|---|---|
| 1 | pfrda_descriptive_statistics | Descriptive Statistics (PFRDA Research) | 1.0000 | 1.0000 |
| 2 | pfrda_economic_statistics | Economic Statistics (PFRDA Research) | 1.0000 | 1.0000 |
| 3 | pfrda_hypothesis_testing | Hypothesis Testing (PFRDA Research) | 1.0000 | 1.0000 |
| 4 | pfrda_operations_research | Operations Research (PFRDA Research) | 1.0000 | 1.0000 |
| 5 | pfrda_probability_distributions | Probability Distributions (PFRDA Research) | 1.0000 | 1.0000 |
| 6 | pfrda_probability_theory | Probability Theory (PFRDA Research) | 1.0000 | 1.0000 |
| 7 | pfrda_sampling_techniques | Sampling Techniques (PFRDA Research) | 1.0000 | 1.0000 |
| 8 | pfrda_statistical_computing | Statistical Computing (PFRDA Research) | 1.0000 | 1.0000 |
| 9 | pfrda_statistical_inference | Statistical Inference (PFRDA Research) | 1.0000 | 1.0000 |
| 10 | pfrda_statistical_quality_control | Statistical Quality Control (PFRDA Research) | 1.0000 | 1.0000 |
| 11 | pfrda_time_series_analysis | Time Series Analysis (PFRDA Research) | 1.0000 | 1.0000 |

## Common (all streams) — `phase2_p1` (Phase II, Paper 1 — English descriptive (all streams))

- Total items in scope: 1
- Uncovered items (coverage = 0, never quizzed): 1 of 1
- At-risk items (weight > median AND coverage < 50%): 0

Showing top 1 of 1:

| Rank | topic_id | name | weight | priority_score |
|---|---|---|---|---|
| 1 | pfrda_english_descriptive | English Descriptive Writing — Precis/Essay/Comprehension (PFRDA) | 1.0000 | 1.0000 |

## General stream — `phase2_p2_general` (Phase II, Paper 2 — General stream)

- Total items in scope: 63
- Uncovered items (coverage = 0, never quizzed): 63 of 63
- At-risk items (weight > median AND coverage < 50%): 28

Showing top 15 of 63:

| Rank | topic_id | name | weight | priority_score |
|---|---|---|---|---|
| 1 | pfrda_costing | Costing — Cost/Management Accounting, Lean/Six Sigma (PFRDA) | 32.8464 | 32.8464 |
| 2 | pfrda_companies_act | Companies Act 2013 — Chapters III/IV/VIII/X/XI/XII/XXVII | 32.1047 | 32.1047 |
| 3 | pfrda_finance | Finance — Financial System/Markets/Derivatives/Fiscal Policy (PFRDA) | 31.8523 | 31.8523 |
| 4 | pfrda_pension_sector | Pension Sector — NPS, APY, Annuities (PFRDA) | 30.6427 | 30.6427 |
| 5 | pfrda_commerce_accountancy | Commerce & Accountancy (PFRDA) | 28.0084 | 28.0084 |
| 6 | pfrda_management | Management — Processes, Leadership, HRD, Motivation Theories (PFRDA) | 27.3523 | 27.3523 |
| 7 | pfrda_economics_basic | Economics — UG-level (PFRDA General; NOT linked to postgrad-depth canonical Macro Theory topics) | 27.0713 | 27.0713 |
| 8 | pfrda_ca_cashflow_ratio | Cash Flow Statement, Fund Flow Statement, Financial Statement & Ratio Analysis | 11.0139 | 11.0139 |
| 9 | pfrda_pen_nps | National Pension System (NPS) | 10.9769 | 10.9769 |
| 10 | pfrda_cost_control_analysis | Cost Control & Analysis — Standard Costing, Marginal Costing, Budget & Budgetary Control | 9.8330 | 9.8330 |
| 11 | pfrda_fin_regulatory_bodies | Role & Functions of Regulatory Bodies in the Financial Sector | 8.5493 | 8.5493 |
| 12 | pfrda_ca_standards | Accounting Standards — Depreciation, Inventories, Revenue Recognition, Fixed Assets, Foreign Exchange Transactions, Investments | 8.4081 | 8.4081 |
| 13 | pfrda_mgmt_leadership_styles | Leadership Styles & Theories; Successful vs. Effective Leader | 7.1615 | 7.1615 |
| 14 | pfrda_pen_apy | Atal Pension Yojana (APY) | 7.0588 | 7.0588 |
| 15 | pfrda_ca2013_ch3 | Chapter III — Prospectus & Allotment of Securities | 6.3742 | 6.3742 |

## Research stream — `phase2_p2_research` (Phase II, Paper 2 — Research stream)

> CAVEAT (Research stream): every topic here carries a flat placeholder weight of 1.0 (DECIDE-30). Zero real PYQ content has been ingested for this stream — DECIDE-31's ingestion only covered the General stream — and per docs/research.md#research-11 (6 coaching sources checked, none cover it), likely never will from a coaching source. Ranking within this stream is currently meaningless: treat it as an unordered topic checklist, not a real priority order.

- Total items in scope: 11
- Uncovered items (coverage = 0, never quizzed): 11 of 11
- At-risk items (weight > median AND coverage < 50%): 0

Showing top 11 of 11:

| Rank | topic_id | name | weight | priority_score |
|---|---|---|---|---|
| 1 | pfrda_descriptive_statistics | Descriptive Statistics (PFRDA Research) | 1.0000 | 1.0000 |
| 2 | pfrda_economic_statistics | Economic Statistics (PFRDA Research) | 1.0000 | 1.0000 |
| 3 | pfrda_hypothesis_testing | Hypothesis Testing (PFRDA Research) | 1.0000 | 1.0000 |
| 4 | pfrda_operations_research | Operations Research (PFRDA Research) | 1.0000 | 1.0000 |
| 5 | pfrda_probability_distributions | Probability Distributions (PFRDA Research) | 1.0000 | 1.0000 |
| 6 | pfrda_probability_theory | Probability Theory (PFRDA Research) | 1.0000 | 1.0000 |
| 7 | pfrda_sampling_techniques | Sampling Techniques (PFRDA Research) | 1.0000 | 1.0000 |
| 8 | pfrda_statistical_computing | Statistical Computing (PFRDA Research) | 1.0000 | 1.0000 |
| 9 | pfrda_statistical_inference | Statistical Inference (PFRDA Research) | 1.0000 | 1.0000 |
| 10 | pfrda_statistical_quality_control | Statistical Quality Control (PFRDA Research) | 1.0000 | 1.0000 |
| 11 | pfrda_time_series_analysis | Time Series Analysis (PFRDA Research) | 1.0000 | 1.0000 |

