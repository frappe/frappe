# How CI works on develop

## Develop merges through a merge queue

Pull requests into develop merge through GitHub's merge queue. Click **Merge when ready** on a pull request and GitHub tests it on top of the latest develop and the pull requests queued before it.

- If the tests pass, the pull request merges on its own. You don't need to update your branch or wait.
- If they fail, the pull request leaves the queue and nothing is merged. The pull request's timeline links the failed run. Fix it and click **Merge when ready** again.

The full suites also run on develop every night.

## Tests on your pull request

Pull requests into develop and desk-v2 run only the linters. To run the server and UI test suites on your pull request, add a label:

| Label                               | What it does                                                                                                                                                     |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `run-full-ci`                       | Runs the full server and UI suites on your pull request. Use it for risky changes.                                                                               |
| `Run Server Tests` / `Run UI Tests` | Runs the full server or UI suite on your pull request.                                                                                                           |
| `fixes-develop`                     | desk-v2 only: your pull request fixes a failing desk-v2. It runs in full whichever suite is failing on desk-v2, and it can merge once those tests pass.          |

You can add a label any time. It restarts your tests within a minute, no push needed.

## desk-v2 is tested every hour

desk-v2 has no merge queue. Every hour, if desk-v2 has new commits, the full suites run on desk-v2: the server suite when server files changed, the UI suite when frontend files changed.

Every open desk-v2 pull request has a **Desk-v2 status** check:

- Green, "desk-v2 is passing": you can merge.
- Red, "desk-v2 is failing": something already merged broke desk-v2. The check links to the failed job, which shows the error. Open a pull request with the fix and add the `fixes-develop` label.

When desk-v2 goes green again, every pull request turns green on its own.

To re-test desk-v2 at any other time: open the **Actions** tab of the repo, click **Develop Tests** in the list on the left, then click the **Run workflow** button on the right.

## Settings

- Merge queue: the develop branch protection rule in the repository settings.
- How often desk-v2 is tested: the `cron` at the top of `.github/workflows/develop-status.yml`.
- Label names: the top of `.github/helper/roulette.py`, and the label checks in `.github/workflows/develop-status.yml`.
