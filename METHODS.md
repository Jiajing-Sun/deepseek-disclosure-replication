# Methods and coding rules

## Information unit and sample

The content unit is an announcement, a named technology/developer object and a relationship dimension. Adoption, commercial relations, equity holdings, other ties, commercialization, orders and revenue are recorded separately. A statement denying one relationship does not negate unmentioned relationships or adoption of an open model.

The source frame comprises 1,179 abnormal-trading announcements in 2025 Q1. Content screening yields 118 coded announcements from 72 firms; 79 refer to DeepSeek or its developer family. Selection starts from the rule-based filing frame, not a concept-stock list or realized return. Firms are included across industries because the disclosure rule and information definition, rather than an industry taxonomy, define the comparison.

Thirty-eight announcements are first developer-relationship denials within their own firms' abnormal-trading filing sequences. A separate formal-notice check leaves 37 candidates. Earlier records identify five restatements and four scope updates, leaving 28 first-public-denial events. Thus 9/37 = 24.3% describes the fraction reclassified; counting 37 instead of 28 produces an excess of 9/28 = 32.1%. These denominators answer different questions.

## Coding and public-history rules

- Code only explicit statements. An unstated dimension is neither a denial nor evidence of a relationship.
- Preserve the named developer, subject (company, subsidiary, managed fund), relationship dimension, scope and qualifications. A denial of a service agreement is narrower than a denial of all commercial dealings; a denial of participation in financing is narrower than a denial of direct and indirect ownership.
- Distinguish deployment/adoption, testing/adaptation, distribution/hosting and explicit non-involvement. Distribution alone is not coded as adoption.
- Keep the supporting quotation and page reference in external coding inputs. Content recomputation checks that retained attention quotations occur in announcement text.
- Compare each statement with records available earlier; later disclosures do not retrospectively change the information available at an earlier event.
- Treat an earlier equivalent or broader same-dimension denial as a restatement. A new dimension or broadened scope is an update within the developer-family history.
- An earlier record that cannot establish attribution or timing is flagged rather than silently treated as proof of prior disclosure. Absence in searched sources does not prove absence from all public channels.

For code 301299, January 7 marks the retained developer-family history. The report at 15:12 on January 27 supplies the exact High-Flyer object match before the evening filing. The earlier-date field is therefore not universally an exact-proposition novelty timestamp.

The coding was AI-assisted and received independent AI blind recoding. Fourteen labels were revised across 12 announcements; this is not human inter-coder validation. Key classification decisions remain subject to author review. The released code starts from the retained labels and event records; it does not automate the underlying semantic judgment or reconstruct the historical retrieval process.

## Event groups

| Code | Definition |
| --- | --- |
| T1 | First public developer-family commercial or equity denial in the retained record. |
| T1p | Initial filing-sequence denial that restates an earlier equivalent or broader public denial. |
| T2 | A denial that updates scope or adds a relationship dimension to an existing history. |
| R | A later abnormal-trading filing repeating the firm's earlier denial. |
| K | DeepSeek-related corporate facts without a developer denial, before any prior denial. |
| K_after_denial | DeepSeek-related facts without denial, following the firm's denial history. |
| O | Other AI-related corporate content. |
| N | AI-silent filing with earlier AI evidence in the candidate-firm history. |
| X | AI-silent filing outside that prior-AI condition. |
| P | Other firms' abnormal-trading benchmark events; the main comparison uses upward triggers. |

K and P are comparison groups, not randomly assigned untreated controls. Main content comparisons retain A/B timing grades; the population benchmark uses its retained high-confidence event dates. Same-firm filings mapping to the same first tradable date are merged into one company-date event. Display dates, clock times, trigger days, nontrading days and exchange holidays enter the upstream event-date review. The inference code uses the supplied reviewed event date rather than reconstructing it from filing dates alone.

## Return estimation

1. Align stock and CSI All Share closes to the exchange calendar. A simple return requires positive finite closes on adjacent exchange dates. Missing or suspended days are not forward filled, and the program does not bridge missing dates.
2. Estimate `stock_return = alpha + beta * market_return + residual` on trading days −140 through −21. Require at least 90 valid stock–market return pairs.
3. Compute abnormal returns as stock returns minus fitted normal returns. CAR is the sum of daily abnormal returns, not a compounded return. A window with any missing abnormal return is missing, not zero.
4. The main window is [0,2]. Report AR[0], CAR[1,2], CAR[3,20], pre-event windows and the other specified timing sensitivities separately. In the main sample, AR[0] + CAR[1,2] = CAR[0,2].
5. Retain market-adjusted and adjusted-price/total-return-index sensitivities. A request for adjusted vendor prices is not accepted as adjusted data if the returned series is unadjusted.

Prices are raw closes for the main specification. Raw values in full-analysis JSON are return fractions; article JSON and CSV values are percent for CAR and percentage points for differences. Source labels `qfq` and `hfq` identify the vendor's adjustment conventions.

## Matching and inference

Each focal event is compared with the mean of its own eligible benchmark pool. Same-week matching uses ISO week and board group; same-day matching uses date and board group, with a same-week fallback if the day pool is empty. Focal-event differences are averaged with equal event weights. Pool observations can be reused; the mean of a union of controls is not the matching estimator.

Event-equal intervals use CR1 event-date clustering and a Student t reference with G−1 degrees of freedom. Date-equal results first average events within each date and then equally weight date means. The latter changes the estimand, not just its standard error. Wild cluster tests impose the null and use Rademacher weights; all sign patterns are enumerated with at most 16 clusters, otherwise the random seed is fixed. The main workflow reports these tests for comparisons with at least 10 date clusters.

Supplementary comparisons exclude benchmark company answers displayed before 00:00 on the event date, or additionally match the previous closing-limit state. A keyword in the investor question alone is insufficient. Empty restricted pools are omitted, not assigned a zero return.

Closing-limit flags apply sample-period board rules and prices rounded half-up to cents. They identify closing at a calculated limit, not intraday limit touches. Later-period events and other disclosure types are separately listed rather than pooled into main inference.

## Specification provenance

The original internal plan was frozen before content-group return comparisons, but pooled diagnostics and event-date repair comparisons had already been viewed. This is not an external preregistration. The full analysis preserves both same-week and same-day matching, corrected and archived heterogeneity definitions, and explicitly labeled post-hoc exploration. Content classification is not selected by return direction or significance. Public repository preparation changes documentation, paths and verification around the analysis; it does not change the retained sample or estimators.
