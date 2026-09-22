// Loads each app's `frontend/tailwind.preset.js`, refuses a second writer on one theme leaf,
// and wraps every preset with `presets: []` so Tailwind's stock theme stays below frappe-ui's.

import { existsSync } from "node:fs";
import { basename, join } from "node:path";
import jiti from "jiti";
import resolveConfig from "tailwindcss/resolveConfig.js";

const PRESET_KEYS = ["theme", "plugins"];

const HEADER =
	"The desk shell builds one stylesheet, which admits one value for each theme key. These presets conflict:";
const FOOTER = "Change the presets and build again.";

// jiti: an app preset is `export default` under a root that may or may not say `"type": "module"`.
const load = jiti(import.meta.url, { interopDefault: true });

export function presetPath(sourceDir) {
	return join(sourceDir, "frontend", "tailwind.preset.js");
}

export function frameworkPreset() {
	return load("frappe-ui/tailwind");
}

/** The theme every app writes against: frappe-ui's preset alone. */
export function frameworkTheme() {
	return resolveConfig({ presets: [frameworkPreset()] }).theme;
}

/** `[{ app, preset }]` for every app on the bench that ships a preset, checked and wrapped. */
export function loadPresets(sourceDirs, theme = frameworkTheme()) {
	const loaded = [];
	for (const sourceDir of sourceDirs) {
		const path = presetPath(sourceDir);
		if (!existsSync(path)) continue;
		loaded.push({ app: basename(sourceDir), preset: load(path) });
	}
	return checkPresets(loaded, theme);
}

export function checkPresets(loaded, theme) {
	const problems = [];
	const writers = new Map();
	for (const { app, preset } of loaded) {
		if (!preset || typeof preset !== "object") {
			problems.push(`${app} exports ${typeof preset}; a preset is an object`);
			continue;
		}
		for (const key of Object.keys(preset)) {
			if (!PRESET_KEYS.includes(key)) {
				problems.push(
					`${app} sets \`${key}\`; a preset carries \`theme\` and \`plugins\` only`
				);
			}
		}
		for (const key of Object.keys(preset.theme ?? {})) {
			if (key !== "extend") {
				problems.push(
					`${app} sets \`theme.${key}\`; a preset writes under \`theme.extend\` only`
				);
			}
		}
		for (const [path, value] of leaves(preset.theme?.extend ?? {})) {
			const framework = lookup(theme, path);
			if (framework !== undefined) {
				problems.push(
					`${app} sets \`${path.join(".")}\`, which the framework defines as ${show(
						framework
					)}`
				);
			}
			const key = JSON.stringify(path);
			if (!writers.has(key)) writers.set(key, []);
			writers.get(key).push({ app, value });
		}
	}
	for (const [key, apps] of writers) {
		if (apps.length < 2) continue;
		const values = new Set(apps.map(({ value }) => show(value)));
		if (values.size === 1 && typeof apps[0].value !== "function") continue;
		const wants = apps.map(({ app, value }) => `${app} wants ${show(value)}`).join(", ");
		problems.push(`${JSON.parse(key).join(".")}: ${wants}`);
	}
	if (problems.length) {
		throw new Error(
			`${HEADER}\n${problems.map((line) => `  ${line}`).join("\n")}\n\n${FOOTER}`
		);
	}
	return loaded.map(({ app, preset }) => ({ app, preset: { ...preset, presets: [] } }));
}

function* leaves(node, prefix = []) {
	for (const [key, value] of Object.entries(node)) {
		const path = [...prefix, key];
		if (isPlainObject(value)) yield* leaves(value, path);
		else yield [path, value];
	}
}

function lookup(theme, path) {
	let node = theme;
	for (const key of path) {
		if (!node || typeof node !== "object") return undefined;
		node = node[key];
	}
	return node;
}

function isPlainObject(value) {
	return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function show(value) {
	if (typeof value === "function") return "a function";
	if (isPlainObject(value)) return "an object";
	return JSON.stringify(value);
}
