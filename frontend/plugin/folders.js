// Folder listing for discovery; a missing folder reads as empty.

import { readdirSync, statSync } from "node:fs";

export function directories(path) {
	try {
		return readdirSync(path, { withFileTypes: true })
			.filter((entry) => entry.isDirectory())
			.map((entry) => entry.name);
	} catch {
		return [];
	}
}

export function files(path, extension = ".js") {
	try {
		return readdirSync(path, { withFileTypes: true })
			.filter((entry) => entry.isFile() && entry.name.endsWith(extension))
			.map((entry) => entry.name);
	} catch {
		return [];
	}
}

export function isFile(path) {
	try {
		return statSync(path).isFile();
	} catch {
		return false;
	}
}
