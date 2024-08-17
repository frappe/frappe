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
	CommandPalette,
	CommandPaletteItem,
	Calendar,
} from "frappe-ui"

export function registerGlobalComponents(app) {
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
	app.component("CommandPalette", CommandPalette)
	app.component("CommandPaletteItem", CommandPaletteItem)
	app.component("Calendar", Calendar)
}
