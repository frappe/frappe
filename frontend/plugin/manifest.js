// Reads the Python-assembled build manifest.
//
// Assembly and singleton enforcement both live in Python (`frappe/shell/manifest.py`),
// not here. #42069 put the check "at manifest assembly, before vite starts" — and
// assembly is Python's, so a conflict fails before vite is even spawned. Keeping a
// second implementation on this side would be one of the hand-synced copies the map
// has been retiring.

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

/** Every app on the bench, contributing or not -- see the plugin's doctype-name index. */
export function readAllSourceDirs() {
	return read().source_dirs;
}
