import type { BlockOptions, BlockStyleMap, Slot } from "@/types";

// Block templates for component families (List, Settings Dialog). Families are
// compositional: one drop of the primary should yield a whole, working tree.
// Content nests through `children` (which Studio renders into each component's
// default slot) — the one exception is ListRows: its row template must live in a
// real slot, because Studio injects the scoped-slot props (item/index/value) only
// into slot content, not children. Everything below ListRows inherits that scope
// ambiently, so it can stay as plain children.

// A List seeded in column mode: a two-column header plus ListRows bound to sample
// items, each row reading `item`/`value` from the scope ListRows exposes.
export function listTemplate(): BlockOptions {
	return {
		componentName: "List",
		blockName: "List",
		componentProps: {
			columns: ["minmax(0, 1fr)", "8rem"],
			rowHeight: 44,
		},
		baseStyles: { width: "100%" } as BlockStyleMap,
		children: [
			{
				componentName: "ListHeader",
				children: [listHeaderCell("Title"), listHeaderCell("Status")],
			},
			{
				componentName: "ListRows",
				componentProps: {
					items: [
						{ name: "1", title: "First item", status: "Open" },
						{ name: "2", title: "Second item", status: "Done" },
						{ name: "3", title: "Third item", status: "Open" },
					],
				},
				// Row template in a real slot so item/index/value reach it.
				componentSlots: withDefaultSlot([
					{
						componentName: "ListRow",
						// `value` is the row identity used by selection / active-row state.
						// Baked from the scope so authors don't wire it by hand.
						componentProps: { value: "{{ value }}" },
						children: [listCell("{{ item.title }}"), listCell("{{ item.status }}")],
					},
				]),
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

function listHeaderCell(label: string): BlockOptions {
	return { componentName: "ListHeaderCell", children: [textBlock(label)] };
}

function listCell(text: string): BlockOptions {
	return { componentName: "ListCell", children: [textBlock(text)] };
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

function textBlock(text: string): BlockOptions {
	return { componentName: "TextBlock", componentProps: { text, tag: "span" } };
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
