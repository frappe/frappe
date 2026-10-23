# How CI works on develop

## Develop is tested every hour

Every hour, if develop has new commits, the full suites run on develop: the server suite when server files changed, the UI suite when frontend files changed. The full suites also run every night.

Every open develop pull request has a **Develop status** check:

- Green, "develop is passing": you can merge.
- Red, "develop is failing": something already merged broke develop. The check links to the failed run. Don't merge until develop is fixed.

When develop goes green again, every pull request turns green on its own. You don't need to push or re-run anything.

## When develop is failing

1. Open the failed run from the Develop status check and find the test that fails.
2. Open a pull request with the fix, or a revert of the change that broke it.
3. Add the `fixes-develop` label. The failing suite runs in full on your pull request.
4. Merge it once those tests pass.
5. Go to Actions, then **Develop Status**, then **Run workflow**. This runs the full suites on develop right away. When they pass, every pull request turns green.

## Labels

| Label                               | What it does                                                                                                                                                               |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `fixes-develop`                     | Your pull request fixes a failing develop. Its Develop status stays green so it can merge, and it runs in full whichever suite is failing on develop (server, UI or both). |
| `run-full-ci`                       | Runs the full server and UI suites on your pull request. Use it for risky changes.                                                                                         |
| `Run Server Tests` / `Run UI Tests` | Runs the full server or UI suite on your pull request.                                                                                                                     |
| `Skip CI`                           | Skips the tests.                                                                                                                                                           |

You can add a label any time. Adding `fixes-develop` or `run-full-ci` restarts your tests within a minute, no push needed. `Run Server Tests` and `Run UI Tests` take effect on your next push or re-run.

## Which tests run on your pull request

CI runs only the tests your change can affect.

- Change only JS, Vue or CSS: server tests are skipped, and only the UI specs that use those files run.
- Change only Python: UI tests are skipped, and only the server tests that use those files run.
- Change both: both run, each picking its related tests.
- Change only docs or images: no tests run.

The tests are picked from a map that the nightly run builds. Changes to core framework files (`frappe/model`, `frappe/database`, `hooks.py`), dependency files, CI files, or a file the map doesn't know yet run the full suite.

## Settings

- How often develop is tested: the `cron` at the top of `.github/workflows/develop-status.yml`.
- Label names: the top of `.github/helper/roulette.py`.
