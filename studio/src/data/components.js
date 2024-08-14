export const COMPONENTS = {
	Alert: {
		name: "Alert",
		title: "Alert",
		icon: "CircleAlert",
	},
	Autocomplete: {
		name: "Autocomplete",
		title: "Autocomplete",
		icon: "TextSearch",
	},
	Avatar: {
		name: "Avatar",
		title: "Avatar",
		icon: "User",
	},
	Badge: {
		name: "Badge",
		title: "Badge",
		icon: "BadgeCheck",
	},
	Button: {
		name: "Button",
		title: "Button",
		icon: "RectangleHorizontal",
		initialState: {
			label: "Button",
		},
	},
	Card: {
		name: "Card",
		title: "Card",
		icon: "IdCard",
	},
	Checkbox: {
		name: "Checkbox",
		title: "Checkbox",
		icon: "CircleCheck",
	},
	DatePicker: {
		name: "DatePicker",
		title: "Date",
		icon: "CalendarCheck",
	},
	DateTimePicker: {
		name: "DateTimePicker",
		title: "Date Time",
		icon: "CalendarClock",
	},
	DateRangePicker: {
		name: "DateRangePicker",
		title: "Date Range",
		icon: "CalendarSearch",
	},
	Dialog: {
		name: "Dialog",
		title: "Dialog",
		icon: "AppWindowMac",
	},
	Divider: {
		name: "Divider",
		title: "Divider",
		icon: "Minus",
	},
	Dropdown: {
		name: "Dropdown",
		title: "Dropdown",
		icon: "ChevronDown",
	},
}

function get(name) {
	return COMPONENTS[name]
}

export default {
	...COMPONENTS,
	list: Object.values(COMPONENTS),
	get,
}
