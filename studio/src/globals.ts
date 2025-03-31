import { App } from "vue"
import {
	Alert,
	Autocomplete,
	Avatar,
	Badge,
	Breadcrumbs,
	Button,
	Card,
	Checkbox,
	DatePicker,
	DateTimePicker,
	DateRangePicker,
	Dialog,
	Divider,
	Dropdown,
	ErrorMessage,
	FeatherIcon,
	FileUploader,
	FormControl,
	GreenCheckIcon,
	Input,
	Link,
	ListItem,
	ListView,
	LoadingIndicator,
	LoadingText,
	Progress,
	Popover,
	Select,
	Spinner,
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
} from "frappe-ui"

import Container from "@/components/AppLayout/Container.vue"
import FitContainer from "@/components/AppLayout/FitContainer.vue"
import Header from "@/components/AppLayout/Header.vue"
import Sidebar from "@/components/AppLayout/Sidebar.vue"
import SplitView from "@/components/AppLayout/SplitView.vue"
import Repeater from "@/components/AppLayout/Repeater.vue"
import CardList from "@/components/AppLayout/CardList.vue"
import AvatarCard from "@/components/AppLayout/AvatarCard.vue"
import Audio from "@/components/AppLayout/Audio.vue"
import ImageView from "@/components/AppLayout/ImageView.vue"
import TextBlock from "@/components/AppLayout/TextBlock.vue"
import AppHeader from "@/components/AppLayout/AppHeader.vue"
import BottomTabs from "@/components/AppLayout/BottomTabs.vue"
import MarkdownEditor from "@/components/AppLayout/MarkdownEditor.vue"

export function registerGlobalComponents(app: App) {
	app.component("Alert", Alert)
	app.component("Autocomplete", Autocomplete)
	app.component("Avatar", Avatar)
	app.component("Badge", Badge)
	app.component("Breadcrumbs", Breadcrumbs)
	app.component("Button", Button)
	app.component("Card", Card)
	app.component("Checkbox", Checkbox)
	app.component("DatePicker", DatePicker)
	app.component("DateTimePicker", DateTimePicker)
	app.component("DateRangePicker", DateRangePicker)
	app.component("Dialog", Dialog)
	app.component("Divider", Divider)
	app.component("Dropdown", Dropdown)
	app.component("ErrorMessage", ErrorMessage)
	app.component("FeatherIcon", FeatherIcon)
	app.component("FileUploader", FileUploader)
	app.component("FormControl", FormControl)
	app.component("GreenCheckIcon", GreenCheckIcon)
	app.component("Input", Input)
	app.component("Link", Link)
	app.component("ListItem", ListItem)
	app.component("ListView", ListView)
	app.component("LoadingIndicator", LoadingIndicator)
	app.component("LoadingText", LoadingText)
	app.component("Progress", Progress)
	app.component("Popover", Popover)
	app.component("Select", Select)
	app.component("Spinner", Spinner)
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

	// studio components
	app.component("Container", Container)
	app.component("FitContainer", FitContainer)
	app.component("Header", Header)
	app.component("Sidebar", Sidebar)
	app.component("SplitView", SplitView)
	app.component("Repeater", Repeater)
	app.component("CardList", CardList)
	app.component("AvatarCard", AvatarCard)
	app.component("Audio", Audio)
	app.component("ImageView", ImageView)
	app.component("TextBlock", TextBlock)
	app.component("AppHeader", AppHeader)
	app.component("BottomTabs", BottomTabs)
	app.component("MarkdownEditor", MarkdownEditor)
}
