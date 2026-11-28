# Flow evals

`bench flow-eval` tells you whether a change to what Flow's Assistant is given (a skill, a whitelisted API an agent calls, an error message, a tool) made it better at a task. You write the task as a small Python file, run it on your bench, and read a table.

**What you need:**

- A bench, and a **throwaway site** whose own `site_config.json` has `allow_flow_evals`. The command copies every table when it starts and puts them all back before each run and at the end, so anything else written to that site meanwhile is lost. Never set it on a site you work on.
  ```
  bench --site eval.localhost set-config allow_flow_evals true
  ```
- For `flow-eval run`: a model on that site, with **your own API key or a local model's address** (Desk, Flow's settings, Flow Model). Frappe gives no key for this. The runs cost what any chat on that model costs.
- `flow-eval check` calls no model and needs no key; the site needs only a Flow Model row so that Flow has an Assistant.
- MariaDB. The bench running (`bench start`) and its flow server, for `run`.

## Write a case

A case is one file in `apps/<app>/evals/`, at the root of your app's repository, beside `skills/`. Do not put it inside a skill's folder: the Assistant can read every file there. Its name without `.py` is the case's name; a file whose name starts with `_` is not a case.

This one is an example, not a case Frappe ships: put yours in your own app.

```python
# apps/frappe/evals/my_todos.py
import frappe

ASK = "What is on my to-do list?"
USER = "anna@example.com"


def setup():
	frappe.get_doc(
		{
			"doctype": "User",
			"email": USER,
			"first_name": "Anna",
			"send_welcome_email": 0,
			"roles": [{"role": "Flow User"}],
		}
	).insert()
	frappe.set_user(USER)
	frappe.get_doc({"doctype": "ToDo", "description": "Send the Acme quote by Friday", "allocated_to": USER}).insert()


PATH = [
	("read_records", {"doctype": "ToDo", "fields": ["description"]}, "Acme quote"),
]


def check(run):
	assert "Acme" in run.reply, "the reply does not have the to-do"
```

- `ASK`: what the user types.
- `USER`: who asks. A normal user, never Administrator: every tool call runs with their permissions.
- `setup()`: makes the records the case needs, as Administrator, on a site just put back. It must make `USER`, with the role Flow User. What it returns is `run.setup`. Make the records the way the app makes them, with the fields its own lists filter on: a ToDo without `allocated_to` is on no one's list.
- `check(run)`: passes by returning, fails with an `AssertionError`, whose message the table shows. It may read `frappe.db`. `run.reply` is the last message, `run.tool_calls` the calls in order (`.name`, `.args`, `.result`), `run.called(name, **args)` whether a call was made with those top-level arguments, `run.usage` the tokens and cost.
- `PATH` (optional): the tool calls a right agent would make, for `flow-eval check`. Each step is `(tool, args)` or `(tool, args, expect)`. `expect` is a string the result must contain, or a function of the result text. A step with an `expect` passes when it holds, even if the tool refused, so `(send, "Join this thread")` says "this is refused, and the refusal names the next step". `PATH` may be a function of what `setup()` returned.

## Check without a model

```
$ bench --site eval.localhost flow-eval check frappe
case                  step                                        result                        bytes
my_todos              1 read_records ToDo                         ok                               75
1 of 1 cases pass. Largest result: 75 bytes. A result over 51,200 bytes is cut before the model sees it.
```

Each step runs through Flow's own tool callback as `USER`, exactly as a model's call would, and the table shows what the model would be given: a refusal, missing rows, an error that names no next step, a result too large. It exits 1 when a case fails.

## Run with a model

```
$ bench --site eval.localhost flow-eval run frappe --skill print-formats --max-cost 0.10
6 runs on openai/openai/gpt-6-luna, stops at $0.10
flow-eval run frappe --skill frappe/print-formats    3 runs a case · openai/openai/gpt-6-luna · frappe 90d6efa1b9

case                  latest.without  latest.with     change
my_todos              3/3             3/3             same
total                 3/3             3/3             0 better · 1 same · 0 unclear · 0 worse

tokens per run        20,488          20,874          (median, input + output)
cost                  $0.001          $0.001          (total, as Flow recorded it)
saved in sites/trial.evals.localhost/private/flow-evals/latest.without and sites/trial.evals.localhost/private/flow-evals/latest.with
```

Each case's `ASK` goes through Flow's chat API as `USER`, with tool calls approved, 3 times (`--runs`). With `--skill`, every case runs with that skill off and on, saved as `<label>.without` and `<label>.with`. A case that has nothing to do with the skill, as here, should come out `same`.

How a case is called:

| Word | When |
|---|---|
| `better` | every run without passed none, every run with passed |
| `worse` | the other way round |
| `same` | both arms passed every run, or both failed every run |
| `unclear` | anything else, or a run ended in an `error` (the provider's or the case's own code); run more |

A run that times out (`--timeout`, 300 s), hits the iteration limit or is denied is a `fail`. Each run is saved as JSON in `sites/<site>/private/flow-evals/<label>/`, with the reply, the tool calls and their results, the usage, a hash of the prompt and each app's commit; `prompt.txt` holds the system prompt of the label's first run; `prompt_hash` tells you whether later runs were given the same one.

`--max-cost` (1 dollar by default) stops the command once the runs have cost that much; it can overshoot by one run. Two provider errors in a row stop it too.

## A code change

`--skill` turns one skill off in the same checkout. For a change to code, run once on the base branch and once on yours, with labels, and compare:

```
git -C apps/myapp switch develop && git -C apps/myapp checkout my-branch -- evals
bench restart
bench --site eval.localhost flow-eval run myapp --label base

git -C apps/myapp switch my-branch
bench restart
bench --site eval.localhost flow-eval run myapp --label mine

bench --site eval.localhost flow-eval compare base mine
```

The web server runs the tools, so restart it after a switch, and migrate when the schema changed. A change that is half skill and half code gives three arms: `base` on the base branch, and `pr.without` and `pr.with` from `flow-eval run myapp --skill myskill --label pr` on your branch. `compare base pr.without` is what the code did; the `--skill` table is what the skill added; `compare base pr.with` is the whole change.

```
$ bench --site eval.localhost flow-eval run frappe
$ bench --site eval.localhost flow-eval compare latest latest.with
latest: openai/openai/gpt-6-luna · frappe 92854a05f8 · raven e2ae015c
latest.with: openai/openai/gpt-6-luna · frappe 90d6efa1b9 · raven e2ae015c

case                  latest       latest.with  change
my_todos              3/3          3/3          same
total                 3/3          3/3          0 better · 1 same · 0 unclear · 0 worse

tokens per run        20,860       20,874       (median, input + output)
cost                  $0.001       $0.001       (total, as Flow recorded it)
```

## Limits

- One turn per case. No approval cards (every call is approved), no `read_screen` (no page is open), no background jobs.
- The restore puts back every table, and nothing else: not files, not Flow's memory and knowledge indexes, not an auto-increment's next value.
- Runs go one after another: about 20 s a run on GPT-6 Luna, plus about half a second to put the site back.
- MariaDB only.

## What it costs

On GPT-6 Luna, 34 runs of Raven's cases cost $0.076 in all: $0.002 a run (median), about 89,000 tokens. So 12 cases run 3 times with and without a skill (72 runs) cost about $0.15 on Luna; a dearer model costs more in proportion. The one-time copy took 5.6 s on a site with frappe and Raven (333 tables).
