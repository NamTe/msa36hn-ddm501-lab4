# Lab 4 — Monitoring and Production Deployment: Analysis

## 1. Purpose and experimental evidence

This experiment evaluates whether production monitoring can detect changes in a credit-risk service when requests still succeed. Accuracy cannot be measured immediately because repayment outcomes arrive later, and declined applications do not produce repayment labels. Input drift, prediction scores, decision mix, and group selection rates therefore provide signals for investigation rather than proof of model failure.

The evidence comprises three runs of 400 predictions: normal, drifted at strength 1.0, and unfair. Each run returned HTTP 200 for all 400 scored requests. The screenshots display model version 1.0.0 throughout. Each saved monitoring response contains a final window of 400 and `sufficient_data: true`, exceeding the minimum of 200. The reference is generated from the training split using quantile bins with open outer edges; it provides the fixed baseline for PSI.

The analysis uses the saved run logs for exact decision counts and client latency, the monitoring JSON files for drift and fairness, and the dashboard screenshots for visual trends. The logs do not record the exact command, seed, delay, or reset procedure, so those settings cannot be independently established from the captures. No mild-drift run is included. An additional alert screenshot records the evaluated rule states.

## 2. Results across the three profiles

Percentages below are calculated from the recorded counts or JSON values. A fairness gap is expressed in percentage points (pp); selection means REVIEW or DECLINE, not approval.

| Measurement | Normal | Drifted (strength 1.0) | Unfair |
|---|---:|---:|---:|
| Successful predictions | 400/400 | 400/400 | 400/400 |
| Final window size | 400 | 400 | 400 |
| Maximum feature PSI | 0.0301 | 4.2510 | 0.3526 |
| Drift classification | Stable | Significant | Significant |
| Mean prediction score | 0.2355 | 0.5897 | 0.3966 |
| Median prediction score | 0.1632 | 0.6398 | 0.2576 |
| APPROVE | 311 (77.75%) | 62 (15.50%) | 209 (52.25%) |
| REVIEW | 57 (14.25%) | 119 (29.75%) | 63 (15.75%) |
| DECLINE | 32 (8.00%) | 219 (54.75%) | 128 (32.00%) |
| Group 1 selection rate | 23.45% | 86.90% | 93.79% |
| Group 2 selection rate | 21.57% | 83.14% | 21.57% |
| Fairness gap | 1.88 pp | 3.76 pp | 72.22 pp |
| Client-observed p95 latency | 1019.8 ms | 991.1 ms | 1018.7 ms |

**Normal traffic establishes the baseline.** All six feature PSI values are below 0.10. AGE has the largest PSI at 0.0301, while utilisation_ratio is 0.0288. Most applications are approved, and the selection-rate gap is small. This supports stability relative to the reference for this sample; it does not establish accuracy or fairness in general.

**Full drift changes both inputs and decisions.** Mean predicted risk increases by 0.3542, and the decline share rises by 46.75 pp. Manual reviews increase from 57 to 119. All six monitored features exceed PSI 0.25. The largest shifts are payment_ratio (4.2510), utilisation_ratio (3.0921), and LIMIT_BAL (2.0426). Both groups have substantially higher selection rates, while their gap remains below the 10 pp alert threshold. The service continues to return successful predictions despite a population that differs strongly from training.

**The unfair profile concentrates the change in one group.** Group 1 selection rises by 70.34 pp, from 23.45% to 93.79%, while group 2 remains at 21.57%. The gap increases from 1.88 to 72.22 pp. Drift is concentrated in max_delay (0.3526), payment_ratio (0.2879), and PAY_0 (0.2791); AGE, LIMIT_BAL, and utilisation_ratio retain their normal-run PSI values. This agrees with the generator's deliberate modification of payment histories and payment amounts for group 1.

## 3. Which signal moved first, and which explained the problem?

In these screenshots, score and decision curves are visible before drift and fairness become available. This is expected: drift and fairness wait for at least 200 observations, whereas prediction histograms and counters start accumulating immediately. The initial zero drift line must not be interpreted as evidence of stability before that minimum is reached.

The captures demonstrate detection, but do not establish that PSI preceded a small change in decisions. The only drifted run uses full strength, where both input and output changes are already large. A mild-drift run at strength 0.05 with timestamped observations would be needed to quantify how much input drift becomes detectable before a material decision shift. The leading-signal argument supported here is that these metrics are available before delayed repayment labels, not that PSI necessarily appears first on every chart.

Per-feature PSI explains **what changed**, while group selection rates explain **who was affected**. The aggregate drift scores in these actual runs are not similar: 4.2510 for full drift versus 0.3526 for unfair traffic. Nevertheless, both receive the same significant-drift classification. That classification alone cannot distinguish broad population change from a concentrated group disparity. The fairness gap provides that distinction: 3.76 pp versus 72.22 pp.

## 4. Which signals would alert?

The following interpretation uses the repository's configured rules. Crossing a threshold is different from satisfying its continuous `for:` duration. A firing alert also does not prove that a notification was delivered.

| Rule | Configured condition and duration | Interpretation of captured evidence |
|---|---|---|
| ModerateFeatureDrift | PSI > 0.10 for 15 min; warning | Drifted and unfair snapshots exceed the threshold. |
| SignificantFeatureDrift | PSI > 0.25 for 15 min; critical | Both changed profiles are candidates for critical escalation if sustained. |
| FairnessGapWidened | Gap > 0.10 for 20 min; critical | Only unfair traffic exceeds the threshold. |
| DecisionMixShift | 30-minute decline-rate ratio > 20% for 30 min; warning | Run-level decline shares exceed 20% for drifted and unfair traffic; the alert screenshot confirms a pending state, but not firing. |
| HighLatencyP95 | HTTP histogram p95 > 0.5 s for 5 min; warning | Service Health plots exceed 0.5 s during traffic in all three profiles. |

The moderate-drift rule has no upper bound, so both drift rules can be active for significant drift. The alert screenshot (Figure 1) shows 12 rules: 4 pending and 8 normal, with none firing. DecisionMixShift is pending for 15 minutes; FairnessGapWidened and both drift rules are pending for 12 minutes. These are shorter than their respective 30-, 20-, and 15-minute hold periods. HighLatencyP95 is normal at capture time; the earlier latency plots do not establish its alert state at that earlier time. Drift and fairness gauges can retain their last window values after traffic stops, whereas rate-based queries change as observations leave their lookback windows; a sustained gauge is not proof of continuing traffic.

Availability remained visible as `Service up = 1` and `Model loaded = 1` in the screenshots. However, availability does not imply acceptable performance. Normal and unfair Service Health captures show p95 summary values of about 1.22 s and 1.37 s. The drifted capture shows 4.75 ms after prediction traffic has subsided, while its earlier time-series values are much higher. That final card is not evidence that drift improved prediction latency.

Client p95 values near one second and Grafana histogram estimates are different measurements: the client measures complete request duration, while Grafana estimates quantiles from buckets over a rolling window and can aggregate multiple endpoints. They should not be equated. These observations warrant a separate latency investigation; the captures do not establish its cause.

## Figure 1. Alert evaluation: four pending rules

All 12 rules are loaded: 4 pending, 8 normal, none firing. DecisionMixShift is pending for 15 minutes; FairnessGapWidened and both drift rules for 12 minutes. The configured hold periods have not yet elapsed.

![Figure 1. Alert evaluation: four pending rules](alert.png)

## Figure 2. Normal traffic: stable inputs

PSI 0.0301; window 400; fairness gap 1.88 percentage points.

![Figure 2. Normal traffic: stable inputs](normal-run-model-behaviour.png)

## Figure 3. Drifted traffic: broad population shift

PSI 4.2510; window 400; fairness gap 3.76 percentage points.

![Figure 3. Drifted traffic: broad population shift](drifted-run-model-behaviour.png)

## Figure 4. Unfair traffic: concentrated group disparity

PSI 0.3526; window 400; fairness gap 72.22 percentage points.

![Figure 4. Unfair traffic: concentrated group disparity](unfair-run-model-behaviour.png)

## Figure 5. Normal traffic: service health

Service and model available; elevated HTTP latency during predictions.

![Figure 5. Normal traffic: service health](normal-run-service-health.png)

## Figure 6. Drifted traffic: service health

The low final latency card follows the end of prediction traffic; earlier latency is elevated.

![Figure 6. Drifted traffic: service health](drifted-run-service-health.png)

## Figure 7. Unfair traffic: service health

Service and model available; elevated HTTP latency despite successful predictions.

![Figure 7. Unfair traffic: service health](unfair-run-service-health.png)
