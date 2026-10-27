// The states a page shows in place of its content, and which one a failed read shows.
import { isApiError } from "@framework/ui/api";
import { htmlToText } from "@framework/ui/RichText";

export type PageStateName =
	| "empty"
	| "filtered"
	| "nothingToOpen"
	| "notFound"
	| "noPermission"
	| "offline"
	| "failed";

/** What the frame draws in place of a page's content. */
export interface PageStateValue {
	name: PageStateName;
	/** The server's message, as text. */
	message?: string;
	/** What a no permission state refused; without it, the state says the person may not see this. */
	act?: { name: "create"; doctype: string };
	/** Offered as Try again; a returned promise holds the button busy until it settles. */
	retry?: () => unknown;
}

/** The state a failed read shows: offline, no permission, not found, or failed with the server's message. */
export function failedState(failure: unknown, retry: () => unknown): PageStateValue {
	if (isOffline(failure)) return { name: "offline", retry };
	if (isApiError(failure) && failure.status === 403) return { name: "noPermission" };
	if (isApiError(failure) && failure.status === 404) return { name: "notFound" };
	return { name: "failed", message: serverMessage(failure), retry };
}

// A reply with a status proves the server answered, whatever the browser says.
function isOffline(failure: unknown) {
	if (isApiError(failure) && failure.status > 0) return false;
	return !navigator.onLine || (isApiError(failure) && failure.type === "NetworkError");
}

// Only the server's words are shown: the wrapper's own errors name a path, not a reason.
function serverMessage(failure: unknown) {
	if (!isApiError(failure) || WRAPPER_ERRORS.has(failure.type)) return undefined;
	return htmlToText(failure.message) || undefined;
}

const WRAPPER_ERRORS = new Set(["NetworkError", "HTTPError", "InvalidResponse", "MissingData"]);
