# DeepSeek disclosure: relationship scope and public histories

Python replication code for **Denying the Developer, Not the Technology: Relationship Scope and Cross-Channel Histories in Corporate AI Disclosure**, by **Xi Zhang, Jiajing Sun and Junda Wu**. Jiajing Sun and Junda Wu are joint corresponding authors.

The study treats an information event as a bounded relationship proposition together with its public history across channels. Among 38 first relationship denials within firms' abnormal-trading filing sequences, 18 also report technology adoption or deployment. Cross-channel evidence separates five restatements and four scope updates from 37 candidates, leaving 28 first-public-denial events on 12 trading dates.

All source files are Python and sit at the repository root. Explanatory comments, docstrings and documentation are in English. Original Chinese coding labels, search expressions and company names remain unchanged as research data.

## Run the public replication

Use Python 3.12. Install the pinned packages in a virtual environment **outside this checkout**, then run:

```bash
python3 -m venv ../disclosure-venv
source ../disclosure-venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest test_methods.py
python run_all.py --mode snapshot --output-dir ../disclosure-snapshot
```

Windows users can activate the same environment with `..\disclosure-venv\Scripts\activate`.

The output directory must be new or empty. It is flat: six LaTeX tables, two vector PDF figures, two CSV tables, numerical-check reports and execution logs. LaTeX is not needed to generate these assets. The table fragments use the manuscript's LaTeX environment and are not standalone documents.

**Snapshot mode is fully runnable with this repository.** It independently reconstructs the main event-equal and date-equal estimates and their confidence intervals from the 28 released event rows, checks content and history accounting, and regenerates article assets. It uses archived content summaries and estimated returns; it does not re-estimate returns from market prices or redo source-document coding.

## Run the complete estimation

The complete Python analysis is included. Its 27 external input files comprise prices, coded documents, event classifications, evidence checks and archived numerical baselines. They are described in [DATA_DICTIONARY.md](DATA_DICTIONARY.md); exact release hashes are in [external_inputs_manifest.json](external_inputs_manifest.json).

Once those inputs are available in one directory:

```bash
python run_all.py --mode full \
  --data-dir /path/to/external-inputs \
  --output-dir ../disclosure-full
```

Full mode verifies input hashes, estimates returns, calculates matched comparisons and uncertainty, checks complete event records against their archived baselines, reconstructs diagnostic results, recomputes the content tables and produces the article assets. It stages inputs read-only in a temporary flat workspace. Neither mode writes into the source-data directory, and no run downloads data or calls an AI service.

**Raw market-price series, complete announcement texts and underlying Q&A archives are not distributed here.** Public-source accessibility does not establish redistribution rights. Full estimation therefore requires separately obtained inputs in the documented schemas; this release does not claim unrestricted availability of those inputs. The public JSON files contain derived article results and selected source metadata. No credentials, student records, manuscript correspondence or submission documents are included.

## File guide

| File | Purpose |
| --- | --- |
| `run_all.py` | Safe entry point for snapshot and complete replication; exports flat outputs and logs. |
| `common.py` | Shared file readers, security identifiers, exchange calendar and date parsing. |
| `content_tables.py` | Content-only sample formation, denial breadth, adoption and wording statistics. |
| `event_study.py` | Adjacent-day returns and OLS market-model abnormal returns. |
| `stats_util.py` | CR1 date-clustered inference, date-equal estimates and wild cluster tests. |
| `main_analysis.py` | Event returns, matching, group contrasts, comparability and labeled exploratory analyses. |
| `supplementary_analysis.py` | Earlier-answer exclusions, prior closing-limit matching and separate later-period listings. |
| `revision_audit.py` | Independent archived-event audit, matched-pool reconstruction and timing corrections. |
| `verify_outputs.py` | Complete nested comparison of newly estimated main/content results with archived baselines. |
| `verify_event_records.py` | Check every field in newly estimated candidate and population event records. |
| `verify_snapshot.py` | Independently recover article means and intervals and verify accounting identities. |
| `prepare_content_evidence.py` | Content combinations, public-history timing and information-role tables. |
| `prepare_assets.py` | Main and supplementary price tables, two figures and the event CSV. |
| `prepare_detail_tables.py` | Nine historical cases and date-composition diagnostics. |
| `test_methods.py` | Deterministic checks for suspension handling, known abnormal returns and weighting. |
| `article_data.json` | Derived 28-event results and main/supplementary numerical summaries. |
| `content_evidence.json` | Derived content combinations, history timing and descriptive return roles. |
| `historical_evidence.json` | Nine case identifiers, classifications, dates and public source URLs. |
| `DATA_DICTIONARY.md` | Units, schemas, input requirements and source-availability boundaries. |
| `METHODS.md` | Event definitions, coding rules, estimator and inference details. |
| `VALIDATION.md` | Checks actually run for this release and what they establish. |

The public runner is the recommended entry point. The lower-level estimation scripts expect inputs beside the script and are intended to run in its temporary workspace. Chinese legacy labels in full-analysis outputs preserve exact baseline comparisons; article table labels are English.

## Reading the estimates

The mean CAR[0,2] is **10.72%**, with a date-clustered 95% interval of **[1.93%, 19.50%]**. The same-week matched difference is **8.85 percentage points [−0.55, 18.25]**, and the same-day difference is **4.50 percentage points [−2.41, 11.41]**. The matched differences are descriptive conditional comparisons; neither interval excludes zero. These calculations support the paper's distinction between content, public novelty and the trading environment, rather than identifying a causal price effect of denial.

The event is defined by content and earlier public records, never by the sign of its return. The four scope updates contain new propositions within an existing developer-family denial history. Human review of the key coding decisions remains outstanding; existing independent recoding was AI-assisted. Numerical reproduction does not substitute for that review.

## Citation and reuse

Use [CITATION.cff](CITATION.cff) for author and repository metadata. This is the code accompanying a manuscript, not a claim of journal publication. The MIT license applies to repository code. Source URLs and derived research data do not grant rights to third-party source documents or price databases. See [DATA_DICTIONARY.md](DATA_DICTIONARY.md) for provenance.
