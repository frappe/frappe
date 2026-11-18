# How CI works on develop

## Develop merges through a merge queue

Pull requests into develop merge through GitHub's merge queue. Click **Merge when ready** on a pull request and GitHub tests it on top of the latest develop and the pull requests queued before it.

- If the tests pass, the pull request merges on its own. You don't need to update your branch or wait.
- If they fail, the pull request leaves the queue and nothing is merged. The pull request's timeline links the failed run. Fix it and click **Merge when ready** again.

The full suites also run on develop every night.

## Tests on your pull request

Pull requests into develop run only the linters, and the server and UI test suites run in the merge queue. To run them on your pull request before queueing it, add a label:

| Label                               | What it does                                                                       |
| ----------------------------------- | ---------------------------------------------------------------------------------- |
| `run-full-ci`                       | Runs the full server and UI suites on your pull request. Use it for risky changes. |
| `Run Server Tests` / `Run UI Tests` | Runs the full server or UI suite on your pull request.                             |

You can add a label any time. It restarts your tests within a minute, no push needed.

Pull requests into desk-v2 run the suites their changes can affect.

## Settings

- Merge queue: the develop branch protection rule in the repository settings.
- Label names: the top of `.github/helper/roulette.py`, and `.github/workflows/test-labels.yml`.
