import { defineAsyncComponent } from "vue"
import type { FrappeUIComponents } from "@/types"

import LucideAppWindowMac from "~icons/lucide/app-window-mac"
import LucideArrowUpDown from "~icons/lucide/arrow-up-down"
import LucideColumns3 from "~icons/lucide/columns-3"
import LucideFrame from "~icons/lucide/frame"
import LucideList from "~icons/lucide/list"
import LucideRows3 from "~icons/lucide/rows-3"
import LucideSettings from "~icons/lucide/settings"
import LucideSidebar from "~icons/lucide/sidebar"

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
	},
	SettingsSidebar: {
		name: "SettingsSidebar",
		title: "Settings Sidebar",
		icon: LucideSidebar,
		group: "SettingsDialog",
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
		initialState: {
			value: "tab",
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
}
