// Every module the cold load runs goes in one chunk beside the entry, so a lazy chunk never splits
// one out. `$initial` counts each emitted entry's imports: add a chunk by `import()`, as importMap does.

import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SHELL_ENTRY = join(dirname(fileURLToPath(import.meta.url)), "..", "src", "main.ts");

export default function entryChunk(entry = SHELL_ENTRY) {
	return {
		name: "frappe-entry-chunk",
		config: () => ({
			build: {
				rolldownOptions: {
					output: {
						codeSplitting: {
							groups: [{ name: shellChunkName(entry), tags: ["$initial"] }],
						},
					},
				},
			},
		}),
	};
}

export function shellChunkName(entry) {
	// The entry modules stay in the entry chunk: with them in the group, the entry chunk is empty
	// and rolldown folds the group into it, under the group's name, and `index.html` loses its chunk.
	return (id, context) => (id === entry || context.getModuleInfo(id)?.isEntry ? null : "shell");
}
