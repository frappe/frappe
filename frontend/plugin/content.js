// The one stylesheet's content list: the build styles what it has source for. A published
// file's folder is scanned wherever it sits; a published package ships its own CSS.

import { dirname, join } from "node:path";
import { isFileValue } from "./importMap.js";

const SOURCE = "**/*.{vue,js,ts}";

/** Each published file value's folder, rooted at its app's source dir; a package value adds nothing. */
export function publishedFolders(manifest) {
	const folders = new Set();
	for (const { source_dir, import_map } of manifest) {
		for (const value of Object.values(import_map ?? {})) {
			if (isFileValue(value)) folders.add(dirname(join(source_dir, value)));
		}
	}
	return [...folders];
}

/** Every app's `frontend/` and `custom/` folders plus its published files; `public/` is compiled output. */
export function appContent(manifest) {
	return [
		...manifest.flatMap(({ source_dir }) => [
			join(source_dir, "**/frontend", SOURCE),
			join(source_dir, "**/custom", SOURCE),
		]),
		...publishedFolders(manifest).map((folder) => join(folder, SOURCE)),
		...manifest.map(({ source_dir }) => "!" + join(source_dir, "**/public/**")),
	];
}
