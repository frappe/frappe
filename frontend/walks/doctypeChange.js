// A DocType change the record page does not show: a Quick Entry Form Layout the walk saves and deletes.

import { withRequest } from "./cachedScript.js";
import { WalkLayouts } from "./walkLayouts.js";

// Matches no record, so the page keeps its layout; the comment names the row's owner.
const MARKER = "false /* Return Visit Walk */";
const TYPES = ["Quick Entry"];

const walkLayouts = new WalkLayouts(MARKER);

/** Saves a marked Quick Entry layout; the server tells open desks that the DocType changed. */
export function changeDoctype(doctype) {
	return withRequest((request) =>
		walkLayouts.insert(request, { dt: doctype, type: "Quick Entry", layout: "[]" })
	);
}

/** Deletes the rows this run saved, then a crashed run's rows on the same doctype. */
export function removeDoctypeChange(doctype) {
	return withRequest(async (request) => {
		await walkLayouts.removeInserted(request);
		await walkLayouts.removeLeftovers(request, doctype, TYPES);
	});
}
