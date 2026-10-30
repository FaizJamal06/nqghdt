# AI tool usage

Updated as the build goes; this log is meant to be honest.

**Tool:** Claude Code (Anthropic), used in VS Code.

| Area | AI did | Human (author) decided |
|---|---|---|
| Product & domain research | Drafted the PRD, Domain Brief and Product Thinking docs with the author | Users, the decision being supported, the metrics, domain rules R1–R11, scope |
| M0 scaffold | Wrote the repo skeleton, configs, Dockerfile, CI and the health test | Single-container deploy shape, deploy order, priorities |
| M1 data layer | Wrote the Elexon client, ingest CLI, loaders and tests; ran the fetch; computed the data findings | Fetch windows and cleaning rules (PRD); the band bucket count and horizon-slider range after reviewing the findings |
| M2 core analytics | Wrote `core/` (selection, alignment, metrics, correction, bands, planner), the tests and the report CLI; ran the January numbers | 40 h horizon cap; the extra analyses (bias diagnosis, correction comparison, lead-time curve, value of waiting); the correction candidates incl. proportional and the choice of proportional; fixing the train-window leak; dropping the horizon split from the band cells after the width check; the worked-example hour |
| M3 API | Wrote the DataStore, the Decision View helpers, schemas, routes and API tests | Endpoint scope (the extra Forecast Trust tables), parameter limits (horizon 0–40, confidence ≤ 0.95, band 50/80/90) |
| M4 frontend | Wrote the settings bar, Overview, Decision View, charts and API client; checked the screens with headless-browser screenshots | The Decision View design (which lines, their weights, plain-words legend, the generated sentence, actuals hidden by default), Overview scope, dropping the wide-band flag, in-sample badge wording, default day |
