# Audit — searchIG2020

Updated: 2026-09-15

The original source declared no third-party dependencies but imported a search provider, opened urls.txt in truncation mode at import and called an incompatible `pause` keyword. The isolated regression run reproduced that TypeError before any query could execute; it created only an empty output fixture in the disposable checkout. No retained result list was accessed.

The repair pins the documented provider API, requires explicit keywords, defers all execution to the CLI and verifies dependency compatibility before creating output. One candidate budget and a timed worker bound provider execution. Output uses exclusive creation and retains already written URLs after interruption, deadline or provider failure. The old per-result delay is removed while page and keyword pacing remain.

All 18 offline tests pass locally on Python 3.12. The installed dependency parser is checked against a synthetic HTML response. Tests also cover a complete CLI/worker round trip, malformed and non-Instagram results, existing/racing outputs, HTTP failure, import behavior, dependency failure and a real worker timeout with partial output retained. All nine installed packages are compatible. Hosted Linux/Windows checks are required before release.

The repository's actual default branch is master, despite stale generic contribution guidance naming main. CONTRIBUTING and the repository override now identify master. The existing label workflow is corrected to use its actual labels.yml configuration. Original source/data files remain preserved. No live Google/Instagram query or stored result-list read was performed, and no Vercel CPU or monthly quota saving is claimed.
