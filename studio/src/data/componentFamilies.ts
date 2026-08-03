import { defineAsyncComponent } from "vue"
import type { FrappeUIComponents } from "@/types"

import LucideAppWindowMac from "~icons/lucide/app-window-mac"
import LucideArrowUpDown from "~icons/lucide/arrow-up-down"
import LucideColumns3 from "~icons/lucide/columns-3"
import LucideFrame from "~icons/lucide/frame"
import LucideList from "~icons/lucide/list"
import LucidePanelLeftClose from "~icons/lucide/panel-left-close"
import LucideRows3 from "~icons/lucide/rows-3"
import LucideSettings from "~icons/lucide/settings"
import LucideSidebar from "~icons/lucide/sidebar"
import LucideTag from "~icons/lucide/tag"

// Component families: the primary (isGroup) drops a whole working tree via its block template
export const COMPONENT_FAMILIES: FrappeUIComponents = {
	// List family (frappe-ui/list)
	List: {
		name: "List",
		title: "List",
		icon: LucideList,
		isGroup: true,
		blockTemplate: "list",
		expandArrayProps: true,
		overrideProps: {
			columns: {
				type: "array",
				inputType: "array",
				editor: defineAsyncComponent(() => import("@/components/PropEditors/ListColumnsEditor.vue")),
			},
			// v-model state leaked in as props by defineModel
			selection: {
				type: "array",
				inputType: "code",
			},
			active: {
				type: "string",
				inputType: "code",
			},
		},
	},
	ListRows: {
		name: "ListRows",
		title: "List Rows",
		icon: LucideRows3,
		group: "List",
		blockTemplate: "list-rows",
		initialState: {
			items: [],
		},
	},
	ListRow: {
		name: "ListRow",
		title: "List Row",
		icon: LucideRows3,
		group: "List",
		blockTemplate: "list-row",
	},
	ListCell: {
		name: "ListCell",
		title: "List Cell",
		icon: LucideColumns3,
		group: "List",
		blockTemplate: "list-cell",
	},
	ListHeader: {
		name: "ListHeader",
		title: "List Header",
		icon: LucideColumns3,
		group: "List",
		blockTemplate: "list-header",
	},
	ListHeaderCell: {
		name: "ListHeaderCell",
		title: "List Header Cell",
		icon: LucideColumns3,
		group: "List",
		blockTemplate: "list-header-cell",
	},
	ListHeaderCellSort: {
		name: "ListHeaderCellSort",
		title: "List Header Cell Sort",
		icon: LucideArrowUpDown,
		group: "List",
		blockTemplate: "list-header-cell-sort",
	},
	ListGroup: {
		name: "ListGroup",
		title: "List Group",
		icon: LucideList,
		group: "List",
		initialState: {
			label: "Group",
		},
	},
	// SettingsDialog family
	SettingsDialog: {
		name: "SettingsDialog",
		title: "Settings Dialog",
		icon: LucideSettings,
		isGroup: true,
		blockTemplate: "settings-dialog",
		editInFragmentMode: true,
		proxyComponent: defineAsyncComponent(() => import("@/components/ProxyComponents/ProxySettingsDialog.vue")),
		overrideProps: {
			// tabs manager: adds/removes NavItem + Panel pairs atomically and tracks
			// the active tab (the `tab` prop) via the leading dot
			tab: {
				type: "string",
				inputType: "custom",
				editor: defineAsyncComponent(() => import("@/components/PropEditors/SettingsTabsEditor.vue")),
			},
		},
	},
	// Sidebar/NavItem/Panel wrap reka-ui tabs primitives (TabsList/Trigger/Content)
	// that throw without the TabsRoot that SettingsDialog provides.
	SettingsSidebar: {
		name: "SettingsSidebar",
		title: "Settings Sidebar",
		icon: LucideSidebar,
		group: "SettingsDialog",
		isStandalone: false,
	},
	SettingsNavGroup: {
		name: "SettingsNavGroup",
		title: "Settings Nav Group",
		icon: LucideSidebar,
		group: "SettingsDialog",
		initialState: {
			label: "Group",
		},
	},
	SettingsNavItem: {
		name: "SettingsNavItem",
		title: "Settings Nav Item",
		icon: LucideSidebar,
		group: "SettingsDialog",
		isStandalone: false,
		initialState: {
			value: "tab",
		},
		// selecting a nav item activates its tab so the matching panel opens for editing
		onSelect: (block) => {
			const value = block.getProp("value")
			const dialog = block.closest("SettingsDialog")
			if (typeof value === "string" && dialog && dialog.getProp("tab") !== value) {
				dialog.setProp("tab", value)
			}
		},
	},
	SettingsContent: {
		name: "SettingsContent",
		title: "Settings Content",
		icon: LucideAppWindowMac,
		group: "SettingsDialog",
	},
	SettingsPanel: {
		name: "SettingsPanel",
		title: "Settings Panel",
		icon: LucideAppWindowMac,
		group: "SettingsDialog",
		isStandalone: false,
		initialState: {
			value: "tab",
		},
	},
	SettingsHeader: {
		name: "SettingsHeader",
		title: "Settings Header",
		icon: LucideFrame,
		group: "SettingsDialog",
		initialState: {
			title: "Section",
		},
	},
	SettingsBody: {
		name: "SettingsBody",
		title: "Settings Body",
		icon: LucideAppWindowMac,
		group: "SettingsDialog",
	},
	SettingsRow: {
		name: "SettingsRow",
		title: "Settings Row",
		icon: LucideRows3,
		group: "SettingsDialog",
		initialState: {
			title: "Setting",
			description: "",
		},
	},
	// Sidebar family
	Sidebar: {
		name: "Sidebar",
		title: "Sidebar",
		icon: LucideSidebar,
		isGroup: true,
		blockTemplate: "sidebar",
		// deprecated config-object API (`header`/`sections`); the family composes
		// SidebarHeader/SidebarLabel/SidebarItem blocks instead
		hideProps: ["header", "sections"],
	},
	SidebarHeader: {
		name: "SidebarHeader",
		title: "Sidebar Header",
		icon: LucideFrame,
		group: "Sidebar",
		initialState: {
			title: "Frappe",
		},
	},
	SidebarItem: {
		name: "SidebarItem",
		title: "Sidebar Item",
		icon: LucideRows3,
		group: "Sidebar",
		initialState: {
			label: "Item",
			icon: "lucide-circle-dashed",
		},
	},
	SidebarLabel: {
		name: "SidebarLabel",
		title: "Sidebar Label",
		icon: LucideTag,
		group: "Sidebar",
		blockTemplate: "sidebar-label",
	},
	SidebarCollapseToggle: {
		name: "SidebarCollapseToggle",
		title: "Sidebar Collapse Toggle",
		icon: LucidePanelLeftClose,
		group: "Sidebar",
	},
}
