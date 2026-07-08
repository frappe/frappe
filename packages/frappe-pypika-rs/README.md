# frappe-pypika-rs

`frappe-pypika-rs` is the internal Rust-backed PyPika compatibility package for Frappe.

The package is intentionally separate from Frappe's main `flit_core` build so the Rust extension can
use `maturin` without changing Frappe's packaging backend. The first supported scope is the PyPika
surface used by Frappe's query builder for MariaDB, Postgres, and SQLite.

The current API is experimental. It exposes package metadata and a narrow Rust-rendered
`render_select(...)` primitive used to validate the build path before replacing PyPika classes.

## Development

From this directory:

```bash
maturin develop
```

Then run the Frappe query-builder tests and the microbenchmark comparison documented in
`frappe/tests/microbenchmarks/README.md`.
