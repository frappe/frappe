// The panel's width and whether it is a strip. Both depend on the screen, so the browser
// is their unit, keyed by user because a profile is shared and a reader's view is not.
import { computed, ref, watch } from "vue";

export const MIN_WIDTH = 320;
export const MAX_WIDTH = 640;
export const DEFAULT_WIDTH = 380;
export const COLLAPSE_AT = 260;
export const REOPEN_DISTANCE = 40;
export const SNAP_DISTANCE = 7;
export const STRIP_WIDTH = 48;

const WIDTH_KEY = "frappe:desk:record-panel-width";
const COLLAPSED_KEY = "frappe:desk:record-panel-collapsed";

export function usePanelGeometry(user: string) {
	const storedWidth = ref(clampWidth(Number(read(WIDTH_KEY, user))));
	const collapsed = ref(read(COLLAPSED_KEY, user) === true);

	const width = computed({
		get: () => storedWidth.value,
		set: (value: number) => (storedWidth.value = clampWidth(value)),
	});

	watch(storedWidth, (value) => write(WIDTH_KEY, user, value));
	watch(collapsed, (value) => write(COLLAPSED_KEY, user, value));

	return { width, collapsed };
}

/** What a drag on the edge amounts to: a new width, a toggle, or neither yet. */
export function dragOutcome(
	open: boolean,
	startWidth: number,
	distance: number
): { width?: number; toggle?: boolean } {
	if (!open) return distance >= REOPEN_DISTANCE ? { toggle: true } : {};
	const width = startWidth + distance;
	// A drag that ends in a collapse commits no resize, so the strip reopens at the width
	// it had before the drag squashed it against the minimum.
	if (width < COLLAPSE_AT) return { width: clampWidth(startWidth), toggle: true };
	return { width: snapToDefault(clampWidth(width)) };
}

/** A drag that passes close to the default width settles on it. */
export function snapToDefault(width: number) {
	return Math.abs(width - DEFAULT_WIDTH) <= SNAP_DISTANCE ? DEFAULT_WIDTH : width;
}

/** Clamped on read as well as on drag, so a hand-edited value cannot escape the range. */
export function clampWidth(width: number) {
	if (!Number.isFinite(width) || width === 0) return DEFAULT_WIDTH;
	return Math.min(Math.max(width, MIN_WIDTH), MAX_WIDTH);
}

function read(key: string, user: string): unknown {
	try {
		const parsed = JSON.parse(localStorage.getItem(key) ?? "null");
		return parsed && typeof parsed === "object" ? parsed[user] : undefined;
	} catch {
		// Storage throws in a sandboxed frame; a value it cannot parse is no value.
		return undefined;
	}
}

function write(key: string, user: string, value: unknown) {
	try {
		const parsed = JSON.parse(localStorage.getItem(key) ?? "null");
		const stored = parsed && typeof parsed === "object" ? parsed : {};
		localStorage.setItem(key, JSON.stringify({ ...stored, [user]: value }));
	} catch {
		// Full or forbidden. The panel keeps its width for this page.
	}
}
