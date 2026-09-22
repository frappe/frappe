// The one Tailwind config. Apps contribute `theme` and `plugins` through a preset; `content`
// and `safelist` never merge from one, and nobody gets a safelist.

import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import frappeUIPreset from "frappe-ui/tailwind";
import { appContent } from "./plugin/content.js";
import { readAllSourceDirs, readManifest } from "./plugin/manifest.js";
import { loadPresets } from "./plugin/presets.js";

const here = dirname(fileURLToPath(import.meta.url));
const manifest = readManifest();

// Every app on the bench, contributing or not; `vite.config.js` ran the same check first, so
// a refusal prints there, once, before any transform.
const appPresets = loadPresets(readAllSourceDirs()).map(({ preset }) => preset);

export default {
	presets: [frappeUIPreset, ...appPresets],
	content: [
		join(here, "index.html"),
		// The class names a stored Client Script may rely on; no file on disk carries a script's text.
		join(here, "palette.txt"),
		join(here, "src/**/*.{vue,js,ts,jsx,tsx}"),
		join(here, "../ui/src/**/*.{vue,js,ts,jsx,tsx}"),
		join(here, "node_modules/frappe-ui/src/**/*.{vue,js,ts,jsx,tsx}"),
		join(here, "node_modules/frappe-ui/frappe/**/*.{vue,js,ts,jsx,tsx}"),
		...appContent(manifest),
	],
	theme: { extend: {} },
	plugins: [],
};
