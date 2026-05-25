/**
 * esbuild plugin: resolve `~icons/lucide/<name>` virtual imports.
 *
 * This is the esbuild port of frappe-ui/vite/lucideIcons.js. We need it
 * because Frappe's Desk islands compile frappe-ui from `.vue` source via
 * esbuild, and ~16 components (mostly TextEditor + a few other SFCs)
 * still use the unplugin-icons virtual-module form
 *   `import HeartIcon from '~icons/lucide/heart'`.
 *
 * Behaviour parity with the Vite plugin:
 *   • Reads SVGs from the `lucide-static` package.
 *   • Generates a tiny Vue render component per icon (no global registration
 *     needed; esbuild bundles each module on demand).
 *   • Normalises stroke-width from 2 → 1.5 to match the frappe-ui visual
 *     style (the Vite plugin does the same).
 *   • Maps camelCase keys exported by `lucide-static` to both kebab-case
 *     variants used by unplugin-icons, so e.g. `~icons/lucide/bar-chart-2`
 *     and `~icons/lucide/bar-chart2` both resolve correctly.
 *   • Missing icons (brand icons removed in lucide v1: youtube, github, …)
 *     emit a "circle-help"-shaped placeholder and warn once.
 *
 * What it deliberately does NOT do:
 *   • The Vite version also registers unplugin-auto-import + unplugin-vue-
 *     components. Those are docs-site IDE conveniences (so SFCs can use
 *     `<LucideHeart />` without an explicit import). The Desk bundle is
 *     always explicitly imported, so we don't need them here.
 */
const LucideIcons = require("lucide-static");

// Fallback SVG inner content used when an icon is missing from lucide-static.
// Visually matches the lucide "circle-help" glyph so missing icons are
// identifiable in the UI without crashing the build.
const FALLBACK_INNER_HTML =
	'<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>';

const NAMESPACE = "frappe-ui-lucide";
const VIRTUAL_PREFIX = "~icons/lucide/";

const warnedIcons = new Set();

function camelToDash(key) {
	// barChart2 -> bar-chart-2
	let withNumber = key.replace(/[A-Z0-9]/g, (m) => "-" + m.toLowerCase());
	if (withNumber.startsWith("-")) {
		withNumber = withNumber.substring(1);
	}
	// barChart2 -> bar-chart2  (unplugin-icons resolver doesn't put a dash
	// before numbers; we need both spellings to match either consumer)
	let withoutNumber = key.replace(/[A-Z]/g, (m) => "-" + m.toLowerCase());
	if (withoutNumber.startsWith("-")) {
		withoutNumber = withoutNumber.substring(1);
	}
	if (withNumber !== withoutNumber) {
		return [withNumber, withoutNumber];
	}
	return [withNumber];
}

function getIcons() {
	const icons = {};
	for (const key in LucideIcons) {
		if (key === "default") continue;
		let svg = LucideIcons[key];
		if (typeof svg === "string" && svg.includes("stroke-width")) {
			svg = svg.replace(/stroke-width="2"/g, 'stroke-width="1.5"');
		}
		icons[key] = svg;
		for (const dashKey of camelToDash(key)) {
			if (dashKey !== key) icons[dashKey] = svg;
		}
	}
	return icons;
}

function generateIconModule(svg) {
	const inner = svg.match(/<svg[^>]*>([\s\S]*)<\/svg>/);
	const innerHTML = inner ? inner[1].replace(/>\s+</g, "><").trim() : "";
	return `
import { h } from 'vue'
export default {
  inheritAttrs: false,
  render() {
    return h('svg', {
      xmlns: 'http://www.w3.org/2000/svg',
      width: '24',
      height: '24',
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      'stroke-width': '1.5',
      'stroke-linecap': 'round',
      'stroke-linejoin': 'round',
      ...this.$attrs,
      innerHTML: ${JSON.stringify(innerHTML)},
    })
  }
}
`;
}

function generateFallbackModule(iconName) {
	const safe = iconName.replace(/[^a-zA-Z0-9_]/g, "_");
	return `
import { h } from 'vue'
export default {
  name: 'LucideMissing_${safe}',
  inheritAttrs: false,
  render() {
    return h('svg', {
      xmlns: 'http://www.w3.org/2000/svg',
      width: '24',
      height: '24',
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      'stroke-width': '1.5',
      'stroke-linecap': 'round',
      'stroke-linejoin': 'round',
      'data-lucide-missing': ${JSON.stringify(iconName)},
      ...this.$attrs,
      innerHTML: ${JSON.stringify(FALLBACK_INNER_HTML)},
    })
  }
}
`;
}

const lucideIconsPlugin = {
	name: "frappe-ui-lucide-icons",
	setup(build) {
		const icons = getIcons();

		build.onResolve({ filter: /^~icons\/lucide\// }, (args) => {
			const iconName = args.path.slice(VIRTUAL_PREFIX.length);
			return { path: iconName, namespace: NAMESPACE };
		});

		build.onLoad({ filter: /.*/, namespace: NAMESPACE }, (args) => {
			const iconName = args.path;
			const svg = icons[iconName];
			if (!svg) {
				if (!warnedIcons.has(iconName)) {
					warnedIcons.add(iconName);
					console.warn(
						`[frappe-ui-lucide-icons] icon "${iconName}" not found in lucide-static ` +
							`(brand icons were removed in lucide v1). Rendering a placeholder. ` +
							`Replace ~icons/lucide/${iconName} with an SVG asset or a different icon.`
					);
				}
				return { contents: generateFallbackModule(iconName), loader: "js" };
			}
			return { contents: generateIconModule(svg), loader: "js" };
		});
	},
};

module.exports = lucideIconsPlugin;
