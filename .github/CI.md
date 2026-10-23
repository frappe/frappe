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
4. Merge it once those tests pass. Every pull request turns green right away. The full suites also run on develop once more to confirm, and if they fail, develop is red again.

To re-test develop at any other time: open the **Actions** tab of the repo, click **Develop Status** in the list on the left, then click the **Run workflow** button on the right.

## Labels

| Label                               | What it does                                                                                                                                                               |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `fixes-develop`                     | Your pull request fixes a failing develop. Its Develop status stays green so it can merge, and it runs in full whichever suite is failing on develop (server, UI or both). |
| `run-full-ci`                       | Runs the full server and UI suites on your pull request. Use it for risky changes.                                                                                         |
| `Run Server Tests` / `Run UI Tests` | Runs the full server or UI suite on your pull request.                                                                                                                     |

You can add a label any time. Adding `fixes-develop` or `run-full-ci` restarts your tests within a minute, no push needed. `Run Server Tests` and `Run UI Tests` take effect on your next push or re-run.

## Tests on your pull request

Pull requests into develop run only the linters. The server and UI test suites don't run on them, because develop runs them every hour. To run them on your pull request, add one of the labels above.

## Settings

- How often develop is tested: the `cron` at the top of `.github/workflows/develop-status.yml`.
- Label names: the top of `.github/helper/roulette.py`.
