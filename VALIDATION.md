# Release validation

Checks completed on 24 October 2026 for the Python release accompanying the current manuscript.

| Check | Observed result |
| --- | --- |
| Exact external input verification | All 27 filenames and SHA-256 digests matched the frozen release manifest. |
| Complete return estimation | Passed from the external price and event inputs. |
| Main nested analysis results | Zero differences from the archived baseline, at 1e-9 relative/absolute numerical tolerance. |
| Content tables | Zero differences from the archived baseline. |
| Candidate-firm event records | All fields in 142 event records matched the archive. |
| Population event records | All fields in 1,019 event records matched the archive, including incomputable and non-upward events. These are not all members of the 803-event upward-triggered benchmark. |
| Corrected earlier-answer exclusions | Same-week mean 8.8618280846 pp; same-day mean 4.3923242923 pp. |
| Public snapshot verification | Recovered the 28-event, 12-date main and matched means/intervals; content, history and AR-window identities passed. |
| Snapshot versus complete workflow | Six LaTeX table files, two CSV files and `content_evidence.json` were byte-identical. |
| Missing-price behavior | A missing close prevents returns across both adjacent dates; no suspension bridging. |
| Known synthetic market model | Recovered the imposed alpha, beta and abnormal return; an incomplete CAR window stayed missing. |
| Weighting | Unequal daily event counts correctly produced distinct event-equal and date-equal means. |
| Language and syntax | All 15 Python modules parsed; comments and docstrings contain no Chinese prose. Original Chinese data literals remain. |
| Release-content scan | No local home-directory paths, student identifier, detected credential assignment, known token pattern or private-key header in release files. |

The complete run used Python 3.12 with the package versions pinned in `requirements.txt`. It completed in approximately 30 seconds on the preparation machine; execution times depend on hardware and numerical libraries. Formatting was subsequently standardized and the deterministic method checks rerun. Formatting does not change estimator behavior.

Both workflow modes generate their own logs, numerical check reports and `replication_report.json` in the selected output directory. Failed stages raise an error and preserve available logs. The runner does not silently fall back to snapshot mode when complete inputs are missing.

These results establish reproducibility conditional on the retained inputs and internal consistency of the public derived data. They do not establish human validation of coding, completeness of historical web coverage, redistribution permission for external databases, or causal identification of price effects. The nine history classifications and key content labels still require human author review.
