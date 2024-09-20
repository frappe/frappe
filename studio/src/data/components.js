import { defineAsyncComponent, h } from "vue"
import * as frappeUI from "frappe-ui"
import Header from "@/components/AppLayout/Header.vue"
import Sidebar from "@/components/AppLayout/Sidebar.vue"

export const COMPONENTS = {
	Alert: {
		name: "Alert",
		title: "Alert",
		icon: "CircleAlert",
		initialState: {
			title: "This user is inactive",
			type: "warning",
		},
	},
	Autocomplete: {
		name: "Autocomplete",
		title: "Autocomplete",
		icon: "TextSearch",
		initialState: {
			placeholder: "Select Person",
			options: [
				{
					label: "John Doe",
					value: "john-doe",
					image: "https://randomuser.me/api/portraits/men/59.jpg",
				},
				{
					label: "Jane Doe",
					value: "jane-doe",
					image: "https://randomuser.me/api/portraits/women/58.jpg",
				},
				{
					label: "John Smith",
					value: "john-smith",
					image: "https://randomuser.me/api/portraits/men/59.jpg",
				},
				{
					label: "Jane Smith",
					value: "jane-smith",
					image: "https://randomuser.me/api/portraits/women/59.jpg",
				},
				{
					label: "John Wayne",
					value: "john-wayne",
					image: "https://randomuser.me/api/portraits/men/57.jpg",
				},
				{
					label: "Jane Wayne",
					value: "jane-wayne",
					image: "https://randomuser.me/api/portraits/women/51.jpg",
				},
			],
		},
	},
	Avatar: {
		name: "Avatar",
		title: "Avatar",
		icon: "User",
		initialState: {
			shape: "circle",
			size: "md",
			image: "https://avatars.githubusercontent.com/u/499550?s=60&v=4",
			label: "EY",
		},
	},
	Badge: {
		name: "Badge",
		title: "Badge",
		icon: "BadgeCheck",
		initialState: {
			variant: "subtle",
			theme: "green",
			size: "sm",
			label: "Active",
		},
	},
	Button: {
		name: "Button",
		title: "Button",
		icon: "RectangleHorizontal",
		initialState: {
			label: "Submit",
			variant: "solid",
		},
	},
	Card: {
		name: "Card",
		title: "Card",
		icon: "IdCard",
		initialState: {
			title: "John Doe",
			subtitle: "Engineering Lead",
		},
	},
	Checkbox: {
		name: "Checkbox",
		title: "Checkbox",
		icon: "CircleCheck",
		initialState: {
			label: "Enable feature",
			padding: true,
			checked: true,
		},
	},
	Calendar: {
		name: "Calendar",
		title: "Calendar",
		icon: "Calendar",
		initialState: {
			config: {
				defaultMode: "Month",
				isEditMode: true,
				eventIcons: {},
				allowCustomClickEvents: true,
				redundantCellHeight: 100,
				enableShortcuts: true,
			},
			events: [
				{
					title: "English by Ryan Mathew",
					participant: "Ryan Mathew",
					id: "EDU-CSH-2024-00091",
					venue: "CNF-ROOM-2024-00001",
					fromDate: "2024-07-08 16:30:00",
					toDate: "2024-07-08 17:30:00",
					color: "green",
				},
				{
					title: "English by Ryan Mathew",
					participant: "Ryan Mathew",
					id: "EDU-CSH-2024-00092",
					venue: "CNF-ROOM-2024-00002",
					fromDate: "2024-07-08 13:30:00",
					toDate: "2024-07-08 17:30:00",
					color: "green",
				},
				{
					title: "English by Sheldon",
					participant: "Sheldon",
					id: "EDU-CSH-2024-00093",
					venue: "CNF-ROOM-2024-00001",
					fromDate: "2024-07-09 10:30:00",
					toDate: "2024-07-09 11:30:00",
					color: "green",
				},
				{
					title: "English by Ryan Mathew",
					participant: "Ryan Mathew",
					id: "EDU-CSH-2024-00094",
					venue: "CNF-ROOM-2024-00001",
					fromDate: "2024-07-17 16:30:00",
					toDate: "2024-07-17 17:30:00",
					color: "green",
				},
				{
					title: "Google Meet with John ",
					participant: "John",
					id: "#htrht41",
					venue: "Google Meet",
					fromDate: "2024-07-21 00:00:00",
					toDate: "2024-07-21 23:59:59",
					color: "amber",
					isFullDay: true,
				},
				{
					title: "Zoom Meet with Sheldon",
					participant: "Sheldon",
					id: "#htrht42",
					venue: "Google Meet",
					fromDate: "2024-07-21 00:00:00",
					toDate: "2024-07-21 23:59:59",
					color: "amber",
					isFullDay: true,
				},
			],
		},
	},
	DatePicker: {
		name: "DatePicker",
		title: "Date",
		icon: "CalendarCheck",
		initialState: {
			placeholder: "Select Date",
		},
	},
	DateTimePicker: {
		name: "DateTimePicker",
		title: "Date Time",
		icon: "CalendarClock",
		initialState: {
			placeholder: "Select Date Time",
		},
	},
	DateRangePicker: {
		name: "DateRangePicker",
		title: "Date Range",
		icon: "CalendarSearch",
		initialState: {
			placeholder: "Select Date Range",
		},
	},
	Dialog: {
		name: "Dialog",
		title: "Dialog",
		icon: "AppWindowMac",
		initialState: {
			options: {
				title: "Confirm",
				message: "Are you sure you want to confirm this action?",
				size: "xl",
				actions: [
					{
						label: "Confirm",
						variant: "solid",
						onClick: () => {},
					},
				],
			},
		},
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
		initialState: {
			options: [
				{
					label: "Edit Title",
					onClick: () => {},
					icon: () => h(frappeUI.FeatherIcon, { name: "edit-2" }),
				},
				{
					label: "Manage Members",
					onClick: () => {},
					icon: () => h(frappeUI.FeatherIcon, { name: "users" }),
				},
				{
					label: "Delete this project",
					onClick: () => {},
					icon: () => h(frappeUI.FeatherIcon, { name: "trash" }),
				},
			],
			button: { label: "Actions" },
		},
	},
	ErrorMessage: {
		name: "ErrorMessage",
		title: "Error Message",
		icon: "CircleX",
		initialState: {
			message: "Transaction failed due to insufficient balance",
		},
	},
	FeatherIcon: {
		name: "FeatherIcon",
		title: "FeatherIcon",
		icon: "Feather",
		initialState: {
			name: "activity",
			class: "h-6 w-6",
		},
	},
	FileUploader: {
		name: "FileUploader",
		title: "File Uploader",
		icon: "FileUp",
		initialState: {
			label: "Upload File",
			fileTypes: "['image/*']",
		},
	},
	FormControl: {
		name: "FormControl",
		title: "Form Control",
		icon: "BookType",
		initialState: {
			type: "text",
			label: "Name",
			placeholder: "John Doe",
			autocomplete: "off",
		},
	},
	ListView: {
		name: "ListView",
		title: "List View",
		icon: "ListCheck",
		initialState: {
			columns: [
				{
					label: "Name",
					key: "name",
					width: 3,
					getLabel: function ({ row }) {
						return row.name
					},
					prefix: function ({ row }) {
						return h(frappeUI.Avatar, {
							shape: "circle",
							image: row.user_image,
							size: "sm",
						})
					},
				},
				{
					label: "Email",
					key: "email",
					width: "200px",
				},
				{
					label: "Role",
					key: "role",
				},
				{
					label: "Status",
					key: "status",
				},
			],
			rows: [
				{
					id: 1,
					name: "John Doe",
					email: "john@doe.com",
					status: "Active",
					role: "Developer",
					user_image: "https://avatars.githubusercontent.com/u/499550",
				},
				{
					id: 2,
					name: "Jane Doe",
					email: "jane@doe.com",
					status: "Inactive",
					role: "HR",
					user_image: "https://avatars.githubusercontent.com/u/499120",
				},
			],
			rowKey: "id",
		},
	},
	Progress: {
		name: "Progress",
		title: "Progress",
		icon: "Ellipsis",
		initialState: {
			value: 50,
			size: "sm",
			label: "Progress",
		},
	},
	Select: {
		name: "Select",
		title: "Select",
		icon: "MousePointer2",
		initialState: {
			placeholder: "Person",
			options: [
				{
					label: "John Doe",
					value: "john-doe",
				},
				{
					label: "Jane Doe",
					value: "jane-doe",
				},
				{
					label: "John Smith",
					value: "john-smith",
				},
				{
					label: "Jane Smith",
					value: "jane-smith",
					disabled: true,
				},
				{
					label: "John Wayne",
					value: "john-wayne",
				},
				{
					label: "Jane Wayne",
					value: "jane-wayne",
				},
			],
		},
	},
	Switch: {
		name: "Switch",
		title: "Switch",
		icon: "ToggleLeft",
		initialState: {
			label: "Enable Notifications",
			description: "Get notified when someone mentions you in a comment",
			modelValue: true,
		},
	},
	Tabs: {
		name: "Tabs",
		title: "Tabs",
		icon: "ArrowRightLeft",
		initialState: {
			tabs: [
				{
					label: "Github",
					content:
						"Github is a code hosting platform for version control and collaboration. It lets you and others work together on projects from anywhere.",
				},
				{
					label: "Twitter",
					content:
						'Twitter is an American microblogging and social networking service on which users post and interact with messages known as "tweets".',
				},
				{
					label: "Linkedin",
					content:
						"LinkedIn is an American business and employment-oriented online service that operates via websites and mobile apps.",
				},
			],
		},
	},
	Textarea: {
		name: "Textarea",
		title: "Textarea",
		icon: "LetterText",
		initialState: {
			placeholder: "Enter your message",
		},
	},
	TextInput: {
		name: "TextInput",
		title: "Text Input",
		icon: "ALargeSmall",
		initialState: {
			placeholder: "Enter your name",
		},
	},
	TextEditor: {
		name: "TextEditor",
		title: "Text Editor",
		icon: "Edit",
		initialState: {
			content: "Type something...",
		},
	},
	Tooltip: {
		name: "Tooltip",
		title: "Tooltip",
		icon: "MessageSquare",
		initialState: {
			text: "This is a tooltip",
		},
	},
	Tree: {
		name: "Tree",
		title: "Tree",
		icon: "ListTree",
		initialState: {
			options: {
				showIndentationGuides: true,
				rowHeight: "25px",
				indentWidth: "15px",
			},
			nodeKey: "name",
			node: {
				name: "guest",
				label: "Guest",
				children: [
					{
						name: "downloads",
						label: "Downloads",
						children: [
							{
								name: "download.zip",
								label: "download.zip",
								children: [
									{
										name: "image.png",
										label: "image.png",
										children: [],
									},
								],
							},
						],
					},
					{
						name: "documents",
						label: "Documents",
						children: [
							{
								name: "somefile.txt",
								label: "somefile.txt",
								children: [],
							},
							{
								name: "somefile.pdf",
								label: "somefile.pdf",
								children: [],
							},
						],
					},
				],
			},
		},
	},
	// Studio Components
	Container: {
		name: "Container",
		title: "Container",
		icon: "AppWindow",
	},
	FitContainer: {
		name: "FitContainer",
		title: "Fit Container",
		icon: "Maximize",
	},
	Header: {
		name: "Header",
		title: "Header",
		icon: "Frame",
		props: Header.props,
		initialState: {
			title: "Frappe",
			menuItems: [
				{ label: "Home", url: "#" },
				{ label: "Settings", url: "#" },
			],
		},
	},
	Sidebar: {
		name: "Sidebar",
		title: "Sidebar",
		icon: "Sidebar",
		props: Sidebar.props,
		initialState: {
			items: [
				{ label: "Home", featherIcon: "home" },
				{ label: "Notifications", featherIcon: "bell" },
				{ label: "Settings", featherIcon: "settings" },
			],
		},
	},
}

function get(name) {
	return COMPONENTS[name]
}

function isFrappeUIComponent(name) {
	return name in frappeUI
}

function getComponent(name) {
	// TODO: A better way to load components for rendering the actual app without compromising the performance
	if (name === "div") {
		// root element
		return name
	} else if (isFrappeUIComponent(name)) {
		return frappeUI[name]
	} else {
		return defineAsyncComponent(() => import(`@/components/AppLayout/${name}.vue`))
	}
}

function getProps(name) {
	if (name in frappeUI) {
		return frappeUI[name]?.props
	} else {
		return COMPONENTS[name]?.props
	}
}

export default {
	...COMPONENTS,
	list: Object.values(COMPONENTS),
	get,
	getComponent,
	getProps,
	isFrappeUIComponent,
}
