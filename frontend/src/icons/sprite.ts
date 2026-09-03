// The shell's runtime icon source: the sprite desk v1 loads through `app_include_icons`.
// frappe-ui's lucide paths are build-time and cannot draw a name that arrives with boot.

import { ref } from "vue";

const SPRITE_URL = "/assets/frappe/icons/lucide/icons.svg";
// Not `lucide-sprite`: that id is frappe-ui's own sprite, whose symbol ids are bare, and
// `recordPage/iconClasses.ts` reads it.
const CONTAINER_ID = "frappe-icon-sprite";

/** Flips once the sprite is in the document. A ref: not every browser lets a `<use>` pick up a symbol that arrives later. */
export const spriteLoaded = ref(false);

let loading: Promise<void> | null = null;
/** Every symbol name the sprite holds, indexed at load. */
const names = new Set<string>();

/** Fetches the sprite once per document; later callers join the first one's request. */
export function loadSprite(): Promise<void> {
	if (loading) return loading;

	loading = fetch(SPRITE_URL, { credentials: "same-origin" })
		.then((response) => {
			if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
			return response.text();
		})
		.then((svg) => {
			const element = container();
			element.innerHTML = svg;
			for (const symbol of element.querySelectorAll("symbol[id]")) names.add(symbol.id);
			spriteLoaded.value = true;
		})
		.catch((error) => {
			console.error(`[frappe] could not load the icon sprite from ${SPRITE_URL}`, error);
		});

	return loading;
}

/** Whether the sprite holds this symbol. False until the sprite lands. */
export function hasSymbol(name: string): boolean {
	// Reads the ref so a row drawn before the sprite landed recomputes when it does.
	return spriteLoaded.value && names.has(symbolId(name));
}

/** The sprite's own spelling of a symbol id. */
export function symbolId(name: string): string {
	return `icon-${name}`;
}

/** Whether an `Icon` field's value is an emoji glyph rather than a symbol name. */
// The same test as `frappe.utils.is_emoji`, since one picker writes for both.
export function isEmoji(value: string): boolean {
	return /^\p{Extended_Pictographic}(‍\p{Extended_Pictographic}|️|⃣)*$/u.test(value);
}

/** One line per name per page session, not one per row. */
const reported = new Set<string>();

/** Says a name resolved to nothing. */
export function reportMissingIcon(name: string) {
	if (reported.has(name)) return;
	reported.add(name);
	console.warn(`[frappe] no icon named '${name}' in the sprite; nothing is drawn.`);
}

/** Test-only: forget the sprite, so each test loads its own. */
export function resetSprite() {
	loading = null;
	spriteLoaded.value = false;
	names.clear();
	reported.clear();
	document.getElementById(CONTAINER_ID)?.remove();
}

function container(): HTMLElement {
	const existing = document.getElementById(CONTAINER_ID);
	if (existing) return existing;

	const element = document.createElement("div");
	element.id = CONTAINER_ID;
	element.style.display = "none";
	document.body.appendChild(element);
	return element;
}
