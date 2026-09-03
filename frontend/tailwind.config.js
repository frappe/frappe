// The one Tailwind config. Apps contribute `theme` and `plugins` through a preset; `content`
// and `safelist` never merge from one, and nobody gets a safelist.

import { createRequire } from "node:module";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import frappeUIPreset from "frappe-ui/tailwind";

const require = createRequire(import.meta.url);
const here = dirname(fileURLToPath(import.meta.url));
const manifest = JSON.parse(readFileSync(join(here, "manifest.json"), "utf-8")).apps;

// A colocated file, found like every other contribution. Loaded synchronously: tailwind 3
// reads this config through jiti, which has no top-level await.
const appPresets = [];
for (const { source_dir } of manifest) {
	const preset = join(source_dir, "frontend", "tailwind.preset.js");
	if (!existsSync(preset)) continue;
	const loaded = require(preset);
	appPresets.push(loaded.default ?? loaded);
}

export default {
	presets: [frappeUIPreset, ...appPresets],
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
