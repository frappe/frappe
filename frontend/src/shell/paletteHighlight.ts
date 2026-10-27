// Keeps the palette's keyboard on a row when rows arrive late, as records from the server do.
import { defineComponent, watch, type PropType } from "vue";
import { injectListboxRootContext } from "reka-ui";
import type { PaletteRow } from "./palette";

/** Inside the palette: the first row takes the keyboard when its row is gone, or rows reach a list with none to pick. */
export const PaletteHighlight = defineComponent({
	name: "PaletteHighlight",
	props: {
		rows: { type: Array as PropType<PaletteRow[]>, required: true },
		pinned: { type: Array as PropType<PaletteRow[]>, required: true },
	},
	setup(props) {
		// frappe-ui's palette highlights the first row only on open and on a change of query.
		const listbox = injectListboxRootContext();
		watch(
			() => [props.rows, props.pinned] as const,
			([rows], [before]) => {
				const gone = !listbox.highlightedElement.value?.isConnected;
				const arrived = !before.some(pickable) && rows.some(pickable);
				if (gone || arrived) listbox.highlightFirstItem();
			},
			{ flush: "post" }
		);
		return () => null;
	},
});

function pickable(row: PaletteRow) {
	return !row.pending && !row.disabled;
}
