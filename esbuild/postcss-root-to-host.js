/**
 * PostCSS plugin: rewrite `:root` → `:host` for Shadow DOM islands.
 *
 * frappe-ui's Tailwind preset emits its design tokens (CSS custom properties)
 * on `:root` (and `:root`-prefixed dark-theme selectors). Inside a shadow tree
 * `:root` matches nothing — it only ever matches the document's root element —
 * so those tokens would never reach components mounted in a shadow root.
 *
 * Rewriting `:root` to `:host` puts the tokens on the shadow host element.
 * Custom properties are inherited, so they flow down to every node inside the
 * shadow tree (the mount root and the teleport/portal target alike).
 *
 * Only used by the Shadow DOM island build (esbuild/build-islands.mjs). In the
 * scoped-island approach the CSS lives in the light DOM and `:root` is correct.
 */

/** @type {import('postcss').Plugin} */
const rootToHost = {
	postcssPlugin: "frappe-ui-root-to-host",
	Rule(rule) {
		if (typeof rule.selector === "string" && rule.selector.includes(":root")) {
			// `:root` → `:host`; `:root[data-theme="dark"]` → `:host[data-theme="dark"]`.
			rule.selector = rule.selector.replace(/:root\b/g, ":host");
		}
	},
};

module.exports = rootToHost;
