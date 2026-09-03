// Script-named icons bridged to CSS classes at runtime: `lucide-*` classes are built
// at build time and a Page Script can never ship a file, so the rule is built from the sprite.
import type { SurfaceItem } from "./types";

const PREFIX = "lucide-";
const SPRITE_ID = "lucide-sprite";
const STYLE_ID = "record-page-icon-classes";
/** `lucideIconsPlugin`'s normalization; lucide itself ships 2. */
const STROKE_WIDTH = 1.5;

const bridged = new Set<string>();
let warnedMissingSprite = false;

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
	const geometry = symbolGeometry(icon.slice(PREFIX.length));
	if (geometry) addRule(icon, dataUri(geometry));
}

function symbolGeometry(name: string) {
	const sprite = document.getElementById(SPRITE_ID);
	if (!sprite) {
		// Once per session, not once per icon: absent sprite means every icon is absent.
		if (!warnedMissingSprite)
			console.warn("[record-page] lucide sprite missing; script-named icons will not render");
		warnedMissingSprite = true;
		return null;
	}
	// Scoped to the sprite: symbol ids are bare words like 'flag' that collide readily.
	const symbol = sprite.querySelector(`#${CSS.escape(name)}`);
	if (!symbol) console.warn(`[record-page] unknown lucide icon '${PREFIX}${name}'`);
	return symbol?.innerHTML ?? null;
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
