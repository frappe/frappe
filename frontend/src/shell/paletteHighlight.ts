// Keeps the palette's keyboard on a row when rows arrive late, as records from the server do.
import { defineComponent, watch, type PropType } from "vue";
import { injectListboxRootContext } from "reka-ui";

/** Inside the palette: once the drawn rows change and the highlighted one is gone, the first takes it. */
export const PaletteHighlight = defineComponent({
	name: "PaletteHighlight",
	props: { rows: { type: Array as PropType<unknown[]>, required: true } },
	setup(props) {
		// frappe-ui's palette highlights the first row only on open and on a change of query.
		const listbox = injectListboxRootContext();
		watch(
			() => props.rows,
			() => {
				if (!listbox.highlightedElement.value?.isConnected) listbox.highlightFirstItem();
			},
			{ flush: "post" }
		);
		return () => null;
	},
});
