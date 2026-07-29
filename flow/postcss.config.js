import tailwindcss from "tailwindcss";
import autoprefixer from "autoprefixer";
import prefixSelector from "postcss-prefix-selector";

// The bundle's CSS is injected into the desk's <head>, so every rule must be
// confined to the panel root `#flow-root` — otherwise frappe-ui's preflight,
// form resets and utilities would bleed onto the surrounding desk.
const ROOT = "#flow-root";

export default {
	plugins: [
		tailwindcss(),
		autoprefixer(),
		prefixSelector({
			prefix: ROOT,
			transform(prefix, selector, prefixedSelector) {
				// Keyframe steps (`0%`, `from`, `to`) must never be prefixed.
				if (/^(\d+%|from|to)$/.test(selector)) return selector;
				// Theme tokens (`:root { --ink-… }`) live on the panel root itself so
				// the panel can carry its own light/dark scope.
				if (selector === ":root") return prefix;
				// `[data-theme="dark"] …` → applies when the panel root is dark
				// (its data-theme is synced to the desk in main.js).
				if (/^\[data-theme/.test(selector)) return `${prefix}${selector}`;
				// Document-level selectors collapse onto the panel root.
				if (selector === "html" || selector === "body" || selector === ":host")
					return prefix;
				return prefixedSelector;
			},
		}),
	],
};
