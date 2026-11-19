// A record address of an opted-in doctype opens the record dialog instead of a page. The
// URL stays and no history entry is made. A direct load has no page to open over: the list
// shows first, then the dialog.
import { START_LOCATION, type RouteLocationNormalized } from "vue-router";
import { opensInDialog } from "@/contributions/registry";
import { openRecordDialog, openRecordDialogAfterNavigation } from "@/shell/recordDialog";

/** The router's answer for a record route, or `undefined` when the page should render. */
export function recordDialogAnswer(
	to: RouteLocationNormalized,
	from: RouteLocationNormalized,
	doctype: string,
	app: string | null
) {
	// A saved full-page new record replaces itself with its record: that is the page, not the dialog.
	if (to.name !== "record" || from.name === "new-record" || !opensInDialog(doctype, app)) return undefined;

	const name = String(to.params.name);
	if (from === START_LOCATION) {
		openRecordDialogAfterNavigation(doctype, name);
		const { name: _, ...params } = to.params;
		return { name: "list", params, replace: true };
	}
	openRecordDialog(doctype, name, from.fullPath);
	return false;
}
