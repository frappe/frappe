import { App, defineAsyncComponent } from "vue"
import {
	Alert,
	Avatar,
	Badge,
	Breadcrumbs,
	Button,
	Checkbox,
	Combobox,
	DatePicker,
	TimePicker,
	DateTimePicker,
	DateRangePicker,
	Dialog,
	Divider,
	Dropdown,
	ErrorMessage,
	FileUploader,
	FormControl,
	FormLabel,
	Icon,
	LoadingIndicator,
	LoadingText,
	MultiSelect,
	Password,
	Progress,
	Popover,
	Radio,
	RadioGroup,
	Rating,
	Select,
	Sidebar,
	SidebarHeader,
	SidebarItem,
	SidebarLabel,
	SidebarCollapseToggle,
	SidebarCard,
	SidebarRail,
	SidebarRailItem,
	Slider,
	Switch,
	TabButtons,
	Tabs,
	TextInput,
	Textarea,
	Tooltip,
	Tree,
	ContextMenu,
	Duration,
	Spinner,
	SettingsDialog,
	SettingsSidebar,
	SettingsNavGroup,
	SettingsNavItem,
	SettingsContent,
	SettingsPanel,
	SettingsHeader,
	SettingsBody,
	SettingsRow,
} from "frappe-ui"
import { Calendar, CommandPalette, CommandPaletteItem, ListView, TextEditor } from "frappe-ui/experimental"
import { FRAPPE_UI_CHARTS } from "@/utils/constants"
import {
	List,
	ListRows,
	ListRow,
	ListCell,
	ListHeader,
	ListHeaderCell,
	ListHeaderCellSort,
	ListGroup,
} from "frappe-ui/list"

import Container from "@/components/AppLayout/Container.vue"
import Repeater from "@/components/AppLayout/Repeater.vue"
import HTML from "@/components/AppLayout/HTML.vue"
import ImageView from "@/components/AppLayout/ImageView.vue"
import TextBlock from "@/components/AppLayout/TextBlock.vue"

export function registerGlobalComponents(app: App) {
	app.component("Alert", Alert)
	app.component("Avatar", Avatar)
	app.component("Badge", Badge)
	app.component("Breadcrumbs", Breadcrumbs)
	app.component("Button", Button)
	app.component("Checkbox", Checkbox)
	app.component("Combobox", Combobox)
	app.component("DatePicker", DatePicker)
	app.component("TimePicker", TimePicker)
	app.component("DateTimePicker", DateTimePicker)
	app.component("DateRangePicker", DateRangePicker)
	app.component("Dialog", Dialog)
	app.component("Divider", Divider)
	app.component("Dropdown", Dropdown)
	app.component("ErrorMessage", ErrorMessage)
	app.component("FileUploader", FileUploader)
	app.component("FormControl", FormControl)
	app.component("FormLabel", FormLabel)
	app.component("Icon", Icon)
	app.component("LoadingIndicator", LoadingIndicator)
	app.component("LoadingText", LoadingText)
	app.component("MultiSelect", MultiSelect)
	app.component("Password", Password)
	app.component("Progress", Progress)
	app.component("Popover", Popover)
	app.component("Rating", Rating)
	app.component("Select", Select)
	app.component("Slider", Slider)
	app.component("Switch", Switch)
	app.component("TabButtons", TabButtons)
	app.component("Tabs", Tabs)
	app.component("TextInput", TextInput)
	app.component("Textarea", Textarea)
	app.component("Tooltip", Tooltip)
	app.component("Tree", Tree)
	app.component("ListView", ListView)
	app.component("TextEditor", TextEditor)
	app.component("CommandPalette", CommandPalette)
	app.component("CommandPaletteItem", CommandPaletteItem)
	app.component("Calendar", Calendar)
	app.component("ContextMenu", ContextMenu)
	app.component("Duration", Duration)
	app.component("Spinner", Spinner)

	for (const chart of FRAPPE_UI_CHARTS) {
		app.component(
			chart,
			defineAsyncComponent(() => import("frappe-ui/charts").then((charts) => charts[chart])),
		)
	}

	// List family (frappe-ui/list) — dropped as a tree via the `list` block template.
	app.component("List", List)
	app.component("ListRows", ListRows)
	app.component("ListRow", ListRow)
	app.component("ListCell", ListCell)
	app.component("ListHeader", ListHeader)
	app.component("ListHeaderCell", ListHeaderCell)
	app.component("ListHeaderCellSort", ListHeaderCellSort)
	app.component("ListGroup", ListGroup)

	// SettingsDialog family — dropped as a tree via the `settings-dialog` block template.
	app.component("SettingsDialog", SettingsDialog)
	app.component("SettingsSidebar", SettingsSidebar)
	app.component("SettingsNavGroup", SettingsNavGroup)
	app.component("SettingsNavItem", SettingsNavItem)
	app.component("SettingsContent", SettingsContent)
	app.component("SettingsPanel", SettingsPanel)
	app.component("SettingsHeader", SettingsHeader)
	app.component("SettingsBody", SettingsBody)
	app.component("SettingsRow", SettingsRow)

	// Sidebar family — dropped as a tree via the `sidebar` block template.
	app.component("Sidebar", Sidebar)
	app.component("SidebarHeader", SidebarHeader)
	app.component("SidebarItem", SidebarItem)
	app.component("SidebarLabel", SidebarLabel)
	app.component("SidebarCollapseToggle", SidebarCollapseToggle)
	app.component("SidebarCard", SidebarCard)

	// SidebarRail family — dropped as a tree via the `sidebar-rail` block template.
	app.component("SidebarRail", SidebarRail)
	app.component("SidebarRailItem", SidebarRailItem)

	// RadioGroup family — dropped as a tree via the `radio-group` block template.
	app.component("RadioGroup", RadioGroup)
	app.component("Radio", Radio)

	// @framework/ui components
	app.component(
		"FormLayout",
		defineAsyncComponent(() => import("@framework/ui/components/FormLayout/FormLayout.vue")),
	)
	app.component(
		"Link",
		defineAsyncComponent(() => import("@framework/ui/components/Link/Link.vue")),
	)
	app.component(
		"Grid",
		defineAsyncComponent(() => import("@framework/ui/components/Grid/Grid.vue")),
	)
	app.component(
		"Phone",
		defineAsyncComponent(() => import("@framework/ui/components/Phone/Phone.vue")),
	)
	app.component(
		"TableMultiSelect",
		defineAsyncComponent(() => import("@framework/ui/components/TableMultiSelect/TableMultiSelect.vue")),
	)
	app.component(
		"NotificationPanel",
		defineAsyncComponent(() => import("@framework/ui/components/Notifications/NotificationPanel.vue")),
	)
	app.component(
		"NotificationItem",
		defineAsyncComponent(() => import("@framework/ui/components/Notifications/NotificationItem.vue")),
	)
	app.component(
		"ActivityTimeline",
		defineAsyncComponent(() => import("@framework/ui/components/ActivityTimeline/ActivityTimeline.vue")),
	)
	app.component(
		"EmailItem",
		defineAsyncComponent(() => import("@framework/ui/components/ActivityTimeline/EmailItem.vue")),
	)
	app.component(
		"CommentItem",
		defineAsyncComponent(() => import("@framework/ui/components/ActivityTimeline/CommentItem.vue")),
	)
	app.component(
		"EmailComposer",
		defineAsyncComponent(() => import("@framework/ui/components/Composer/EmailComposer/EmailComposer.vue")),
	)
	app.component(
		"CommentComposer",
		defineAsyncComponent(
			() => import("@framework/ui/components/Composer/CommentComposer/CommentComposer.vue"),
		),
	)
	app.component(
		"Filter",
		defineAsyncComponent(() => import("@framework/ui/components/Filter/Filter.vue")),
	)
	app.component(
		"SortBy",
		defineAsyncComponent(() => import("@framework/ui/components/SortBy/SortBy.vue")),
	)
	app.component(
		"QuickFilter",
		defineAsyncComponent(() => import("@framework/ui/components/QuickFilter/QuickFilter.vue")),
	)
	app.component(
		"ColumnSettings",
		defineAsyncComponent(() => import("@framework/ui/components/ColumnSettings/ColumnSettings.vue")),
	)
	app.component(
		"ListViewShell",
		defineAsyncComponent(() => import("@framework/ui/components/ListView/ListViewShell.vue")),
	)
	app.component(
		"FileUploadDialog",
		defineAsyncComponent(() => import("@framework/ui/components/FileUpload/FileUploadDialog.vue")),
	)
	app.component(
		"AttachmentsList",
		defineAsyncComponent(() => import("@framework/ui/components/FileUpload/AttachmentsList.vue")),
	)
	app.component(
		"UploadTray",
		defineAsyncComponent(() => import("@framework/ui/components/FileUpload/UploadTray.vue")),
	)

	// studio components
	app.component("Container", Container)
	app.component("Repeater", Repeater)
	app.component("HTML", HTML)
	app.component("ImageView", ImageView)
	app.component("TextBlock", TextBlock)
}
