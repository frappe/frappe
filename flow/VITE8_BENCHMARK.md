# Vite 8 validation

Compared develop `0c4d656697574a3891d646cf79d415ecbde76d42` with PR #45270
`2785f7386051ee3f9a8336f74c6f08620196d6cd` plus the local container-query fix.
Both use the current island pipeline, including its discovery and output builds.

## Production build

Local macOS run with Node 24.13.0 and Yarn 1.22.22. Each revision had its own
frozen-lockfile Flow dependency install and isolated bench/output directory;
both borrowed the same installed framework root dependencies. Installation is
excluded from the timings. One warmup preceded three sequential timed builds per
revision, with warm filesystem caches. Other work could run on this machine.

| Metric | Vite 5.4.21 | Vite 8.0.13 with fix |
| --- | ---: | ---: |
| Wall time, run 1 | 8.769 s | 3.426 s |
| Wall time, run 2 | 7.950 s | 3.108 s |
| Wall time, run 3 | 8.907 s | 3.295 s |
| Median wall time | 8.769 s | 3.295 s |
| Initial JavaScript | 1,172,475 bytes | 1,172,479 bytes |
| All JavaScript, including lazy chunk | 1,645,005 bytes | 1,642,469 bytes |
| CSS | 341,821 bytes | 267,114 bytes |

The median is 62.4% lower (2.66× faster). This is a local Flow build measurement,
not an end-to-end CI or deployment timing.

For each revision, run inside its `flow/` directory:

```sh
yarn install --frozen-lockfile
FRAPPE_BENCH_ROOT=<isolated-bench> FRAPPE_DOCKER_BUILD=1 yarn build
```

The isolated bench contains `sites/apps.txt` listing `frappe`, an empty
`sites/common_site_config.json`, and `sites/assets/frappe/`. Each build's
registered assets and relative chunk imports resolve to files, and its entry
retains the `mount` export. Output sizes were stable across all three runs.

## Regression and browser checks

`yarn test` passes all 75 Flow tests. The new build test failed on the unfixed
production pipeline and passes with the PostCSS conversion, including Tailwind's
minimum-width and negated breakpoints, maximum-width rules, and media conditions
that must remain viewport-dependent.

Chromium 151.0.7922.34 mounted the actual production JavaScript and stylesheet in
a 420×780 panel and a 1440×900 full page, at a constant 1440×900 viewport. Both
layouts and Agent/Model menu interactions passed without console or network
errors. The fixed screenshots match the Vite 5 baseline byte-for-byte. An
unfixed Vite 8 build reproduced overflowing/clipped panel controls.

Container breakpoints were checked at host widths 420, 639, 640 and 900px: the
fixed build follows the host width; the unfixed build follows the viewport.
These browser checks used a static `tester@example.com` API/socket fixture, not
an authenticated site. Backend permissions, provider calls and streaming were
not tested.
