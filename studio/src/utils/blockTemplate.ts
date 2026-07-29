import type { BlockOptions, BlockStyleMap, Slot } from "@/types";

function getBlockTemplate(
	type:
		| "body"
		| "container"
		| "fit-container"
		| "header"
		| "list"
		| "settings-dialog"
		| "fallback-component"
		| "empty-component"
		| "missing-component"
): BlockOptions {
	switch (type) {
		case "body":
			return {
				componentId: "root",
				componentName: "div",
				blockName: "body",
				originalElement: "body",
				children: [],
				baseStyles: {
					display: "flex",
					flexDirection: "row",
					flexShrink: 0,
					width: "inherit",
					overflowX: "hidden",
					height: "100%",
				}
			};

		case "container":
			return {
				componentName: "container",
				originalElement: "div",
				blockName: "container",
				baseStyles: {
					display: "flex",
					flexDirection: "row",
					flexShrink: 1,
				} as BlockStyleMap,
			};

		case "fit-container":
			return {
				componentName: "container",
				originalElement: "div",
				blockName: "container",
				baseStyles: {
					display: "flex",
					flexDirection: "row",
					flexShrink: 1,
					height: "fit-content",
					width: "fit-content",
				} as BlockStyleMap,
			};

		case "header":
			return {
				componentName: "header",
				blockName: "header",
				originalElement: "header",
				baseStyles: {
					display: "flex",
					flexDirection: "row",
					width: "100%",
					height: "fit-content",
					padding: "10px 12px",
					backgroundColor: "var(--surface-base)",
					borderStyle: "solid",
					borderWidth: "0px 0px 1px 0px",
					borderColor: "var(--outline-gray-1)",
				} as BlockStyleMap,
				children: [
					{
						componentName: "Breadcrumbs",
						componentProps: {
							items: [
								{
									label: "Home",
									route: { name: "Home" },
								},
								{
									label: "List",
									route: "/components/breadcrumbs",
								},
							],
						}
					},
					{
						componentName: "Button",
						componentProps: {
							label: "Create",
							iconLeft: "plus",
							variant: "solid",
						},
						baseStyles: {
							marginLeft: "auto",
						} as BlockStyleMap,
					}
				],
			}

		case "list":
			return listTemplate();

		case "settings-dialog":
			return settingsDialogTemplate();

		case "fallback-component":
			return {
				componentName: "p",
				originalElement: "__raw_html__",
				innerHTML: `<div style="color: red;background: #f4f4f4;display:flex;flex-direction:column;position:static;top:auto;left:auto;width: 600px;height: 275px;align-items:center;font-size: 30px;justify-content:center"><p>Component missing</p></div>`,
				baseStyles: {
					height: "fit-content",
					width: "fit-content",
				}
			}

		case "empty-component":
			return {
				componentName: "container",
				originalElement: "div",
				baseStyles: {
					height: "200px",
					width: "100%",
				} as BlockStyleMap,
			};

		case "missing-component":
			return {
				componentName: "HTML",
				originalElement: "__raw_html__",
				innerHTML: `<div style="color:#E86C13;background:#F8F8F8;display:flex;width:300px;height:150px;align-items:center;font-size:16px;justify-content:center"><p>Component Missing</p></div>`,
				baseStyles: {
					height: "fit-content",
					width: "fit-content",
				} as BlockStyleMap,
			};
	}
}

// --- Compound component templates -------------------------------------------
// The list and settings families are compositional: one drop should yield a
// whole, working tree. Studio injects scoped-slot props (item/index/value) only
// into blocks that live in a component's *slot*, not its `children`, so these
// templates nest their content through the default slot (see withDefaultSlot).

// A List seeded in column mode: a two-column header plus ListRows bound to sample
// items, each row reading `item`/`value` from the scope ListRows exposes.
function listTemplate(): BlockOptions {
	return {
		componentName: "List",
		blockName: "List",
		componentProps: {
			columns: ["minmax(0, 1fr)", "8rem"],
			rowHeight: 44,
		},
		baseStyles: { width: "100%" } as BlockStyleMap,
		componentSlots: withDefaultSlot([
			{
				componentName: "ListHeader",
				componentSlots: withDefaultSlot([
					listHeaderCell("Title"),
					listHeaderCell("Status"),
				]),
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
				componentSlots: withDefaultSlot([
					{
						componentName: "ListRow",
						// `value` is the row identity used by selection / active-row state.
						// Baked from the scope so authors don't wire it by hand.
						componentProps: { value: "{{ value }}" },
						componentSlots: withDefaultSlot([
							listCell("{{ item.title }}"),
							listCell("{{ item.status }}"),
						]),
					},
				]),
			},
		]),
	};
}

// A minimal two-tab settings dialog. NOTE: SettingsDialog renders through
// frappe-ui's Dialog (a teleported modal), so it needs a dedicated proxy to be
// visible/editable on the canvas — dropping it seeds the tree (visible in Layers)
// but nothing renders on the page until that proxy lands. `shortcut` and
// `unmountOnHide` are turned off here because both are hostile to the editor.
function settingsDialogTemplate(): BlockOptions {
	return {
		componentName: "SettingsDialog",
		blockName: "Settings Dialog",
		componentProps: {
			modelValue: false,
			shortcut: false,
			unmountOnHide: false,
		},
		componentSlots: withDefaultSlot([
			{
				componentName: "SettingsSidebar",
				componentSlots: withDefaultSlot([
					{
						componentName: "SettingsNavGroup",
						componentProps: { label: "User settings" },
						componentSlots: withDefaultSlot([
							navItem("profile", "Profile"),
							navItem("notifications", "Notifications"),
						]),
					},
				]),
			},
			{
				componentName: "SettingsContent",
				componentSlots: withDefaultSlot([
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
				]),
			},
		]),
	};
}

function listHeaderCell(label: string): BlockOptions {
	return {
		componentName: "ListHeaderCell",
		componentSlots: withDefaultSlot([textBlock(label)]),
	};
}

function listCell(text: string): BlockOptions {
	return {
		componentName: "ListCell",
		componentSlots: withDefaultSlot([textBlock(text)]),
	};
}

function navItem(value: string, label: string): BlockOptions {
	// `value` pairs a nav item with the SettingsPanel that shares it.
	return {
		componentName: "SettingsNavItem",
		componentProps: { value },
		componentSlots: withDefaultSlot([textBlock(label)]),
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
		componentSlots: withDefaultSlot([
			{
				componentName: "SettingsHeader",
				componentProps: description ? { title, description } : { title },
			},
			{
				componentName: "SettingsBody",
				componentSlots: withDefaultSlot(rows),
			},
		]),
	};
}

function settingsRow(title: string, description: string, control: BlockOptions): BlockOptions {
	return {
		componentName: "SettingsRow",
		componentProps: { title, description },
		componentSlots: withDefaultSlot([control]),
	};
}

function textBlock(text: string): BlockOptions {
	return { componentName: "TextBlock", componentProps: { text, tag: "span" } };
}

// Wrap blocks as a component's default-slot content. Each block is tagged with
// parentSlotName so slot bookkeeping (selection, removal) works; Block's
// constructor upgrades these loose options into real Slot/Block instances
// (slotId, parentBlockId, reactive Blocks) via initializeSlots().
function withDefaultSlot(content: BlockOptions[]): Record<string, Slot> {
	content.forEach((block) => (block.parentSlotName = "default"));
	return {
		default: { slotName: "default", slotContent: content },
	} as unknown as Record<string, Slot>;
}

export default getBlockTemplate;