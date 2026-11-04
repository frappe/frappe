// The body a `pages.json` dialog entry names, loaded when the dialog opens: a page's `component`, as
// for a replacement page. A body that fails to load shows its error in the dialog's frame.
import { defineAsyncComponent, defineComponent, h, type Component } from "vue";
import { ErrorMessage } from "frappe-ui";
import { __ } from "@/i18n";
import { errorMessage } from "@/recordPage";
import { pageOf } from "@/router/mainPage";

export function recordBodyComponent(loader: () => Promise<unknown>): Component {
	return defineAsyncComponent({
		loader: () => loader().then((module) => pageOf(module as Component)),
		delay: 0,
		errorComponent: defineComponent({
			props: ["error"],
			setup: (props) => () =>
				h(ErrorMessage, { message: `${__("Could not load this view")}: ${errorMessage(props.error)}` }),
		}),
	});
}
