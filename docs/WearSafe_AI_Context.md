# WearSafe AI — Complete Project Context

*Context handoff for continuing the project. Rebuilt as Markdown from the original WearSafe_AI_Full_Context_for_Claude.docx.*

This document consolidates the project definition, product positioning, technical architecture, dataset strategy, data design, model plan, evaluation methodology, prototype scope, startup framing, competition positioning, investor concerns, and recommended implementation workflow that have been discussed and finalized so far.

## 0. How Claude should use this document

- Treat the decisions marked as FINAL / FROZEN as current project decisions unless the user explicitly changes them.
- Do not silently reframe the system as a confirmed attack detector. The scientifically valid claim is potential physical-danger / safety-anomaly detection.
- Do not create fake attack labels from stress or fall data.
- Do not pair motion from one person/dataset with heart data from another and treat them as synchronous observations.
- Prefer subject-independent evaluation and false-alert analysis over random window-level train/test splits.
- When proposing changes, distinguish clearly between current design, optional experiments, and future work.

## 1. Project identity and one-line definition

Working name: WearSafe AI

Core definition: An AI-powered wearable personal-safety system that uses ordinary smartwatch motion and heart-related signals to identify potential physical-danger patterns and trigger a user-confirmation and emergency-response workflow.

The intended real-world target is physical attacks / dangerous physical incidents. However, because reliable public datasets of real assaults recorded with synchronized smartwatch sensors are not readily available, the ML system is framed as a potential safety-anomaly / danger detector rather than a confirmed assault classifier.

## 2. Problem statement

Most existing personal-safety systems are reactive: the user must press an SOS button, unlock a phone, call someone, or manually share location. During an actual physical threat, the user may be unable to do so.

Modern and even affordable wearables commonly expose motion sensing and optical heart-rate sensing. The opportunity is to interpret these signals together so that the system can recognize suspicious combinations without treating ordinary exercise or emotional stress as danger.

## 3. Core product hypothesis

High motion alone is not danger. High heart rate alone is not danger. The useful signal is the combination of abrupt / irregular movement, physiological arousal, and activity context.

| Motion | Physiological arousal | Interpretation | Expected product behavior |
| --- | --- | --- | --- |
| Low | Low | Normal | No alert |
| Low | High | Stress / panic / excitement | Monitor; not physical-danger by itself |
| High | Low or expected | Exercise / active ADL | Suppress or lower risk |
| High + abrupt/irregular | High or rising | Possible danger | Safety check / escalation workflow |

## 4. User story and product behavior

Target persona: a student, solo commuter, late-shift worker, or person moving alone through an unfamiliar or potentially unsafe environment.

Trigger example: the wrist suddenly shows chaotic movement, the physiological signal indicates elevated arousal, or PPG becomes unreliable due to intense movement.

System response: WearSafe vibrates / prompts 'Are you safe?'. If the user cancels, nothing happens. If the user does not respond within a short confirmation window, the phone initiates a mock or real SOS workflow, including emergency contacts and location in later product stages.

## 5. Scientific claim boundary

### What we claim
- Detect unusual combinations of abrupt wrist movement and physiological arousal.
- Estimate a potential danger / safety-anomaly score.
- Use activity context to reduce false alarms.
- Prototype an end-to-end wearable safety workflow.

### What we do NOT claim
- That the model legally proves an attack occurred.
- That public stress or fall datasets contain real assault ground truth.
- That high heart rate alone indicates danger.
- That a fall, stress episode, or vigorous exercise is equivalent to an attack.

## 6. Product scope and hardware strategy

FINAL / FROZEN sensor strategy:
- Mandatory / minimum: wrist accelerometer.
- Mandatory / minimum: optical heart-rate / PPG-derived heart-rate signal.
- Optional enhancement: gyroscope.
- Not required for MVP: ECG, EDA, skin temperature, SpO2.
- GPS is useful for SOS location but is not required as an ML input.

The product should ultimately work as a software layer on existing watches rather than requiring proprietary hardware. The first prototype does not require a physical smartwatch; dataset replay can simulate the live stream.

## 7. Full product architecture

Data source → sensor ingestion → preprocessing → feature extraction → component ML models → fusion / risk scoring → user confirmation → emergency escalation.

- Data sources: public datasets, replay simulator, and later a real smartwatch API.
- Motion branch: wrist ACC, optional gyro.
- Physiology branch: PPG/HR and derived arousal features.
- Context branch: stationary / locomotion / vigorous activity or equivalent context representation.
- Fusion engine: combines component scores and signal-quality status.
- Alert engine: safety-check prompt, cancellation, no-response escalation.

## 8. Dataset strategy — FINAL v1

The project should not create one giant fake 'attack dataset'. Instead it uses multiple datasets as evidence for different measurable components.

| Dataset | Primary role | Wrist ACC | Gyro | PPG/HR | Notes |
| --- | --- | --- | --- | --- | --- |
| PPG-DaLiA | Normal real-life multimodal context + false-alarm benchmark | Yes | No | BVP/PPG | Strong hard negatives such as cycling, stairs, table soccer. |
| WESAD | Physiological arousal / stress | Yes | No | BVP/PPG | Baseline, stress, amusement; stress is not attack. |
| BITS-2 | Synchronous abrupt-motion + HR bridge dataset | Yes | Yes | HR | Useful because motion and HR are from the same trial/person; falls remain proxy events. |
| UP-Fall | External motion validation | Yes | Yes | No | Wrist IMU intended to simulate smartwatch usage. |
| FallAllD | Optional larger abrupt-motion source | Yes | Yes | No | Useful later; not required for MVP v1. |

## 9. Why BITS-2 matters

BITS-2 is especially useful because it provides wrist IMU and heart-rate measurements from the same trial. That allows genuine synchronous analysis of abrupt events and physiological response without fabricating cross-dataset pairs.

It should still be treated as abrupt-event / fall-proxy data, not real attack ground truth.

## 10. Dataset roles

- PPG-DaLiA: What does legitimate everyday movement + heart behavior look like? Also used to measure false alerts during normal life.
- WESAD: What does physiological arousal / stress look like at the wrist?
- BITS-2: What do synchronized abrupt-event motion and HR dynamics look like?
- UP-Fall: Does the motion detector transfer to an external wrist-IMU dataset?
- FallAllD: Optional larger wrist abrupt-motion training / validation source after the MVP pipeline is stable.

## 11. Dataset design philosophy

Use a common logical schema, but do not force every dataset into one physical CSV with invented values. Keep data modular and preserve source-specific information.

Three storage layers are recommended:
- Layer A — normalized raw signals.
- Layer B — synchronized windows.
- Layer C — feature tables for classical ML.

## 12. Layer A — normalized raw signal schema

- recording_id
- dataset
- subject_id
- trial_id / session_id
- activity_label / original label
- event_type
- sensor_location
- sensor_name
- sampling_rate
- timestamp
- x, y, z for vector sensors
- scalar_value for BVP / HR / other scalar signals
- original_unit
- canonical_unit

## 13. Layer B — synchronized window schema

- window_id, dataset, namespaced subject_id, trial_id
- window_start, window_end, duration
- original activity/state label
- derived context_class
- derived motion_event_class
- derived arousal_class
- acc[], optional gyro[], optional bvp[], optional hr[]
- sampling rates per modality
- availability flags: has_acc, has_gyro, has_bvp, has_hr
- signal-quality fields / missingness indicators

## 14. Layer C — feature table

### Motion features
- acceleration magnitude mean/std/max/p95/RMS
- acceleration range
- jerk mean/std/max
- motion energy
- dominant frequency
- spectral entropy
- spectral energy

### Gyroscope features
- gyro magnitude mean/std/max
- rotation energy

### Physiology features
- HR mean/std/min/max
- HR delta
- HR slope
- relative HR vs recent baseline
- BVP peak rate / inter-beat interval features when raw BVP is available
- PPG signal-quality score
- missing / uncertain physiology flag

## 15. Labels — keep them separate

FINAL label design:

| Label | Meaning | Examples |
| --- | --- | --- |
| original_label | Untouched source label | walking, table_soccer, stress, fall_forward |
| context_class | Coarse legitimate activity context | stationary, low_activity, locomotion, vigorous_activity |
| motion_event_class | Motion branch ground truth | normal_adl, abrupt_event_proxy |
| arousal_class | Physiological state | low_arousal, high_arousal |

There is intentionally no attack ground-truth label in Data Design v1.

## 16. Context label proposal

| Original | Proposed context |
| --- | --- |
| Sitting | stationary |
| Working | low_activity |
| Driving | low_activity |
| Walking | locomotion |
| Stairs | vigorous_activity |
| Cycling | vigorous_activity |
| Table soccer | vigorous_activity / irregular hard negative |
| Lunch | mixed / low_activity, to be decided after inspection |

## 17. Hard negatives

Hard negatives are normal activities that resemble danger. They are essential because the system must not fire on exercise or active daily life.
- table soccer
- stairs
- cycling
- running/jumping when available
- amusement / non-danger high arousal

## 18. Windowing strategy — task specific

Earlier we considered using one universal 5-second window. The current design improves this by using task-specific temporal scales.

| Task | Initial window | Overlap / clock | Reason |
| --- | --- | --- | --- |
| Motion event | 2 s | 50% overlap initially | Abrupt movement happens quickly. |
| Activity/context | 5 s | 50% overlap initially | Enough context for daily activity. |
| Arousal | 30 s | Compare 10/30/60 s | Physiological response evolves more slowly. |

Real-time fusion can run on a common decision clock (e.g. every 1 second) while each branch looks back over a different history length.

## 19. BITS-2 special event-centered representation

In addition to sliding windows, BITS-2 should have an event-centered representation because HR is lower-rate and the most useful analysis may be before-event vs during-event vs after-event.
- event_id, subject_id, activity
- event_start / event_peak / event_end
- pre_event_hr_mean
- event_hr_mean
- post_event_hr_mean
- hr_delta_pre_to_post
- peak_acc, peak_jerk, motion_energy, gyro_energy
- proxy event label

## 20. Units and sampling

Canonical units should be explicit and recorded:
- acceleration → m/s^2
- gyroscope → rad/s
- heart rate → bpm
- time → seconds

Do not globally force all sensors to one sampling rate. Normalize within model branches when useful.

Initial motion canonical rate can be explored around 20–32 Hz, because BITS-2 is lower-rate and future low-power wearable deployment matters. PPG-DaLiA / WESAD BVP should initially remain at their native 64 Hz for peak detection and signal-quality work.

## 21. Data directory proposal

```
data/
  raw/
    ppg_dalia/
    wesad/
    bits2/
    upfall/
    fallalld/
  interim/
    <dataset>/normalized_signals/
    <dataset>/windows/
  processed/
    context/features.parquet
    arousal/features.parquet
    motion/features.parquet
    fusion_validation/ppg_dalia.parquet
    fusion_validation/bits2_events.parquet
metadata/
  subjects.parquet
  recordings.parquet
  label_map.parquet
splits/
  <dataset>_v1.json
```

## 22. Subject IDs and leakage prevention

Subject IDs must be namespaced, e.g. PPGDALIA_S01, WESAD_S01, BITS2_S01. Do not use random window-level splitting.

Required evaluation policy:
- Subject-independent train/validation/test splits.
- For 15-subject datasets, consider LOSO (Leave-One-Subject-Out) for final reporting.
- No subject may appear in more than one split.
- Cross-dataset validation should remain separate from tuning.

## 23. ML architecture

The current design uses component models before fusion:
- Context model: estimates stationary / locomotion / vigorous activity or comparable context.
- Motion model: normal ADL vs abrupt-event proxy.
- Arousal model: baseline / low arousal vs stress / high arousal.
- Fusion engine: combines motion score, arousal score, context, and signal quality into a danger score.

## 24. Modeling progression

Do not begin with deep learning. Recommended order:
1. Rule / threshold baseline.
2. Logistic regression.
3. Random forest.
4. XGBoost after the baseline pipeline is stable.
5. Optional 1D CNN / LSTM / temporal deep model only after classical baselines are understood.

## 25. Fusion strategy

Start with rule-based late fusion, not an opaque learned fusion model.

Example logic: high motion anomaly + high arousal + context not explained by vigorous exercise → high risk. High motion + unreliable PPG should not be interpreted as 'no arousal'; it should remain uncertain.

Later compare rule-based fusion with learned fusion if a valid synchronous training/evaluation design is available.

## 26. PPG motion-artifact issue

Strong wrist movement can corrupt optical PPG exactly when the system most cares about the physiological signal. Therefore signal quality is a first-class feature, not a side note.

If PPG quality is poor during intense motion, the fusion layer should represent physiology as unavailable/uncertain rather than forcing a misleading heart-rate estimate.

## 27. Evaluation metrics

Accuracy alone is not sufficient.
- Motion branch: precision, recall, F1, PR-AUC, ROC-AUC, per-subject performance.
- Arousal branch: precision, recall, F1, PR-AUC, calibration, per-subject performance.
- Full system: false high-risk alerts per user-hour during normal life.
- Proxy-event evaluation: percentage of abrupt events detected.
- Latency: time to detection / time to prompt.
- Robustness: stability across subjects and across datasets.

## 28. False alerts are a primary startup metric

For a consumer safety system, a technically accurate detector can still be unusable if it generates frequent emergency alerts. The pitch-deck metric that best reflects usability is false emergency alerts per user-hour during ordinary life.

## 29. Prototype plan

Phase-1 prototype does not need a smartwatch. Replay recorded dataset windows in real time.
- Dataset replay simulates watch stream.
- Live feature extraction / inference runs every decision step.
- Dashboard displays HR, motion, component scores, risk, and signal quality.
- High risk prompts 'Are you safe?'.
- No response triggers a mock SOS flow.

## 30. Technology stack

| Area | Recommended stack |
| --- | --- |
| Data processing | Python, NumPy, Pandas, SciPy, NeuroKit2 / HeartPy where appropriate |
| ML | scikit-learn, XGBoost, optional PyTorch |
| Backend | FastAPI, WebSocket / streaming endpoint |
| Storage | SQLite initially, PostgreSQL later |
| Prototype UI | Streamlit first; React / Next.js later |
| Deployment path | Wear OS / Android phone bridge later |
| Experiment tracking | MLflow or W&B |
| Data/version tracking | DVC or Git LFS as appropriate |

## 31. Software-engineering product architecture

- Data-source abstraction: dataset replay, future smartwatch API, simulator.
- Sensor ingestion service.
- Preprocessor / synchronizer.
- Feature engine.
- ML inference services / modules.
- Fusion / risk engine.
- Alert engine.
- User-facing safety UI.
- Optional backend logging and analytics.

## 32. Recommended development milestones

- D00 — repository + data contracts
- D01 — PPG-DaLiA ingestion audit
- D02 — preprocessing / windowing smoke test
- D03 — first feature pipeline
- D04 — WESAD ingestion + arousal dataset
- D05 — BITS-2 synchronized event dataset
- D06 — full processed dataset build
- D07 — subject-independent split manifests
- M00 — rule baselines
- M01 — classical motion models
- M02 — classical arousal models
- M03 — context model
- M04 — model selection + calibration
- F00 — rule-based fusion
- F01 — false-alert evaluation
- F02 — cross-dataset validation
- F03 — optional learned fusion
- P00 — dataset replay simulator
- P01 — live inference API
- P02 — safety UI
- P03 — mock SOS workflow

## 33. Working rules already decided

- Dataset first, then smoke test, then full build, then integrity audit, then model training.
- Do not use model performance to debug the dataset.
- Never change scientific assumptions silently.
- Do not continue automatically to the next milestone; stop and report after each validated milestone.
- Raw data must remain immutable.
- Preserve original labels and source metadata.
- Do not invent undocumented fields.
- Stop if invariants fail.

## 34. Competition positioning

For Future-Forge 2026, WearSafe AI fits primarily under Track D — Robotics & Automation, especially 'Emerging Technologies with Societal and Industrial Impact' and 'Physical and Digital Automation'.

Secondary cross-domain fit: Track C — Digital & Emerging Tech / Artificial Intelligence.

Competition framing: an intelligent physical-digital safety system that senses the physical world, interprets risk with AI, and automatically initiates a digital safety response.

## 35. Startup / investor positioning

Core investor questions the pitch deck should answer proactively:
- Why is this better than a panic button?
- What stops it from triggering every time the user runs or exercises?
- Where is the attack dataset and how is the system validated without one?
- Can it work on affordable/common smartwatches?
- How do you handle unreliable PPG during intense movement?
- What is the false-alert rate?
- How will battery usage be controlled?
- What happens if the user does not respond?
- What is the liability boundary?
- How does it scale without proprietary hardware?
- Who pays and what is the initial market wedge?

## 36. Business model / go-to-market ideas

- B2C: freemium personal safety app + premium family/SOS features.
- B2B2C: campus and workplace safety programs.
- Family safety subscription.
- Wearable / device partnerships later.
- Initial wedge: students, solo commuters, late-shift workers, people travelling alone.

## 37. Key feasibility position

Technically feasible as a proof-of-concept now. Scientifically constrained by the lack of real assault ground truth. Product risk is dominated by false alerts, PPG motion artefacts, battery drain, and device API limitations.

## 38. Major limitations to preserve in all reports/pitches

- No real attack ground truth in the core public datasets.
- Stress is not the same as fear or assault.
- Falls are not the same as attacks.
- Lab stress differs from real-world danger.
- Different datasets use different hardware, protocols, populations, units, and sampling rates.
- PPG quality degrades under strong wrist motion.
- Physiological responses vary between people.
- Cross-dataset generalization may be substantially worse than within-dataset performance.

## 39. Strong viva / investor answer to 'Where is the attack dataset?'

There is no genuine attack-labelled wearable dataset in the primary training setup. Real assault-labelled physiological data is difficult to collect ethically and safely. Therefore, instead of falsely relabelling stress or falls as attacks, the problem is decomposed into measurable components: abrupt wrist motion, physiological arousal, and normal activity context. Each component is learned from a dataset with appropriate ground truth, and their outputs are fused into a potential-danger score. The system can then be evaluated on proxy abrupt events, normal-life false alerts, and later controlled simulated defensive motions / real wearable pilots.

## 40. Current implementation order — recommended

1. PPG-DaLiA — establish loader, preprocessing, context windows, feature extraction, and false-alert reference.
2. WESAD — establish arousal branch using compatible wrist ACC + BVP pipeline.
3. BITS-2 — build abrupt-event motion branch plus synchronized event-centered HR analysis.
4. UP-Fall — external motion validation.
5. FallAllD — optional larger abrupt-motion source after pipeline is stable.
6. Train classical component baselines only after data validation and split validation are complete.
7. Add fusion only after component models are trustworthy.
8. Build simulated live prototype last.

## 41. Open decisions / items still to be empirically validated

- Exact label mapping for mixed activities such as lunch in PPG-DaLiA.
- Final motion canonical sampling rate (20 vs 25 vs 32 Hz) after ablation.
- Final motion window size (1/2/3/5 s).
- Final arousal window size (10/30/60 s).
- Best PPG/HR extraction and signal-quality method.
- Whether gyro materially improves performance enough to justify being an optional input.
- Whether context should be explicit classification or an implicit anomaly model.
- Best fusion thresholds and whether learned fusion adds value.
- How low false-alert rate must be for MVP acceptance.

## 42. Useful source references already used in project research

- PPG-DaLiA — UCI Machine Learning Repository / original dataset paper.
- WESAD — UCI Machine Learning Repository / original WESAD paper.
- BITS-2 — Zenodo dataset record and associated data paper.
- UP-Fall — original Sensors dataset paper.
- FallAllD — dataset paper / repository.
- Research literature on wrist PPG motion artefacts and wearable stress detection.

## 43. Short handoff summary

WearSafe AI is currently best understood as a context-aware, multimodal wearable safety-anomaly system. The product target is physical danger, but the research prototype does not claim real attack classification. The strongest current data design uses PPG-DaLiA for normal context, WESAD for arousal, and BITS-2 for synchronized abrupt-event motion + HR, with UP-Fall as external validation and FallAllD optional later. The system should be built dataset-first with strict smoke tests and subject-independent splits, then classical component models, then late fusion, then false-alert evaluation, and finally a replay-based live prototype.
