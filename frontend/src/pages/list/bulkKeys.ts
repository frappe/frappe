// The list's selection keys as acts, so the shell's key binder runs them and the palette lists them:
// `x` toggles the row under the pointer or with focus, Shift+X extends the selection to it, `.` opens
// the bar's menu and Esc clears the selection. A key whose act is hidden does nothing.
import type { Ref } from "vue";
import type { ActEntry } from "@/acts/dispatcher";
import { __ } from "@/i18n";

export interface BulkKeysOptions {
	selection: Ref<string[]>;
	/** The row under the pointer or with focus, if any. */
	cursor: Ref<string | null>;
	/** Whether the cursor row is among the shown rows. */
	shown: (name: string) => boolean;
	/** The person's `bulk_actions` switch is off: the bar draws no menu. */
	locked: boolean;
	/** Whether the bar's More menu has anything in it; read when the key runs, as the bar's layout reads the acts. */
	hasMenu: () => boolean;
	menuOpen: Ref<boolean>;
	toggle: (name: string) => void;
	extendTo: (name: string) => void;
}

export function bulkKeyEntries(options: BulkKeysOptions): ActEntry[] {
	const { selection, cursor, shown, menuOpen } = options;
	const onRow = () => cursor.value !== null && shown(cursor.value);
	// The row keys need a row, so the palette has nothing to offer them.
	return [
		{
			item: {
				name: "toggle_row",
				label: __("Select Row"),
				key: "x",
				palette: false,
				run: () => options.toggle(cursor.value!),
			},
			hidden: !onRow(),
		},
		{
			item: {
				name: "extend_row",
				label: __("Select Rows up to Here"),
				key: "Shift+X",
				palette: false,
				run: () => options.extendTo(cursor.value!),
			},
			hidden: !onRow(),
		},
		{
			item: {
				name: "open_bulk_menu",
				label: __("Open Bulk Actions"),
				icon: "lucide-ellipsis",
				key: "Period",
				// `when`, not `hidden`: the menu is the bar's layout, which reads these entries.
				when: options.hasMenu,
				run: () => (menuOpen.value = options.hasMenu()),
			},
			hidden: !selection.value.length || options.locked,
		},
		{
			item: {
				name: "clear_selection",
				label: __("Clear Selection"),
				icon: "lucide-x",
				key: "Escape",
				run: () => (selection.value = []),
			},
			hidden: !selection.value.length,
		},
	];
}
