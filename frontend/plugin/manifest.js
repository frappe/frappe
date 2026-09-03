// Reads the build manifest Python assembles; singleton enforcement lives there too,
// in `frappe/shell/manifest.py`.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

function read() {
	const path = join(here, "..", "manifest.json");
	try {
		return JSON.parse(readFileSync(path, "utf-8"));
	} catch {
		throw new Error(
			`No build manifest at ${path}.\n` +
				`The framework's frontend is built through bench, which assembles the manifest first.\n` +
				`Run \`bench build\` (or \`bench build --app frappe\`) rather than \`yarn build\` here.`
		);
	}
}

/** The bundle: the apps that actually contribute source. */
export function readManifest() {
	return read().apps;
}

/** Every app on the bench, contributing or not; see the plugin's doctype-name index. */
export function readAllSourceDirs() {
	return read().source_dirs;
}
