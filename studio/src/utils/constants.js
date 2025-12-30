export const FRAPPE_UI_COMPONENTS = [
	"Alert",
	"Autocomplete",
	"Avatar",
	"Badge",
	"Button",
	"Breadcrumbs",
	"Card",
	"Checkbox",
	"Calendar",
	"Combobox",
	"DatePicker",
	"TimePicker",
	"DateTimePicker",
	"DateRangePicker",
	"MonthPicker",
	"Dialog",
	"Divider",
	"Dropdown",
	"ErrorMessage",
	"FeatherIcon",
	"FileUploader",
	"FormLabel",
	"FormControl",
	"ListView",
	"MultiSelect",
	"Progress",
	"Rating",
	"Select",
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
]
export const FRAPPE_COMPONENTS = ["Filter", "Link"]
export const STUDIO_COMPONENTS = [
	"Container",
	"FitContainer",
	"Repeater",
	"Header",
	"Sidebar",
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

// Matches a single complete function (function declaration or arrow function), nothing before or after
// - Function declaration: (async)? function name?(...) {...}
// - Arrow function: (async)? (...) => expr or (...) => {...}
export const FUNCTION_STRING_REGEX =
	/^\s*(?:async\s+)?(?:(?:function\s*[a-zA-Z_$][a-zA-Z0-9_$]*\s*\([^)]*\)\s*\{(?:[^{}]|\{[^{}]*\})*\})|(?:(?:\([^)]*\)|[a-zA-Z_$][a-zA-Z0-9_$]*)\s*=>\s*(?:\{(?:[^{}]|\{[^{}]*\})*\}|[^,;{}]+)))\s*$/

// Matches strings that are entirely wrapped in double curly braces, e.g., "{{ expression }}" (allows whitespace inside)
export const DYNAMIC_EXPRESSION_REGEX = /^\{\{[\s\S]*\}\}$/

// Match a double-quoted string and capture its inner content, including escaped chars.
// This pattern safely captures the contents of a JSON-style double-quoted string,
// preserving escaped sequences (e.g. \" or \\n) in the captured group.
export const QUOTED_STRING_CONTENT_REGEX = /"((?:[^"\\]|\\.)*)"/g
