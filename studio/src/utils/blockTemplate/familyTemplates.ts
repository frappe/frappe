import type { BlockOptions, BlockStyleMap, Slot } from "@/types";
import type { TextBlockProps } from "@/types/studio_components/TextBlock";

export const familyTemplates = {
	list: listTemplate,
	"list-row": listRowTemplate,
	"list-rows": listRowsTemplate,
	"list-header": listHeaderTemplate,
	"list-cell": listCellTemplate,
	"list-header-cell": listHeaderCellTemplate,
	"list-header-cell-sort": listHeaderCellSortTemplate,
	"settings-dialog": settingsDialogTemplate,
	sidebar: sidebarTemplate,
	"sidebar-label": sidebarLabelTemplate,
} satisfies Record<string, () => BlockOptions>;

const MEMBERS = [
	{ name: "Rosa Diaz", email: "rosa@example.com", role: "Admin", since: "2021-06" },
	{ name: "Jake Peralta", email: "jake@example.com", role: "Member", since: "2022-01" },
	{ name: "Amy Santiago", email: "amy@example.com", role: "Admin", since: "2020-11" },
	{ name: "Terry Jeffords", email: "terry@example.com", role: "Member", since: "2023-03" },
	{ name: "Raymond Holt", email: "holt@example.com", role: "Guest", since: "2024-08" },
];

function listTemplate(): BlockOptions {
	return {
		componentName: "List",
		blockName: "List",
		componentProps: {
			columns: ["minmax(0, 1fr)", "7rem", "8rem", "3rem"],
			rowHeight: 56,
		},
		baseStyles: { width: "100%" } as BlockStyleMap,
		children: [
			{
				componentName: "ListHeader",
				children: [
					listHeaderCell("Member"),
					listHeaderCell("Role"),
					listHeaderCell("Member since", { justifyContent: "flex-end" }),
					// empty header over the row-action column
					{ componentName: "ListHeaderCell" },
				],
			},
			{
				componentName: "ListRows",
				componentProps: { items: MEMBERS },
				// Row template in a real slot so item/index/value reach it.
				componentSlots: withDefaultSlot([
					{
						componentName: "ListRow",
						// `value` is the row identity used by selection / active-row state.
						// Baked from the scope so authors don't wire it by hand.
						componentProps: { value: "{{ value }}" },
						children: [
							memberCell(),
							listCell("{{ item.role }}", { color: "var(--ink-gray-7)" }),
							listCell(
								"{{ item.since }}",
								{ color: "var(--ink-gray-6)" },
								{ justifyContent: "flex-end" }
							),
							{
								componentName: "ListCell",
								baseStyles: { justifyContent: "flex-end" } as BlockStyleMap,
								children: [
									{
										componentName: "Button",
										componentProps: { variant: "ghost", icon: "lucide-trash-2", label: "Remove member" },
									},
								],
							},
						],
					},
				]),
			},
		],
	};
}

// Avatar with the member's name and email stacked beside it.
function memberCell(): BlockOptions {
	return {
		componentName: "ListCell",
		children: [
			{
				componentName: "Avatar",
				componentProps: { label: "{{ item.name }}", size: "xl", shape: "circle" },
			},
			{
				componentName: "container",
				originalElement: "div",
				baseStyles: {
					display: "flex",
					flexDirection: "column",
					marginLeft: "12px",
					minWidth: "0px",
				} as BlockStyleMap,
				children: [
					{
						...textBlock("{{ item.name }}", { color: "var(--ink-gray-8)" }, "text-base"),
						classes: ["truncate"],
					},
					{
						...textBlock("{{ item.email }}", { marginTop: "2px", color: "var(--ink-gray-5)" }, "text-sm"),
						classes: ["truncate"],
					},
				],
			},
		],
	};
}

// A minimal two-tab settings dialog
function settingsDialogTemplate(): BlockOptions {
	return {
		componentName: "SettingsDialog",
		blockName: "Settings Dialog",
		componentProps: {
			modelValue: false,
			shortcut: false,
			unmountOnHide: false,
			// active tab
			tab: "profile",
		},
		children: [
			{
				componentName: "SettingsSidebar",
				children: [
					{
						componentName: "SettingsNavGroup",
						componentProps: { label: "User settings" },
						children: [navItem("profile", "Profile"), navItem("notifications", "Notifications")],
					},
				],
			},
			{
				componentName: "SettingsContent",
				children: [
					settingsPanel("profile", "Profile", "How you appear across the app.", [
						settingsRow("Full name", "Your display name.", {
							componentName: "TextInput",
							componentProps: { modelValue: "Alex Rivera" },
						}),
					]),
					settingsPanel("notifications", "Notifications", "", [
						settingsRow("Enable email digests", "Send a summary of missed activity.", {
							componentName: "Switch",
							componentProps: { modelValue: true },
						}),
					]),
				],
			},
		],
	};
}

function sidebarTemplate(): BlockOptions {
	return {
		componentName: "Sidebar",
		blockName: "Sidebar",
		children: [
			{
				componentName: "SidebarHeader",
				componentProps: { title: "Frappe", subtitle: "Jane Doe" },
			},
			{
				componentName: "container",
				originalElement: "div",
				baseStyles: {
					display: "flex",
					flexDirection: "column",
					flex: "1",
					minHeight: "0px",
					overflowY: "auto",
					padding: "4px 8px",
				} as BlockStyleMap,
				children: [
					sidebarLabel("Menu"),
					sidebarItem("Home", "lucide-house"),
					sidebarItem("Profile", "lucide-user-pen"),
					sidebarItem("Settings", "lucide-settings"),
				],
			},
			{
				componentName: "container",
				originalElement: "div",
				baseStyles: { marginTop: "auto", padding: "0px 8px 8px" } as BlockStyleMap,
				children: [{ componentName: "SidebarCollapseToggle" }],
			},
		],
	};
}

// --- Standalone part templates ------------------------------------------
// A bare row/header/cell paints zero pixels on canvas (grid boxes with no content),
// so individually dropped parts seed minimal visible content. Seeded counts won't
// always match the surrounding List's columns — the column manager's mismatch
// banner guides the fix-up.

function listRowTemplate(): BlockOptions {
	return { componentName: "ListRow", children: [listCell("—"), listCell("—")] };
}

function listHeaderTemplate(): BlockOptions {
	return {
		componentName: "ListHeader",
		children: [listHeaderCell("Column 1"), listHeaderCell("Column 2")],
	};
}

// Sample items + a row template in a real slot (scoped item/index/value) — the same
// shape as the full list template, with neutral fields.
function listRowsTemplate(): BlockOptions {
	return {
		componentName: "ListRows",
		componentProps: {
			items: [
				{ name: "1", title: "First item", status: "Open" },
				{ name: "2", title: "Second item", status: "Done" },
				{ name: "3", title: "Third item", status: "Open" },
			],
		},
		componentSlots: withDefaultSlot([
			{
				componentName: "ListRow",
				componentProps: { value: "{{ value }}" },
				children: [listCell("{{ item.title }}"), listCell("{{ item.status }}")],
			},
		]),
	};
}

function listCellTemplate(): BlockOptions {
	return listCell("Cell");
}

function listHeaderCellTemplate(): BlockOptions {
	return listHeaderCell("Label");
}

function listHeaderCellSortTemplate(): BlockOptions {
	return { componentName: "ListHeaderCellSort", children: [textBlock("Label")] };
}

// A bare SidebarLabel paints nothing — its text lives in the default slot.
function sidebarLabelTemplate(): BlockOptions {
	return sidebarLabel("Label");
}

function sidebarLabel(text: string): BlockOptions {
	return { componentName: "SidebarLabel", children: [textBlock(text)] };
}

function sidebarItem(label: string, icon: string): BlockOptions {
	return { componentName: "SidebarItem", componentProps: { label, icon } };
}

export function listHeaderCell(label: string, styles: BlockStyleMap = {}): BlockOptions {
	return { componentName: "ListHeaderCell", baseStyles: styles, children: [textBlock(label)] };
}

export function listCell(
	text: string,
	textStyles: BlockStyleMap = {},
	cellStyles: BlockStyleMap = {}
): BlockOptions {
	return { componentName: "ListCell", baseStyles: cellStyles, children: [textBlock(text, textStyles)] };
}

export function navItem(value: string, label: string): BlockOptions {
	// `value` pairs a nav item with the SettingsPanel that shares it.
	return {
		componentName: "SettingsNavItem",
		componentProps: { value },
		children: [textBlock(label)],
	};
}

export function settingsPanel(
	value: string,
	title: string,
	description: string,
	rows: BlockOptions[]
): BlockOptions {
	return {
		componentName: "SettingsPanel",
		componentProps: { value },
		children: [
			{
				componentName: "SettingsHeader",
				componentProps: description ? { title, description } : { title },
			},
			{
				componentName: "SettingsBody",
				children: rows,
			},
		],
	};
}

function settingsRow(title: string, description: string, control: BlockOptions): BlockOptions {
	return {
		componentName: "SettingsRow",
		componentProps: { title, description },
		children: [control],
	};
}

function textBlock(
	text: string,
	styles: BlockStyleMap = {},
	fontSize?: TextBlockProps["fontSize"]
): BlockOptions {
	return {
		componentName: "TextBlock",
		baseStyles: styles,
		componentProps: { text, tag: "span", ...(fontSize && { fontSize }) },
	};
}

// Wrap blocks as a component's default-slot content to access slot scope
function withDefaultSlot(content: BlockOptions[]): Record<string, Slot> {
	content.forEach((block) => (block.parentSlotName = "default"));
	return {
		default: { slotName: "default", slotContent: content },
	} as unknown as Record<string, Slot>;
}
