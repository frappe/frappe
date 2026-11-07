import { FlowAPIError } from "@flow/ui-core/client.js";
import { call as frappeCall, upload } from "frappe-ui";

// Every request the page makes goes through here, so a Frappe failure reaches the
// store as the FlowAPIError its toasts expect, with the server's message as text.
export async function call(method, args = {}) {
	try {
		return await frappeCall(method, args);
	} catch (error) {
		throw toApiError(error);
	}
}

export async function uploadFile(file) {
	try {
		return await upload(file, { private: true });
	} catch (error) {
		throw toApiError(error);
	}
}

export function deleteFile(name) {
	return call("frappe.client.delete", { doctype: "File", name });
}

export function toApiError(error) {
	if (error instanceof FlowAPIError) return error;
	const message = error?.messages?.find(Boolean) ?? error?.message ?? "Request failed";
	return new FlowAPIError(error?.status ?? 0, stripTags(message), error);
}

// Frappe messages may carry markup (<code>…</code>); toasts show plain text.
function stripTags(text) {
	return String(text).replace(/<[^>]+>/g, "");
}
