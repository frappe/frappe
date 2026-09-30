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

After those steps the walk goes to the list twice more. The first time, it saves version `v2`
of its Client Script. The second time, it saves a Quick Entry Form Layout on the doctype,
which the record page does not show, and deletes it at the end. The server tells the desk
about each change. Each time, the walk then opens the record again. Each run starts with
version `v1` of the script.

A return step fails when it shows a skeleton, draws any field or row more than once, or
does not settle in time. A return step on the record also fails when the script's item is
drawn more than once, is ever drawn without the count, or is missing at the end.

A return to the record after a change has its own rule for the script's item. The old
version may draw first, so the item may be drawn twice. It fails when it is ever drawn
without the count, or does not end on its `v2` label. After the Form Layout save, the step
also fails when the page did not read the doctype's meta again.

The walk is run by hand, not in CI.

## View-restore walk

`viewRestore.js` checks that a return visit to a record shows the view the reader left.

Before it starts, it stores two Form Layouts on the doctype and deletes them at the end:

- a Details layout, copied from the doctype's own, with the first labelled section of a later
  form tab closed by default;
- a Side Panel layout with enough fields that the panel column scrolls.

The walk picks the later tab with the most fields. Both rows carry the condition
`doc.name != 'view-restore-walk'`, which every record matches; the walk deletes only rows
with that condition.

On the first visit, the walk picks that form tab, opens the closed section, and scrolls
the Details tab and the panel column halfway down. It then goes Back to the list, Forward
to the record, to the list through the rail, sidebar or breadcrumb, Back to the record, to
the list again, and to the record through navigation or its list row. On each return to
the record it checks:

- each scroll offset is within 1 px of the first visit's;
- the form tab and the state of every section match the first visit's;
- no frame, from the first one that shows the record, showed a different offset.

Last, it opens a record from the list that it has not visited. That step fails unless both
offsets are 0 and every section is as the layout starts it.

A frame's offsets are read after that frame's animation-frame callbacks and layout, before
it paints. A step also fails when it does not settle in time. The walk stops with a
message when the doctype has no later form tab with a labelled section, or when a scroller
moves less than 40 px.

```sh
yarn --cwd frontend/walks walk:view
DOCTYPE=User yarn --cwd frontend/walks walk:view --json /tmp/view.json
```

Without `DOCTYPE`, it takes the navigation doctype with at least three rows whose later
form tab has the most fields. `User` works on a stock site: its Settings tab scrolls.

### Against a checkout's frontend

The bench answers `/apps` with its built document. To walk a checkout's source without
building, serve it with vite and point the walk at it:

```sh
cd frontend && ./node_modules/.bin/vite --config walks/vite.walk.config.js
BASE_URL=http://<site>:8098 yarn --cwd frontend/walks walk:view
```

The config serves `/apps` from the checkout and sends every other bench path to the
bench. It needs `frontend/manifest.json`; copy the one from a built checkout and point the
`frappe` app's source directory at this checkout. `WALK_PORT` changes the port.

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
