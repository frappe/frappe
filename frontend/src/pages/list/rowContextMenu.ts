// A row's right-click menu, built from the lists the "⋯" menu and the bulk bar draw: Open, the row's actions
// and the bulk actions for one record; with several rows selected, only the selection's bulk actions.
import type { ContextMenuOptions } from "frappe-ui";
import { __ } from "@/i18n";
import type { ListRow } from "@/listPage/types";
import type { BulkLayout, BulkMenuGroup, BulkMenuOption } from "./bulkLayout";
import type { RowMenuOption } from "./rowActions";

export interface ContextMenuInput {
	row: ListRow;
	selection: string[];
	/** The options the row's own "⋯" menu draws. */
	rowOptions: RowMenuOption[];
	layout: BulkLayout;
	open: () => void;
	openInNewTab: () => void;
	copyLink: () => void;
}

export function contextMenuOptions(input: ContextMenuInput): ContextMenuOptions {
	const bulk = bulkGroups(input.layout);
	const { selection, row } = input;
	if (selection.length > 1 && selection.includes(row.name) && bulk.length) {
		const [first, ...rest] = bulk;
		return [{ ...first, group: __("{0} selected", [selection.length]), hideLabel: false, theme: undefined }, ...rest];
	}
	return [openGroup(input), actionGroup(input), ...bulk].filter((group) => group.options.length);
}

function openGroup({ open, openInNewTab, copyLink }: ContextMenuInput): BulkMenuGroup {
	return {
		group: "",
		hideLabel: true,
		options: [
			{ label: __("Open"), icon: "lucide-arrow-up-right", onClick: open },
			{ label: __("Open in new tab"), icon: "lucide-external-link", onClick: openInNewTab },
			{ label: __("Copy link"), icon: "lucide-link", onClick: copyLink },
		],
	};
}

function actionGroup({ rowOptions }: ContextMenuInput): BulkMenuGroup {
	return { group: "", hideLabel: true, options: rowOptions };
}

// The bar's order: the buttons first, then More's groups with the danger group last.
function bulkGroups(layout: BulkLayout): BulkMenuGroup[] {
	const bar: BulkMenuOption[] = [...layout.transitions, ...layout.buttons];
	return [{ group: "", options: bar }, ...layout.menu]
		.filter((group) => group.options.length)
		.map((group) => ({ ...group, hideLabel: true }));
}
