export const FRAPPE_UI_COMPONENTS = [
	"Alert",
	"Autocomplete",
	"Avatar",
	"Badge",
	"Button",
	"Breadcrumbs",
	"Checkbox",
	"Calendar",
	"CodeEditor",
	"Combobox",
	"ContextMenu",
	"DatePicker",
	"TimePicker",
	"DateTimePicker",
	"DateRangePicker",
	"MonthPicker",
	"Dialog",
	"Divider",
	"Dropdown",
	"Duration",
	"ErrorMessage",
	"FeatherIcon",
	"FileUploader",
	"FormLabel",
	"FormControl",
	"ListView",
	"MultiSelect",
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
	"TextEditor",
	"Tooltip",
	"Tree",
	"AxisChart",
	"NumberChart",
	"DonutChart",
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
// Legacy frappe-ui/frappe components. Filter and Link now ship from @framework/ui
// (see FRAMEWORK_UI_COMPONENTS), so this list is currently empty.
export const FRAPPE_COMPONENTS = []

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
