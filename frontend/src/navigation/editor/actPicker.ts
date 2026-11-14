// The Act step of the add-row picker: which acts and options a person may pick, and the row they
// make. The save (`frappe/shell/act_row.py`) takes the payload only in these bounds.

import { acts, type ActOption, type AvailableAct } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { listedInPalette } from "@/shell/paletteGroups";
import type { EditorRow } from "./draft";

/** The most bytes a stored payload takes as compact JSON; one row's share of the boot budget. */
export const PAYLOAD_CAP_BYTES = 128;

// The server's act name: a shell act, or an app's global act.
const ACT_NAME = /^shell\.[a-z0-9_]+(\.[a-z0-9_]+)?$/;

/** The acts the palette's first step lists, for the person who is editing, that a row can name. */
export function pickableActs(): AvailableAct[] {
	return acts
		.available()
		.filter((act) => listedInPalette(act) && ACT_NAME.test(act.name) && byteLength(act.name) <= PAYLOAD_CAP_BYTES)
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

function survivesJson(value: unknown): boolean {
	try {
		return isDeepEqual(JSON.parse(JSON.stringify(value)), value);
	} catch {
		return false;
	}
}

// `JSON.stringify(undefined)` is undefined, which does not parse back; an object with an undefined
// field or a NaN loses it, which this catches.
function isDeepEqual(a: unknown, b: unknown): boolean {
	if (Object.is(a, b)) return true;
	if (typeof a !== "object" || typeof b !== "object" || !a || !b) return false;
	if (Array.isArray(a) !== Array.isArray(b)) return false;
	const keys = Object.keys(a);
	if (keys.length !== Object.keys(b).length) return false;
	return keys.every((key) =>
		isDeepEqual((a as Record<string, unknown>)[key], (b as Record<string, unknown>)[key])
	);
}

/** The row an act, and its preset when it has one, adds: label and icon are written so it draws at first paint. */
export function actRow(act: AvailableAct, option?: ActOption): Omit<EditorRow, "key"> {
	const icon = option?.icon ?? act.icon;
	return {
		item_type: "Act",
		payload: payloadOf(act.name, option),
		label: option ? `${act.label}: ${option.label}` : act.label,
		...(icon ? { icon } : {}),
	};
}

/** Whether a sidebar's visible rows are Acts alone: none of them opens a page, so it has none to open. */
export function hasNoPageToOpen(rows: EditorRow[]): boolean {
	const drawn = rows.filter((row) => !row.hidden && !row.no_access && row.item_type !== "Section");
	return drawn.length > 0 && drawn.every((row) => row.item_type === "Act");
}
