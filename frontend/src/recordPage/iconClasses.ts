// Script-named icons bridged to CSS classes at runtime: `lucide-*` classes are built
// at build time and a Client Script can never ship a file, so the rule is built from a sprite.
import type { SurfaceItem } from "./types";

/** Resolves a bare lucide name to its symbol's inner geometry, or `null` when the host has none. */
export type IconSource = (name: string) => Promise<string | null>;

const PREFIX = "lucide-";
const STYLE_ID = "record-page-icon-classes";
/** `lucideIconsPlugin`'s normalization; lucide itself ships 2. */
const STROKE_WIDTH = 1.5;

const bridged = new Set<string>();
let source: IconSource | null = null;
let warnedNoSource = false;

/** The host's sprite lookup. The engine imports no icon tier of its own. */
export function setIconSource(next: IconSource | null) {
	source = next;
}

/** Every icon an item can name: its own, plus a tab's create-action icon. */
export function ensureIcons(item: Partial<SurfaceItem>) {
	ensureIconClass(item.icon);
	ensureIconClass(item.create?.icon);
}

/** Guarantees the class `icon` names exists. Idempotent, and safe to over-call. */
export function ensureIconClass(icon?: string) {
	// No document in the engine's node tests; built-in icons are in the bundle already.
	if (typeof document === "undefined") return;
	if (!icon?.startsWith(PREFIX) || bridged.has(icon)) return;
	bridged.add(icon);
	if (!source) {
		if (!warnedNoSource)
			console.warn("[record-page] no icon source; script-named icons will not render");
		warnedNoSource = true;
		return;
	}
	const name = icon.slice(PREFIX.length);
	source(name)
		.then((geometry) => {
			if (geometry) addRule(icon, dataUri(geometry));
			else console.warn(`[record-page] unknown lucide icon '${icon}'`);
		})
		.catch((error) => console.warn(`[record-page] icon source failed for '${icon}'`, error));
}

// The sprite's symbols carry geometry only, so rebuild the wrapper Icon.vue draws.
function dataUri(geometry: string) {
	const svg =
		`<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" ` +
		`fill="none" stroke="currentColor" stroke-width="${STROKE_WIDTH}" ` +
		`stroke-linecap="round" stroke-linejoin="round">${geometry}</svg>`;
	return `data:image/svg+xml;utf8,${encodeURIComponent(svg.replace(/\s+/g, " "))}`;
}

function addRule(className: string, uri: string) {
	styleElement().textContent +=
		`.${className}{display:block;width:1em;height:1em;background-color:currentColor;` +
		`-webkit-mask-image:url("${uri}");mask-image:url("${uri}");` +
		`-webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;` +
		`-webkit-mask-position:center;mask-position:center;` +
		`-webkit-mask-size:contain;mask-size:contain;flex-shrink:0}`;
}

function styleElement() {
	const existing = document.getElementById(STYLE_ID);
	if (existing) return existing;
	const style = document.createElement("style");
	style.id = STYLE_ID;
	// Prepended so utilities loaded later (`size-4` at the call site) still beat the `width: 1em` here.
	document.head.prepend(style);
	return style;
}
