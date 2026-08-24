# Evidence Bank — Test Fixture (no real person)

> Source of truth. Exhaustive. Not for submission.

## Angles

### angle: platform-leader
claim:  Builds the paved road other teams ship on.
proof:  ev:0031, ev:0033
serves: primary

### angle: cost-optimizer
claim:  Finds the expensive thing and makes it cheap.
proof:  ev:0031, ev:0032
serves: primary

## Evidence

### ev:0031 — Cut deploy time 45m → 6m
role:       Staff Engineer, Example Co
dates:      2021-03 → 2023-08
metric:     45m → 6m (87%)
confidence: measured
source:     Q3-2022 platform review deck
scope:      team of 6 · ~200 deploys/wk · 40 eng consumers
tags:       ci-cd, github-actions, docker, buildkit, platform
angles:     platform-leader, cost-optimizer
narrative: >
  CI was the bottleneck. Rebuilt the pipeline around a warm build cache and
  parallel test shards. Median deploy fell from 45 minutes to 6.

### ev:0032 — Estimated cloud saving from rightsizing
role:       Staff Engineer, Example Co
dates:      2022-01 → 2022-06
metric:     ~30% compute reduction (my estimate, unverified)
confidence: estimated
source:     n/a
scope:      ~120 services
tags:       aws, cost, terraform
angles:     cost-optimizer
narrative: >
  Rightsized over-provisioned services. Never got a clean before/after bill,
  so the saving is directional only.

### ev:0033 — Mentored the on-call rotation into health
role:       Staff Engineer, Example Co
dates:      2022-06 → 2023-08
metric:     n/a
confidence: qualitative
source:     n/a
scope:      team of 6
tags:       leadership, on-call, incident-response
angles:     platform-leader
narrative: >
  Rebuilt runbooks and coached the rotation. Pages stopped waking people up
  at 3am, though we never tracked the number cleanly.

## Shortfalls
- Kubernetes at scale — operated, never designed a cluster.
- People management — tech lead, never a line manager.
