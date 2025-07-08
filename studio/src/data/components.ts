import { defineAsyncComponent, h } from "vue"
import { FRAPPE_UI_COMPONENTS } from "@/utils/constants"

import type { FrappeUIComponents, FrappeUIComponent } from "@/types"

import LucideCircleAlert from "~icons/lucide/circle-alert"
import LucideTextSearch from "~icons/lucide/text-search"
import LucideUser from "~icons/lucide/user"
import LucideBadgeCheck from "~icons/lucide/badge-check"
import LucideRectangleHorizontal from "~icons/lucide/rectangle-horizontal"
import LucideIdCard from "~icons/lucide/id-card"
import LucideCircleCheck from "~icons/lucide/circle-check"
import LucideCalendar from "~icons/lucide/calendar"
import LucideCalendarCheck from "~icons/lucide/calendar-check"
import LucideCalendarClock from "~icons/lucide/calendar-clock"
import LucideCalendarSearch from "~icons/lucide/calendar-search"
import LucideAppWindowMac from "~icons/lucide/app-window-mac"
import LucideMinus from "~icons/lucide/minus"
import LucideChevronDown from "~icons/lucide/chevron-down"
import LucideCircleX from "~icons/lucide/circle-x"
import LucideFeather from "~icons/lucide/feather"
import LucideFileUp from "~icons/lucide/file-up"
import LucideBookType from "~icons/lucide/book-type"
import LucideListCheck from "~icons/lucide/list-check"
import LucideEllipsis from "~icons/lucide/ellipsis"
import LucideMousePointer2 from "~icons/lucide/mouse-pointer-2"
import LucideToggleLeft from "~icons/lucide/toggle-left"
import LucideArrowRightLeft from "~icons/lucide/arrow-right-left"
import LucideLetterText from "~icons/lucide/letter-text"
import LucideALargeSmall from "~icons/lucide/a-large-small"
import LucideEdit from "~icons/lucide/edit"
import LucideMessageSquare from "~icons/lucide/message-square"
import LucideListTree from "~icons/lucide/list-tree"
import LucideAppWindow from "~icons/lucide/app-window"
import LucideMaximize from "~icons/lucide/maximize"
import LucideRepeat from "~icons/lucide/repeat"
import LucideFrame from "~icons/lucide/frame"
import LucideSidebar from "~icons/lucide/sidebar"
import LucideSquareSplitHorizontal from "~icons/lucide/square-split-horizontal"
import LucideImage from "~icons/lucide/image"
import LucideList from "~icons/lucide/list"
import LucideMusic from "~icons/lucide/music"
import LucideType from "~icons/lucide/type"
import LucideFilePenLine from "~icons/lucide/file-pen-line"

export const COMPONENTS: FrappeUIComponents = {
	Alert: {
		name: "Alert",
		title: "Alert",
		icon: LucideCircleAlert,
		initialState: {
			title: "This user is inactive",
			type: "warning",
		},
	},
	Autocomplete: {
		name: "Autocomplete",
		title: "Autocomplete",
		icon: LucideTextSearch,
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
		icon: LucideUser,
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
		icon: LucideBadgeCheck,
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
		icon: LucideRectangleHorizontal,
		initialState: {
			label: "Submit",
			variant: "solid",
		},
	},
	Card: {
		name: "Card",
		title: "Card",
		icon: LucideIdCard,
		initialState: {
			title: "John Doe",
			subtitle: "Engineering Lead",
		},
	},
	Checkbox: {
		name: "Checkbox",
		title: "Checkbox",
		icon: LucideCircleCheck,
		initialState: {
			label: "Enable feature",
			padding: true,
			checked: true,
		},
	},
	Calendar: {
		name: "Calendar",
		title: "Calendar",
		icon: LucideCalendar,
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
		icon: LucideCalendarCheck,
		initialState: {
			placeholder: "Select Date",
		},
	},
	DateTimePicker: {
		name: "DateTimePicker",
		title: "Date Time",
		icon: LucideCalendarClock,
		initialState: {
			placeholder: "Select Date Time",
		},
	},
	DateRangePicker: {
		name: "DateRangePicker",
		title: "Date Range",
		icon: LucideCalendarSearch,
		initialState: {
			placeholder: "Select Date Range",
		},
	},
	Dialog: {
		name: "Dialog",
		title: "Dialog",
		icon: LucideAppWindowMac,
		initialState: {
			modelValue: false,
			disableOutsideClickToClose: true,
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
		editInFragmentMode: true,
		proxyComponent: defineAsyncComponent(() => import("@/components/ProxyComponents/ProxyDialog.vue")),
	},
	Divider: {
		name: "Divider",
		title: "Divider",
		icon: LucideMinus,
	},
	Dropdown: {
		name: "Dropdown",
		title: "Dropdown",
		icon: LucideChevronDown,
		initialState: {
			options: [
				{
					label: "Edit Title",
					onClick: () => {},
					// @ts-ignore
					icon: () => h(FeatherIcon, { name: "edit-2" }),
				},
				{
					label: "Manage Members",
					onClick: () => {},
					// @ts-ignore
					icon: () => h(FeatherIcon, { name: "users" }),
				},
				{
					label: "Delete this project",
					onClick: () => {},
					// @ts-ignore
					icon: () => h(FeatherIcon, { name: "trash" }),
				},
			],
			button: { label: "Actions" },
		},
	},
	ErrorMessage: {
		name: "ErrorMessage",
		title: "Error Message",
		icon: LucideCircleX,
		initialState: {
			message: "Transaction failed due to insufficient balance",
		},
	},
	FeatherIcon: {
		name: "FeatherIcon",
		title: "FeatherIcon",
		icon: LucideFeather,
		initialState: {
			name: "activity",
			class: "h-6 w-6",
		},
	},
	FileUploader: {
		name: "FileUploader",
		title: "File Uploader",
		icon: LucideFileUp,
		initialState: {
			label: "Upload File",
			fileTypes: "['image/*']",
		},
	},
	FormControl: {
		name: "FormControl",
		title: "Form Control",
		icon: LucideBookType,
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
		icon: LucideListCheck,
		initialState: {
			columns: [
				{
					label: "Name",
					key: "name",
					width: 3,
					getLabel: function ({ row }: { row: any }) {
						return row.name
					},
					prefix: function ({ row }: { row: any }) {
						// @ts-ignore
						return h(Avatar, {
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
		icon: LucideEllipsis,
		initialState: {
			value: 50,
			size: "sm",
			label: "Progress",
		},
	},
	Select: {
		name: "Select",
		title: "Select",
		icon: LucideMousePointer2,
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
		icon: LucideToggleLeft,
		initialState: {
			label: "Enable Notifications",
			description: "Get notified when someone mentions you in a comment",
			modelValue: true,
		},
	},
	Tabs: {
		name: "Tabs",
		title: "Tabs",
		icon: LucideArrowRightLeft,
		initialState: {
			as: "div",
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
	TabButtons: {
		name: "TabButtons",
		title: "Tab Buttons",
		icon: LucideArrowRightLeft,
		initialState: {
			buttons: [
				{
					label: "My Tasks",
					value: "mytasks",
				},
				{
					label: "Team Tasks",
					value: "teamtasks",
				},
			],
		},
	},
	Textarea: {
		name: "Textarea",
		title: "Textarea",
		icon: LucideLetterText,
		initialState: {
			placeholder: "Enter your message",
		},
	},
	TextInput: {
		name: "TextInput",
		title: "Text Input",
		icon: LucideALargeSmall,
		initialState: {
			placeholder: "Enter your name",
		},
	},
	TextEditor: {
		name: "TextEditor",
		title: "Text Editor",
		icon: LucideEdit,
		initialState: {
			content: "Type something...",
		},
	},
	Tooltip: {
		name: "Tooltip",
		title: "Tooltip",
		icon: LucideMessageSquare,
		initialState: {
			text: "This is a tooltip",
		},
	},
	Tree: {
		name: "Tree",
		title: "Tree",
		icon: LucideListTree,
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
		icon: LucideAppWindow,
	},
	FitContainer: {
		name: "FitContainer",
		title: "Fit Container",
		icon: LucideMaximize,
	},
	Repeater: {
		name: "Repeater",
		title: "Repeater",
		icon: LucideRepeat,
	},
	Header: {
		name: "Header",
		title: "Header",
		icon: LucideFrame,
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
		icon: LucideSidebar,
		initialState: {
			title: "Frappe",
			menuItems: [
				{ label: "Home", featherIcon: "home", route_to: "/" },
				{ label: "Notifications", featherIcon: "bell", route_to: "/" },
				{ label: "Settings", featherIcon: "settings", route_to: "/" },
			],
		},
	},
	SplitView: {
		name: "SplitView",
		title: "Split View",
		icon: LucideSquareSplitHorizontal,
		initialSlots: ["left", "right"],
	},
	AvatarCard: {
		name: "AvatarCard",
		title: "Avatar Card",
		icon: LucideImage,
		initialState: {
			title: "Up&Up",
			subtitle: "Coldplay",
			imageURL: "https://upload.wikimedia.org/wikipedia/en/e/e9/Coldplay%2C_Up%26Up%2C_Artwork.jpg",
		},
	},
	CardList: {
		name: "CardList",
		title: "Card List",
		icon: LucideList,
		initialState: {
			title: "Card List",
			cards: [
				{
					title: "Card Title",
					subtitle: "Subtitle",
					imageURL: "https://avatars.githubusercontent.com/u/499550",
				},
				{
					title: "Card Title",
					subtitle: "Subtitle",
					imageURL: "https://avatars.githubusercontent.com/u/499120",
				},
			],
		},
	},
	Audio: {
		name: "Audio",
		title: "Audio",
		icon: LucideMusic,
		initialState: {
			file: "https://cdn.uppbeat.io/audio-output/208/3691/main-version/streaming-previews/STREAMING-achievement-philip-anderson-main-version-01-31-13804.mp3",
		},
	},
	ImageView: {
		name: "ImageView",
		title: "Image View",
		icon: LucideImage,
		initialState: {
			image: "https://blocks.astratic.com/img/general-img-square.png",
			size: "xs",
		},
	},
	TextBlock: {
		name: "TextBlock",
		title: "Text Block",
		icon: LucideType,
		initialState: {
			fontSize: "text-md",
			fontWeight: "font-normal",
		},
	},
	AppHeader: {
		name: "AppHeader",
		title: "App Header",
		icon: LucideFrame,
		initialState: {
			title: "Frappe",
		},
	},
	BottomTabs: {
		name: "BottomTabs",
		title: "Bottom Tabs",
		icon: LucideArrowRightLeft,
		initialState: {
			tabs: [
				{
					label: "Home",
					icon: "home",
					route: "/",
				},
				{
					label: "Settings",
					icon: "settings",
					route: "/settings",
				},
			],
		},
	},
	MarkdownEditor: {
		name: "MarkdownEditor",
		title: "Markdown",
		icon: LucideFilePenLine,
		initialState: {
			modelValue: "# This is a markdown editor",
		},
	}
}

const proxyComponentMap = new Map<string, any>()
Object.values(COMPONENTS).forEach((component: FrappeUIComponent) => {
	if (component.proxyComponent) {
		proxyComponentMap.set(component.name, component.proxyComponent)
	}
})

function isFrappeUIComponent(name: string) {
	return FRAPPE_UI_COMPONENTS.includes(name)
}

function getProxyComponent(name: string) {
	return proxyComponentMap.get(name)
}

export default {
	...COMPONENTS,
	list: Object.values(COMPONENTS),
	names: Object.keys(COMPONENTS),
	getProxyComponent,
	isFrappeUIComponent,
}
