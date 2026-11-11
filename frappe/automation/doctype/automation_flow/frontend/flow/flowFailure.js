import { __ } from "frappe/i18n";
import { isApiError } from "@framework/ui/api";
import { htmlToText } from "@framework/ui/RichText";

/** What the page says when the flow could not be read. */
export function failureState(failure) {
	if (!failure) return {};
	if (isApiError(failure) && failure.status === 403)
		return {
			title: __("Not permitted"),
			description: __("Only a System Manager can open Automation Flows."),
		};
	if (isApiError(failure) && failure.status === 404)
		return { title: __("Flow not found"), description: __("It may have been deleted.") };
	return {
		title: __("The flow could not be opened"),
		description: (isApiError(failure) && htmlToText(failure.message)) || "",
		retry: true,
	};
}
