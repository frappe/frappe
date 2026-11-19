// What an app contains: per app and permission-filtered, unlike the address table beside
// it. Fetched when a `Module Contents` row expands, never in boot.

import { runMethod } from "@framework/ui/api";

export type ContentEntry = { doctype: string; slug: string; module: string };

/**
 * Throws on failure: an empty list is a real answer here and must not be forged.
 */
export async function fetchContents(app: string, module: string): Promise<ContentEntry[]> {
	const response = await runMethod<ContentEntry[]>(
		"frappe.shell.doctypes.get_contents",
		{ app, module },
		{ http: "GET" }
	);
	return response.data;
}
