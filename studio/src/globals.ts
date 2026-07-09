import { App, defineAsyncComponent, shallowRef } from "vue"
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
	MonthPicker,
	ErrorMessage,
	FeatherIcon,
	FileUploader,
	FormControl,
	FormLabel,
	Input,
	ListItem,
	ListView,
	LoadingIndicator,
	LoadingText,
	MultiSelect,
	Progress,
	Popover,
	Rating,
	Select,
	Sidebar,
	Slider,
	Switch,
	TabButtons,
	Tabs,
	TextInput,
	Textarea,
	TextEditor,
	Toast,
	Tooltip,
	Tree,
	CommandPalette,
	CommandPaletteItem,
	Calendar,
	NumberChart,
	AxisChart,
	DonutChart,
	ContextMenu,
	Duration,
	Spinner,
} from "frappe-ui"
import { CodeEditor } from "frappe-ui/code-editor"

// @framework/ui (the in-house shared component library from apps/frappe/ui).
// Filter and Link live here now, replacing the older frappe-ui/frappe versions.
import {
	FormLayout,
	Link,
	Grid,
	Phone,
	TableMultiSelect,
	NotificationPanel,
	NotificationItem,
	ActivityTimeline,
	EmailItem,
	CommentItem,
	LogItem,
	VersionItem,
	InviteUser,
} from "@framework/ui"
import { Filter } from "@framework/ui/Filter"
import { SortBy } from "@framework/ui/SortBy"
import { QuickFilter } from "@framework/ui/QuickFilter"
import { ColumnSettings } from "@framework/ui/ColumnSettings"
import { ListViewShell } from "@framework/ui/ListView"
import { FileUploadDialog, AttachmentsList, UploadTray } from "@framework/ui/FileUpload"

import Container from "@/components/AppLayout/Container.vue"
import FitContainer from "@/components/AppLayout/FitContainer.vue"
import SplitView from "@/components/AppLayout/SplitView.vue"
import Repeater from "@/components/AppLayout/Repeater.vue"
import HTML from "@/components/AppLayout/HTML.vue"
import CardList from "@/components/AppLayout/CardList.vue"
import AvatarCard from "@/components/AppLayout/AvatarCard.vue"
import Audio from "@/components/AppLayout/Audio.vue"
import ImageView from "@/components/AppLayout/ImageView.vue"
import TextBlock from "@/components/AppLayout/TextBlock.vue"
import AppHeader from "@/components/AppLayout/AppHeader.vue"
import BottomTabs from "@/components/AppLayout/BottomTabs.vue"
import MarkdownEditor from "@/components/AppLayout/MarkdownEditor.vue"

import { vueComponents } from "@/data/vueComponents"
import { CustomVueComponentMeta } from "@/types/vue"

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
	app.component("MonthPicker", MonthPicker)
	app.component("Dialog", Dialog)
	app.component("Divider", Divider)
	app.component("Dropdown", Dropdown)
	app.component("ErrorMessage", ErrorMessage)
	app.component("FeatherIcon", FeatherIcon)
	app.component("FileUploader", FileUploader)
	app.component("FormControl", FormControl)
	app.component("FormLabel", FormLabel)
	app.component("Input", Input)
	app.component("ListItem", ListItem)
	app.component("ListView", ListView)
	app.component("LoadingIndicator", LoadingIndicator)
	app.component("LoadingText", LoadingText)
	app.component("MultiSelect", MultiSelect)
	app.component("Progress", Progress)
	app.component("Popover", Popover)
	app.component("Rating", Rating)
	app.component("Select", Select)
	app.component("Sidebar", Sidebar)
	app.component("Slider", Slider)
	app.component("Switch", Switch)
	app.component("TabButtons", TabButtons)
	app.component("Tabs", Tabs)
	app.component("TextInput", TextInput)
	app.component("Textarea", Textarea)
	app.component("TextEditor", TextEditor)
	app.component("Toast", Toast)
	app.component("Tooltip", Tooltip)
	app.component("Tree", Tree)
	app.component("CommandPalette", CommandPalette)
	app.component("CommandPaletteItem", CommandPaletteItem)
	app.component("Calendar", Calendar)
	app.component("NumberChart", NumberChart)
	app.component("AxisChart", AxisChart)
	app.component("DonutChart", DonutChart)
	app.component("CodeEditor", CodeEditor)
	app.component("ContextMenu", ContextMenu)
	app.component("Duration", Duration)
	app.component("Spinner", Spinner)

	// @framework/ui components
	app.component("FormLayout", FormLayout)
	app.component("Link", Link)
	app.component("Grid", Grid)
	app.component("Phone", Phone)
	app.component("TableMultiSelect", TableMultiSelect)
	app.component("NotificationPanel", NotificationPanel)
	app.component("NotificationItem", NotificationItem)
	app.component("ActivityTimeline", ActivityTimeline)
	app.component("EmailItem", EmailItem)
	app.component("CommentItem", CommentItem)
	app.component("LogItem", LogItem)
	app.component("VersionItem", VersionItem)
	app.component("InviteUser", InviteUser)
	app.component("Filter", Filter)
	app.component("SortBy", SortBy)
	app.component("QuickFilter", QuickFilter)
	app.component("ColumnSettings", ColumnSettings)
	app.component("ListViewShell", ListViewShell)
	app.component("FileUploadDialog", FileUploadDialog)
	app.component("AttachmentsList", AttachmentsList)
	app.component("UploadTray", UploadTray)

	// studio components
	app.component("Container", Container)
	app.component("FitContainer", FitContainer)
	app.component("SplitView", SplitView)
	app.component("Repeater", Repeater)
	app.component("HTML", HTML)
	app.component("CardList", CardList)
	app.component("AvatarCard", AvatarCard)
	app.component("Audio", Audio)
	app.component("ImageView", ImageView)
	app.component("TextBlock", TextBlock)
	app.component("AppHeader", AppHeader)
	app.component("BottomTabs", BottomTabs)
	app.component("MarkdownEditor", MarkdownEditor)
}

export const customVueComponentsRegistry = shallowRef<Record<string, any>>({})
/**
 * Dynamically register custom Vue components from a specific Frappe app into the custom components registry.
 * @param frappeApp - The Frappe app name to fetch components from
 */
export async function registerCustomVueComponents(frappeApp: string): Promise<CustomVueComponentMeta[]> {
	try {
		if (!frappeApp) return []
		const components: CustomVueComponentMeta[] = await vueComponents.reload({ frappe_app: frappeApp })

		const registry = { ...customVueComponentsRegistry.value }
		for (const comp of components) {
			try {
				const asyncComp = defineAsyncComponent(() => import(/* @vite-ignore */ comp.file_path))
				registry[comp.component_name] = asyncComp
				if (window.__APP_COMPONENTS__) {
					window.__APP_COMPONENTS__[comp.component_name] = asyncComp
				}
			} catch (err) {
				console.error(`Failed to load custom component ${comp.component_name}:`, err)
			}
		}
		customVueComponentsRegistry.value = registry
		return components
	} catch (err) {
		console.error("Failed to fetch custom Vue components:", err)
		return []
	}
}

/**
 * Unregister previously registered custom Vue components from the custom components registry.
 * Called when switching apps to clean up components from the previous app's frappe_app.
 */
export function unregisterCustomVueComponents(components: CustomVueComponentMeta[]) {
	const registry = { ...customVueComponentsRegistry.value }
	for (const comp of components) {
		delete registry[comp.component_name]
		if (window.__APP_COMPONENTS__) {
			delete window.__APP_COMPONENTS__[comp.component_name]
		}
	}
	customVueComponentsRegistry.value = registry
}
