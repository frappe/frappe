import { acts, type ActOption, type AvailableAct } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { EditorRow } from "./draft";

/** The most bytes a stored payload takes as compact JSON (`frappe/shell/act_row.py` refuses more). */
export const PAYLOAD_CAP_BYTES = 128;

// The server's act name: a shell act, or an app's global act.
const ACT_NAME = /^shell\.[a-z0-9_]+(\.[a-z0-9_]+)?$/;

/** The acts the palette's first step lists, for the person who is editing, that a row can name. */
export function pickableActs(): AvailableAct[] {
	return acts
		.listed()
		.filter(
			(act) =>
				ACT_NAME.test(act.name) &&
				byteLength(JSON.stringify(payloadOf(act.name))) <= PAYLOAD_CAP_BYTES
		)
		.sort((a, b) => a.label!.localeCompare(b.label!));
}

type Payload = { act: string; value?: unknown };

/** The row's payload: with a preset it carries its `value`, and without one the click asks. */
export function payloadOf(act: string, option?: ActOption): Payload {
	return option ? { act, value: option.value } : { act };
}

function byteLength(text: string): number {
	return new TextEncoder().encode(text).length;
}

/** Why an option cannot be a row's preset, or null when it can. */
export function optionRefusal(act: string, option: ActOption): string | null {
	if (!survivesJson(option.value)) return __("Can't be saved");
	if (byteLength(JSON.stringify(payloadOf(act, option))) > PAYLOAD_CAP_BYTES) return __("Too long to save");
	return null;
}

function isPlain(value: object): boolean {
	const proto = Object.getPrototypeOf(value);
	return proto === Object.prototype || proto === Array.prototype || proto === null;
}

/** A stable key for an option: the same option from a re-asked list gets the same key. */
export function keyOf(option: ActOption): string {
	return survivesJson(option.value) ? JSON.stringify([option.label, option.value]) : option.label;
}

function survivesJson(value: unknown): boolean {
	try {
		return isDeepEqual(JSON.parse(JSON.stringify(value)), value);
	} catch {
		return false;
	}
}

// JSON drops an undefined field, turns NaN into null and a Map or a class instance into `{}`.
function isDeepEqual(a: unknown, b: unknown): boolean {
	if (Object.is(a, b)) return true;
	if (typeof a !== "object" || typeof b !== "object" || !a || !b) return false;
	if (!isPlain(b)) return false;
	if (Array.isArray(a) !== Array.isArray(b)) return false;
	const keys = Object.keys(a);
	if (keys.length !== Object.keys(b).length) return false;
	return keys.every((key) =>
		isDeepEqual((a as Record<string, unknown>)[key], (b as Record<string, unknown>)[key])
	);
}

/** The row an act, and its preset when it has one, adds. Label and icon are written so it draws at first paint; the icon is a sprite name, not a `lucide-` one. */
export function actRow(act: AvailableAct, option?: ActOption): Omit<EditorRow, "key"> {
	const icon = (option?.icon ?? act.icon)?.replace(/^lucide-/, "");
	return {
		item_type: "Act",
		payload: payloadOf(act.name, option),
		label: option ? `${act.label}: ${option.label}` : act.label,
		...(icon ? { icon } : {}),
	};
}

/** Whether a sidebar's visible rows are Acts alone: none of them opens a page, so it has none to open. */
export function hasNoPageToOpen(rows: EditorRow[]): boolean {
	const drawn = rows.filter((row) => !isShut(rows, row) && row.item_type !== "Section");
	return drawn.length > 0 && drawn.every((row) => row.item_type === "Act");
}

/** A row is shut when it, or a row above it, is hidden (saving takes its whole branch off), or when it has no access itself (its allowed children stay). */
function isShut(rows: EditorRow[], row: EditorRow): boolean {
	if (row.no_access) return true;
	const seen = new Set<string>();
	let at: EditorRow | undefined = row;
	while (at && !seen.has(at.key)) {
		if (at.hidden) return true;
		seen.add(at.key);
		const parentKey: string | undefined = at.parent_key;
		at = rows.find((r) => r.key === parentKey);
	}
	return false;
}
