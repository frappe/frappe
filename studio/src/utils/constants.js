export const FRAPPE_UI_COMPONENTS = [
	"Alert",
	"Avatar",
	"Badge",
	"Button",
	"Breadcrumbs",
	"Checkbox",
	"Combobox",
	"ContextMenu",
	"DatePicker",
	"TimePicker",
	"DateTimePicker",
	"DateRangePicker",
	"Dialog",
	"Divider",
	"Dropdown",
	"Duration",
	"ErrorMessage",
	"FileUploader",
	"FormLabel",
	"FormControl",
	"Icon",
	"MultiSelect",
	"Password",
	"Popover",
	"Progress",
	"Rating",
	"Select",
	"Slider",
	"Spinner",
	"Switch",
	"Tabs",
	"TabButtons",
	"Textarea",
	"TextInput",
	"Tooltip",
	"Tree",
	// SettingsDialog family
	"SettingsDialog",
	"SettingsSidebar",
	"SettingsNavGroup",
	"SettingsNavItem",
	"SettingsContent",
	"SettingsPanel",
	"SettingsHeader",
	"SettingsBody",
	"SettingsRow",
	// Sidebar family
	"Sidebar",
	"SidebarHeader",
	"SidebarItem",
	"SidebarLabel",
	"SidebarCollapseToggle",
	"SidebarCard",
	// SidebarRail family
	"SidebarRail",
	"SidebarRailItem",
	// RadioGroup family
	"RadioGroup",
	"Radio",
]

// frappe-ui "molecules"
export const FRAPPE_UI_MOLECULES = [
	"List",
	"ListRows",
	"ListRow",
	"ListCell",
	"ListHeader",
	"ListHeaderCell",
	"ListHeaderCellSort",
	"ListGroup",
]
// frappe-ui/experimental: families parked outside the stable root export
export const FRAPPE_UI_EXPERIMENTAL_COMPONENTS = ["Calendar", "CodeEditor", "ListView", "TextEditor"]

// frappe-ui/charts
export const FRAPPE_UI_CHARTS = [
	"AreaChart",
	"BarChart",
	"LineChart",
	"DonutChart",
	"FunnelChart",
	"HeatmapChart",
	"ScatterChart",
	"SankeyChart",
	"NumberCard",
]

// @framework/ui — the in-house shared component library from apps/frappe/ui.
export const FRAMEWORK_UI_COMPONENTS = [
	"FormLayout",
	"Link",
	"Grid",
	"Phone",
	"TableMultiSelect",
	"NotificationPanel",
	"NotificationItem",
	"ActivityTimeline",
	"EmailItem",
	"CommentItem",
	"EmailComposer",
	"CommentComposer",
	"Filter",
	"SortBy",
	"QuickFilter",
	"ColumnSettings",
	"ListViewShell",
	"FileUploadDialog",
	"AttachmentsList",
	"UploadTray",
]
export const STUDIO_COMPONENTS = [
	"Container",
	"FitContainer",
	"Repeater",
	"HTML",
	"SplitView",
	"AvatarCard",
	"CardList",
	"Audio",
	"ImageView",
	"TextBlock",
	"AppHeader",
	"BottomTabs",
	"MarkdownEditor",
]

// Matches strings that are entirely wrapped in double curly braces, e.g., "{{ expression }}" (allows whitespace inside)
export const DYNAMIC_EXPRESSION_REGEX = /^\{\{[\s\S]*\}\}$/

// Matches every {{ ... }} expression in a string and captures its inner contents
export const DYNAMIC_EXPRESSION_CONTENT_REGEX = /\{\{([\s\S]*?)\}\}/g

// Match a double-quoted string and capture its inner content, including escaped chars.
// This pattern safely captures the contents of a JSON-style double-quoted string,
// preserving escaped sequences (e.g. \" or \\n) in the captured group.
export const QUOTED_STRING_CONTENT_REGEX = /"((?:[^"\\]|\\.)*)"/g
