// Vite dev for the walks: serves this checkout's frontend at `/apps`, which the bench otherwise
// answers with its built document; the other bench paths still go to the bench.

import { mergeConfig } from "vite";
import base from "../vite.config.js";

const BENCH_PATHS = "^/(desk|app|login|api|assets|files|private)";
// `app` without the negative lookahead also matches `/apps`.
const BENCH_PATHS_BUT_APPS = "^/(desk|app(?!s)|login|api|assets|files|private)";

export default (env) =>
	mergeConfig(base(env), {
		plugins: [servesApps()],
		// A UMD package the dep scan misses; served raw, it has no default export.
		optimizeDeps: { include: ["vuedraggable"] },
	});

function servesApps() {
	return {
		name: "walk-serves-apps",
		config(config) {
			const { proxy } = config.server;
			if (!proxy?.[BENCH_PATHS]) throw new Error(`No ${BENCH_PATHS} proxy to narrow`);
			proxy[BENCH_PATHS_BUT_APPS] = proxy[BENCH_PATHS];
			delete proxy[BENCH_PATHS];
			config.server.port = Number(process.env.WALK_PORT || 8098);
			config.server.strictPort = true;
		},
	};
}
