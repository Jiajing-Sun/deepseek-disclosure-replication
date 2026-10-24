# Data and availability

## Included derived data

All three JSON files are in the repository root. Company identifiers refer to listed companies, not individuals.

| File / object | Unit and interpretation |
| --- | --- |
| `article_data.json` → `event_rows` | 28 company-date events. `code` is a six-digit string; `t0` is the first tradable event date; `week_n` and `day_n` are benchmark pool sizes. `car` is CAR[0,2] in percent; `week_diff` and `day_diff` are percentage-point differences. |
| `article_data.json` → `core` | Event-equal mean and date-clustered interval (`mean`, `ci`); date-equal mean and interval (`date_mean`, `date_ci`); event and date counts (`n`, `dates`). |
| `article_data.json` → `comparisons` | Same-week, same-day and supplementary matching summaries. `mean_pp`, `ci_pp`, `date_mean_pp`, `date_ci_pp` are percentage-point quantities. `pool_sizes` follows the estimation ordering, so use the event rows to identify individual event pools. |
| `content_evidence.json` → `adoption_by_denied_dimension` | Counts of commercial-only, equity-only and joint denials within each adoption category, totaling 38 filings. |
| `content_evidence.json` → `attention_reference_types` | Mutually exclusive classifications of the quoted disclosure context. `none` denotes no retained attention quotation. |
| `content_evidence.json` → `history_timing` | Nine earlier-history cases: company code, classification, earlier date, event date and count of exchange dates between them. The legacy field `sessions_before_event` counts dates, not elapsed full trading sessions. |
| `content_evidence.json` → `roles` | Descriptive event counts, date counts, means and intervals by information role. Return means are percent. `precar_events` can be smaller because of missing pre-event windows. |
| `historical_evidence.json` | Case identifiers, reviewed classification, filing display date and earlier-record date/source URL. Complete source texts and internal review notes are not included. |

`source_directory` in the article snapshot is a provenance description, not a path to a bundled raw dataset. The Python code contains English paraphrases for the historical-case table. Original public-source links may change or require access through the source platform.

## External inputs for full mode

The manifest lists 27 required filenames, byte sizes and SHA-256 hashes of the frozen inputs used for this release. Hashes identify exact research inputs; they do not grant distribution rights. The runner deliberately fails on missing or changed inputs instead of substituting snapshot results.

| Files | Purpose and core fields |
| --- | --- |
| `daily_prices.jsonl`, `frame_daily_prices_raw.jsonl`, `extended_firms_daily_prices_raw.jsonl`, `extension_daily_prices_raw.jsonl` | Daily prices by `symbol`, ISO `date`, `adjustment_requested`, `series_returned`, `close`; main-period records also supply `turnover_pct`. Prices must be positive for a valid adjacent-date return. Raw records use `adjustment_requested="raw"`; adjusted requests retain the actual returned-series identifier. |
| `csindex_H00985.jsonl` | Total-return-index sensitivity: ISO `date` and `close`. The main raw benchmark and exchange calendar are identified by `symbol="sh000985"` in the daily-price inputs. |
| `coding_documents.jsonl` | Announcement-level content coding. Identifiers: `announcement_id`, `code`, `name`, `board`, `t0_final`. Dimensions: `adopt`, `biz`, `eq`, `tie`, `prod`, `order`, `rev`, with associated quote/page/scope fields. Also uses `content`, `deepseek_related`, `supplementary_outside_keyword_set` and `market_attention_quote`. Unstated dimensions retain their original Chinese code value. |
| `document_novelty.jsonl` | Within-firm history labels keyed by `announcement_id`. `novelty_within_candidate_docs` beginning with `C1` selects the 38 first filing-sequence denials. |
| `documents_candidate_firms_groups.jsonl` | `announcement_id` → final `doc_group`, with reviewed date, timing grade and direction. |
| `events_candidate_firms.jsonl` | Merged company-date events: `event_key`, `code`, `name`, `board`, `board_group`, `t0`, `week`, `group`, semicolon-delimited `announcement_ids`, `timing_grade_worst`, `direction`, novelty/adoption and other-news flags. |
| `events_population.jsonl` | Benchmark events using the same date, board and key fields, with group P and trigger direction. |
| `announcement_text_pages.json` | JSON mapping announcement identifiers to lists of page records containing `text`, used for exact quotation checks and wording counts. |
| `ai_candidates.jsonl` | Screened announcement candidates with a `hits` list; each hit includes `keyword`. |
| `frame_audit.json`, `screening_audit.json` | Source-frame counts including `unique_ids`, `eligible_documents`, `downloaded_and_parsed`. |
| `frame_sohu_differences.jsonl` | Cross-vendor price discrepancies identified by `symbol`; an empty file means none are retained in this release. |
| `population_ai_adjacent_docs.json` | `announcement_ids` for the adjacent-topic exclusion sensitivity. |
| `extended_first_denials.jsonl`, `prior_record_review.json` | Other disclosure types and their earlier-record review, including code, title, event date, timing grade and novelty decision. |
| `p_pool_qa_hits.jsonl` | Retrieved Q&A evidence keyed by company `code`, with `answer_display_time` and boolean `deepseek_in_answer`. Display times are local China time in sortable `YYYY-MM-DD HH:MM:SS` form. |
| `p_pool_qa_flags.csv` | Event-level earlier-answer flags and retained evidence times; includes `event_key`, `code`, `name`, `t0`, `ds_prior_answer`, `evidence_answer_display_times`. |
| `limit_streaks.csv` | Event keys and reviewed `limit_up_m1_rule`; used for previous closing-limit matching. |
| `extension_events.csv` | Later-period candidate events, including `code`, `name`, `group`, `t0`, `flag_generic_developer_object`. Generic-object denials remain separate from named-developer T1 events. |
| `baseline_main_results.json`, `baseline_content_tables.json` | Archived nested result objects for complete numerical comparison. |
| `baseline_event_returns_candidate_firms.jsonl`, `baseline_event_returns_population.jsonl` | Archived per-event model output, including event keys, attributes, daily abnormal returns, windows and completeness indicators. |
| `baseline_event_level_returns.csv` | Archived focal-event extraction, including group, code, date, board, CAR and same-week/same-day differences. Used by the independent audit after recomputed event records have been checked. |

JSON Lines files contain one object per nonblank line. Read CSV files with UTF-8 BOM support and preserve security codes as strings. Do not infer classification from the English display labels or replace missing values by zero. The original Chinese coding literals in the scripts are intentional compatibility keys; the explanatory documentation and comments are English.

## Provenance and access

The research inputs originate from corporate announcements on CNINFO, exchange Q&A records and public reproductions, dated media reports, market-price services, and CSI index records. The main-price provider is Tencent; the research package also retains cross-source price checks. These external inputs and their upstream retrieval archives are held separately from this public code release. Obtaining similarly named data today need not reproduce the historical records or their hashes.

The MIT license covers the authored code, not third-party documents or provider databases. This repository contains no API keys, authentication cookies, university student records, full-text reference library or submission correspondence. It provides derived-data replication immediately and complete analysis code conditional on access to the external inputs. An independently reconstructed input set requires a separately documented validation exercise rather than a claim of exact frozen-input replication.
