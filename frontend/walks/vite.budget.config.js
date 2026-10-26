// Builds this checkout for the click-budget walk and serves the build with `vite preview`: `/apps`
// gets the built document, every other bench path goes to the bench.

import { mergeConfig } from "vite";
import walk from "./vite.walk.config.js";

// Not `/assets/`: the bench answers that path with its own build.
const BASE = "/_walk/";

export default (env) =>
	mergeConfig(walk(env), {
		base: BASE,
		build: { outDir: process.env.OUT_DIR, emptyOutDir: true },
		preview: { port: Number(process.env.WALK_PORT || 8098), strictPort: true },
		plugins: [servesBuiltApps()],
	});

function servesBuiltApps() {
	return {
		name: "walk-serves-built-apps",
		configurePreviewServer(server) {
			server.middlewares.use((request, _response, next) => {
				if (request.url === "/apps" || request.url.startsWith("/apps/"))
					request.url = `${BASE}index.html`;
				next();
			});
		},
	};
}
