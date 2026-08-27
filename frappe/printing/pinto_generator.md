# pinto PDF generator

[pinto](https://github.com/the-bokya/pinto) renders printview HTML to PDF in a single
short-lived process — no Chromium, no browser pool. It is a third PDF generator alongside
`wkhtmltopdf` and `chrome`, selectable in Print Settings or per Print Format.

## Setup

pinto ships as a standalone binary, not a Python dependency; a site without it keeps using
whichever generator it already has.

```bash
git clone https://github.com/the-bokya/pinto && cd pinto
cargo build --release
```

Put the binary on `PATH` as `pinto`, or point at it explicitly:

```json
// sites/common_site_config.json
{ "pinto_path": "/path/to/pinto/target/release/pinto", "pinto_timeout": 120 }
```

Then set **PDF Generator → pinto** in Print Settings (site-wide) or on a Print Format.

## How it plugs in

`frappe.utils.pdf_generator.pinto.get_pinto_pdf` is registered on the `pdf_generator` hook and
claims renders where `pdf_generator == "pinto"`. It pipes the printview HTML to the binary on
stdin along with a config file carrying the wkhtmltopdf-style options plus the site-local values
a standalone binary cannot read for itself — host URL, bench/site paths for resolving
host-relative `<img>` and `<link>`, and the Print Settings page geometry — and reads the PDF
back on stdout.

Password protection is applied by Frappe with pypdf after the render, not by pinto.

## Trade-offs

Chromium stays the fidelity reference. pinto has its own layout engine, so it is close to but
not pixel-identical with Chromium, and it does not implement flexbox, grid, `position: absolute`,
transforms, `border-radius` or SVG. Formats using the beta renderer emit flexbox and are pinned
to Chromium regardless of this setting. Use pinto for classic print formats where a ~10 MB
process beats a ~120 MB browser.
