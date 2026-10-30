# AI tool usage

Updated as the build goes; this log is meant to be honest.

**Tool:** Claude Code (Anthropic), used in VS Code.

| Area | AI did | Human (author) decided |
|---|---|---|
| Product & domain research | Drafted the PRD, Domain Brief and Product Thinking docs with the author | Users, the decision being supported, the metrics, domain rules R1–R11, scope |
| M0 scaffold | Wrote the repo skeleton, configs, Dockerfile, CI and the health test | Single-container deploy shape, deploy order, priorities |
| M1 data layer | Wrote the Elexon client, ingest CLI, loaders and tests; ran the fetch; computed the data findings | Fetch windows and cleaning rules (PRD); the band bucket count and horizon-slider range after reviewing the findings |
| M2 core analytics | Wrote `core/` (selection, alignment, metrics, correction, bands, planner), the tests and the report CLI; ran the January numbers | Band cells (2 horizon × 3 level), 40 h horizon cap, the extra analyses (bias diagnosis, correction comparison, lead-time curve, value of waiting), the correction model options and split |
