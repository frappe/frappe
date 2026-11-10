// Local only, not committed: the walk config, with `ui/` files sent as no-cache. Vite tags them
// `?v=<hash>` as immutable, and the hash stays the same across restarts.
import walk from "./vite.walk.config.js";

export default (env) => {
	const config = walk(env);
	config.plugins.push({
		name: "walk-ui-no-cache",
		configureServer(server) {
			server.middlewares.use((req, res, next) => {
				if (req.url?.startsWith("/node_modules/@framework/ui/")) {
					const set = res.setHeader.bind(res);
					res.setHeader = (name, value) =>
						set(name, name.toLowerCase() === "cache-control" ? "no-cache" : value);
				}
				next();
			});
		},
	});
	return config;
};
