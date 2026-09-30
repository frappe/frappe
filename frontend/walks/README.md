# Return-visit walk

The walk opens a list, opens a record, goes Back and Forward, then reaches the list
through the rail, sidebar or breadcrumb. It reopens the record through navigation when
available, otherwise from its list row. On each step it counts the skeletons shown and how
many times each field and each list row is drawn, on a normal and a throttled network.

Before it starts, the walk stores a Client Script on the doctype, named `Return Visit Walk`.
Its `onRefresh` draws a header item with the doctype's row count, read with
`page.cached`. The walk deletes the script when it ends. It deletes only a script it made,
so if the site already has another script of that name, the walk stops. The `script` column counts how
many times that item is drawn on a record step.

A return step fails when it shows a skeleton, draws any field or row more than once, or
does not settle in time. A return step on the record also fails when the script's item is
drawn more than once, is ever drawn without the count, or is missing at the end. The walk is
run by hand, not in CI. It is expected to fail until the desk caches what a return visit
needs.

## Run

```sh
yarn --cwd frontend/walks install
yarn --cwd frontend/walks playwright install chromium
yarn --cwd frontend/walks walk
yarn --cwd frontend/walks walk --json /tmp/walk.json
```

`--json <path>` also writes every step's counts to that file. The walk exits with 0 when
every return step passes on every network, and 1 otherwise.

## Environment

| Variable     | Default                                         | Meaning                                  |
| ------------ | ----------------------------------------------- | ---------------------------------------- |
| `BASE_URL`   | `http://localhost:8000`                         | The site to walk                         |
| `USR`        | `Administrator`                                 | Login user                               |
| `PWD_FRAPPE` | `admin`                                         | Login password                           |
| `DOCTYPE`    | the first rail or sidebar doctype that has rows | The doctype whose list and record to use |
| `NETWORK`    | both                                            | `normal` or `slow`                       |
