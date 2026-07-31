import type { BlockOptions, BlockStyleMap, Slot } from "@/types";
import type { TextBlockProps } from "@/types/studio_components/TextBlock";

// Block templates for component families (List, Settings Dialog). Families are
// compositional: one drop of the primary should yield a whole, working tree.
// Content nests through `children` (which Studio renders into each component's
// default slot) — the one exception is ListRows: its row template must live in a
// real slot, because Studio injects the scoped-slot props (item/index/value) only
// into slot content, not children. Everything below ListRows inherits that scope
// ambiently, so it can stay as plain children.

// A List seeded in column mode, mirroring the frappe-ui "Columns" story
// (docs/molecules/list): a members table with an avatar + name/email cell, role,
// a right-aligned date, and a trailing action button. Row identity defaults to
// the item's `name`. Sort chrome (ListHeaderCellSort) is deliberately left out —
// it needs app-owned sort state, which a seeded template can't provide.
const MEMBERS = [
	{ name: "Rosa Diaz", email: "rosa@example.com", role: "Admin", since: "2021-06" },
	{ name: "Jake Peralta", email: "jake@example.com", role: "Member", since: "2022-01" },
	{ name: "Amy Santiago", email: "amy@example.com", role: "Admin", since: "2020-11" },
	{ name: "Terry Jeffords", email: "terry@example.com", role: "Member", since: "2023-03" },
	{ name: "Raymond Holt", email: "holt@example.com", role: "Guest", since: "2024-08" },
];

export function listTemplate(): BlockOptions {
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

// A minimal two-tab settings dialog. SettingsDialog renders through frappe-ui's Dialog
// (a teleported modal), so it's edited on a fragment canvas (editInFragmentMode) via
// ProxySettingsDialog, which renders the inner TabsRoot inline. `shortcut` and
// `unmountOnHide` are turned off here because both are hostile to the editor.
export function settingsDialogTemplate(): BlockOptions {
	return {
		componentName: "SettingsDialog",
		blockName: "Settings Dialog",
		componentProps: {
			modelValue: false,
			shortcut: false,
			unmountOnHide: false,
			// select the first nav item so its panel shows when the dialog opens (and so the
			// editor proxy isn't blank — reka-ui shows no panel until a tab is active)
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

function navItem(value: string, label: string): BlockOptions {
	// `value` pairs a nav item with the SettingsPanel that shares it.
	return {
		componentName: "SettingsNavItem",
		componentProps: { value },
		children: [textBlock(label)],
	};
}

function settingsPanel(
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

// Wrap blocks as a component's default-slot content. Only ListRows needs this:
// its scoped-slot props reach expressions solely through slot content. Each block
// is tagged with parentSlotName so slot bookkeeping (selection, removal) works;
// Block's constructor upgrades these loose options into real Slot/Block instances
// (slotId, parentBlockId, reactive Blocks) via initializeSlots().
function withDefaultSlot(content: BlockOptions[]): Record<string, Slot> {
	content.forEach((block) => (block.parentSlotName = "default"));
	return {
		default: { slotName: "default", slotContent: content },
	} as unknown as Record<string, Slot>;
}
