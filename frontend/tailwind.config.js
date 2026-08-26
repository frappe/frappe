// ONE framework-owned Tailwind config. Apps contribute `theme` and `plugins` only.
//
// The shape came from the tooling, not from taste: `theme` and `plugins` merge from a
// preset; `content` and `safelist` do NOT -- `content` never, at any depth (frappe-ui
// documents this), and `safelist` last-non-empty-wins silently. So the framework owns
// exactly the two keys that cannot compose (#42123).
//
// And nobody gets a safelist, including the framework. CRM's `!(text|bg)-` pattern is
// 88% of its CSS gzip bytes; it serves CRM v1's runtime class composition and arrived
// in frontend2 by copy-paste. The one genuinely unscannable case, Page Script icons,
// is already solved without one.

import { createRequire } from "node:module";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import frappeUIPreset from "frappe-ui/tailwind";

const require = createRequire(import.meta.url);
const here = dirname(fileURLToPath(import.meta.url));
const manifest = JSON.parse(readFileSync(join(here, "manifest.json"), "utf-8")).apps;

// Contribution is a colocated file, found the way every other contribution is -- NOT
// a scalar hook. The `app_prefix`/`app_boot`/`app_permission` family exists because
// those values are needed before JS is read, or per-site at runtime. A preset is
// neither.
//
// Loaded synchronously: tailwind 3 reads this config through jiti, which has no
// top-level await.
const appPresets = [];
for (const { source_dir } of manifest) {
	const preset = join(source_dir, "frontend", "tailwind.preset.js");
	if (!existsSync(preset)) continue;
	const loaded = require(preset);
	appPresets.push(loaded.default ?? loaded);
}

export default {
	presets: [frappeUIPreset, ...appPresets],
	// Derived from the manifest's `source_dir`, which loses nothing: the only
	// hand-written globs on this bench point at packages the framework now owns.
	content: [
		join(here, "index.html"),
		join(here, "src/**/*.{vue,js,ts,jsx,tsx}"),
		join(here, "../ui/src/**/*.{vue,js,ts,jsx,tsx}"),
		join(here, "node_modules/frappe-ui/src/**/*.{vue,js,ts,jsx,tsx}"),
		join(here, "node_modules/frappe-ui/frappe/**/*.{vue,js,ts,jsx,tsx}"),
		...manifest.flatMap(({ source_dir }) => [
			join(source_dir, "**/frontend/**/*.{vue,js,ts}"),
			join(source_dir, "**/custom/**/*.{vue,js,ts}"),
		]),
	],
	theme: { extend: {} },
	plugins: [],
};
