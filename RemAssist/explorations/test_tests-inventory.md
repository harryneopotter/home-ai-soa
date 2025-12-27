# test_tests Directory Inventory

## Summary
`test_tests/` contains focused unit tests, currently with an emphasis on the keep-alive behavior for ModelClient. The directory serves as a place for small, fast unit tests.

## Files
- `tests/test_model_keepalive.py` — Unit test asserting ModelClient.chat sends `keep_alive: -1` to `/api/chat` (monkeypatching `requests.post`).

## Observations
- The test is relevant and aligns with the documented behavior of pinning models in `RemAssist/` documents.
- Many other tests are integration-style and exist in `test_scripts/`. Consider consolidating unit tests into `test_tests/` and integration tests into `tests/integration/`.

## Recommendations
- Expand `test_tests/` with more unit tests covering parser, orchestrator logic, and utils.
- Adopt pytest conventions and add a CI job to run these unit tests quickly.
- Consolidate test discovery and add `conftest.py` for shared fixtures.
