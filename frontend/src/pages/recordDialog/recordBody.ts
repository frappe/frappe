// The body a `pages.json` dialog entry names, loaded when the dialog opens: a page's `component`, as
// for a replacement page. A body that fails to load gives way to the form, so the record stays editable.
import { defineAsyncComponent, type Component } from "vue";
import { pageOf } from "@/router/mainPage";

export function recordBodyComponent(
	loader: () => Promise<unknown>,
	failed: (error: unknown) => void
): Component {
	return defineAsyncComponent({
		loader: () =>
			loader()
				.then((module) => pageOf(module as Component))
				.catch((error) => {
					failed(error);
					return { render: () => null };
				}),
		delay: 0,
	});
}
