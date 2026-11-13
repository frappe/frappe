// The layout the editor opens, in the address: `?layout=side-panel&row=<id>`.
import type { LocationQuery } from "vue-router";
import type { FormLayoutType } from "@/recordPage/formLayoutSource/types";
import type { LayoutRef } from "./workingLayouts";

const KEYS: Record<FormLayoutType, string> = {
	Details: "details",
	"Side Panel": "side-panel",
	"Quick Entry": "quick-entry",
	"New Record": "new-record",
};

/** An unknown `layout` opens Details; no `row` opens the type's default. */
export function layoutFromQuery(query: LocationQuery): LayoutRef {
	const key = first(query.layout);
	const type = (Object.keys(KEYS) as FormLayoutType[]).find((each) => KEYS[each] === key) ?? "Details";
	const row = first(query.row);
	return row ? { type, id: row } : { type };
}

export function layoutQuery({ type, id }: LayoutRef): { layout: string; row?: string } {
	return id ? { layout: KEYS[type], row: id } : { layout: KEYS[type] };
}

function first(value: LocationQuery[string] | undefined): string {
	return String((Array.isArray(value) ? value[0] : value) ?? "");
}
