import { defineAsyncComponent } from "vue"
import { FRAPPE_UI_COMPONENTS } from "@/utils/constants"

import type { FrappeUIComponents, FrappeUIComponent } from "@/types"

import LucideCircleAlert from "~icons/lucide/circle-alert"
import LucideUser from "~icons/lucide/user"
import LucideChevronsRight from "~icons/lucide/chevrons-right"
import LucideBadgeCheck from "~icons/lucide/badge-check"
import LucideRectangleHorizontal from "~icons/lucide/rectangle-horizontal"
import LucideCircleCheck from "~icons/lucide/circle-check"
import LucideCalendar from "~icons/lucide/calendar"
import LucideClock from "~icons/lucide/clock"
import LucideCalendarCheck from "~icons/lucide/calendar-check"
import LucideCalendarClock from "~icons/lucide/calendar-clock"
import LucideCalendarSearch from "~icons/lucide/calendar-search"
import LucideCalendarDays from "~icons/lucide/calendar-days"
import LucideAppWindowMac from "~icons/lucide/app-window-mac"
import LucideMinus from "~icons/lucide/minus"
import LucideChevronDown from "~icons/lucide/chevron-down"
import LucideCircleX from "~icons/lucide/circle-x"
import LucideFeather from "~icons/lucide/feather"
import LucideFileUp from "~icons/lucide/file-up"
import LucideBookType from "~icons/lucide/book-type"
import LucideTag from "~icons/lucide/tag"
import LucideListCheck from "~icons/lucide/list-check"
import LucideEllipsis from "~icons/lucide/ellipsis"
import LucideStar from "~icons/lucide/star"
import LucideMousePointer2 from "~icons/lucide/mouse-pointer-2"
import LucideToggleLeft from "~icons/lucide/toggle-left"
import LucideArrowRightLeft from "~icons/lucide/arrow-right-left"
import LucideLetterText from "~icons/lucide/letter-text"
import LucideALargeSmall from "~icons/lucide/a-large-small"
import LucideEdit from "~icons/lucide/edit"
import LucideMessageSquare from "~icons/lucide/message-square"
import LucideListTree from "~icons/lucide/list-tree"
import LucideCode from "~icons/lucide/code"
import LucideRepeat from "~icons/lucide/repeat"
import LucideFrame from "~icons/lucide/frame"
import LucideSidebar from "~icons/lucide/sidebar"
import LucideImage from "~icons/lucide/image"
import LucideList from "~icons/lucide/list"
import LucideLink from "~icons/lucide/link"
import LucideType from "~icons/lucide/type"
import LucideDollarSign from "~icons/lucide/dollar-sign"
import LucideChartLine from "~icons/lucide/chart-line"
import LucideChartPie from "~icons/lucide/chart-pie"
import LucideListFilter from "~icons/lucide/list-filter"
import LucideSquareMousePointer from "~icons/lucide/square-mouse-pointer"
import LucideTimer from "~icons/lucide/timer"
import LucidePill from "~icons/lucide/pill"
import LucideLoaderCircle from "~icons/lucide/loader-circle"
import LucideSlidersHorizontal from "~icons/lucide/sliders-horizontal"

export const COMPONENTS: FrappeUIComponents = {
	TextBlock: {
		name: "TextBlock",
		title: "Text Block",
		icon: LucideType,
		initialState: {
			text: "Text Block",
			tag: "p",
		},
		hideProps: ["fontSize"],
	},
	Alert: {
		name: "Alert",
		title: "Alert",
		icon: LucideCircleAlert,
		initialState: {
			title: "This user is inactive",
			description: "Please enable the user to allow login access.",
			theme: "yellow",
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
	Breadcrumbs: {
		name: "Breadcrumbs",
		title: "Breadcrumbs",
		icon: LucideChevronsRight,
		initialState: {
			items: [
				{
					label: "Home",
					route: { name: "Home" },
				},
				{
					label: "List",
					route: "/components/breadcrumbs",
				},
			],
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
	CodeEditor: {
		name: "CodeEditor",
		title: "Code Editor",
		icon: LucideCode,
		initialState: {
			modelValue: "console.log('Hello, world!')",
			language: "javascript",
		},
	},
	ContextMenu: {
		name: "ContextMenu",
		title: "Context Menu",
		icon: LucideSquareMousePointer,
		initialState: {
			options: [
				{ label: "Open", icon: "lucide-folder-open", onClick: () => {} },
				{ label: "Rename", icon: "lucide-pencil", onClick: () => {} },
				{ label: "Delete", icon: "lucide-trash", onClick: () => {} },
			],
		},
	},
	Combobox: {
		name: "Combobox",
		title: "Combobox",
		icon: LucideListCheck,
		initialState: {
			placeholder: "Select Fruit",
			options: [
				{
					group: "Fruits",
					options: [
						{
							label: "Apple",
							value: "apple",
							icon: "🍎",
						},
						{
							label: "Banana",
							value: "banana",
							icon: "🍌",
						},
						{
							label: "Orange",
							value: "orange",
							icon: "🍊",
						},
						{
							label: "Grape",
							value: "grape",
							icon: "🍇",
						},
					],
				},
				{
					group: "Vegetables",
					options: [
						{
							label: "Carrot",
							value: "carrot",
							icon: "🥕",
						},
						{
							label: "Broccoli",
							value: "broccoli",
							icon: "🥦",
						},
						{
							label: "Tomato",
							value: "tomato",
							icon: "🍅",
						},
						{
							label: "Lettuce",
							value: "lettuce",
							icon: "🥬",
						},
					],
				},
			],
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
	TimePicker: {
		name: "TimePicker",
		title: "Time",
		icon: LucideClock,
		initialState: {
			placeholder: "Select Time",
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
	MonthPicker: {
		name: "MonthPicker",
		title: "Month Picker",
		icon: LucideCalendarDays,
		initialState: {
			placeholder: "Select Month",
		},
	},
	Dialog: {
		name: "Dialog",
		title: "Dialog",
		icon: LucideAppWindowMac,
		initialState: {
			modelValue: false,
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
					icon: "lucide-edit-2",
				},
				{
					label: "Manage Members",
					onClick: () => {},
					icon: "lucide-users",
				},
				{
					label: "Delete this project",
					onClick: () => {},
					icon: "lucide-trash",
				},
			],
			button: { label: "Actions" },
		},
	},
	Duration: {
		name: "Duration",
		title: "Duration",
		icon: LucideTimer,
		initialState: {
			modelValue: 5445,
			format: "short",
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
	Filter: {
		name: "Filter",
		title: "Filter",
		icon: LucideListFilter,
		initialState: {
			doctype: "User",
			filters: {
				enabled: 1,
			},
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
		additionalProps: {
			modelValue: { required: false },
			placeholder: { required: false, type: String },
			options: {
				required: false,
				type: Array,
				default: () => ["John Doe", "Jane Doe"],
				condition: (state: Record<string, any>) => state.type === "select" || state.type === "autocomplete",
			},
			disabled: { type: Boolean },
		},
	},
	FormLabel: {
		name: "FormLabel",
		title: "Form Label",
		icon: LucideTag,
		initialState: {
			label: "Form Label",
		},
	},
	ListView: {
		name: "ListView",
		title: "List View",
		icon: LucideList,
		initialState: {
			columns: [
				{
					label: "Name",
					key: "name",
					width: 3,
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
				},
				{
					id: 2,
					name: "Jane Doe",
					email: "jane@doe.com",
					status: "Inactive",
					role: "HR",
				},
			],
			rowKey: "id",
		},
	},
	Link: {
		name: "Link",
		title: "Link",
		icon: LucideLink,
		initialState: {
			doctype: "User",
			filters: {
				enabled: 1,
			},
		},
	},
	MultiSelect: {
		name: "MultiSelect",
		title: "Multi Select",
		icon: LucideListCheck,
		initialState: {
			placeholder: "Select Fruits",
			options: [
				{
					label: "Apple",
					value: "apple",
				},
				{
					label: "Banana",
					value: "banana",
				},
				{
					label: "Orange",
					value: "orange",
				},
				{
					label: "Grape",
					value: "grape",
				},
			],
		},
	},
	Pill: {
		name: "Pill",
		title: "Pill",
		icon: LucidePill,
		initialState: {
			label: "Pill",
			active: true,
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
	Rating: {
		name: "Rating",
		title: "Rating",
		icon: LucideStar,
		initialState: {
			label: "Rating",
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
	Sidebar: {
		name: "Sidebar",
		title: "Sidebar",
		icon: LucideSidebar,
		initialState: {
			header: {
				title: "Frappe",
				subtitle: "Jane Doe",
				menuItems: [
					{
						label: "Help",
						to: "/help",
						icon: "{{ getIcon('circle-question-mark') }}",
						onClick: () => alert("Help clicked!"),
					},
					{
						label: "Logout",
						to: "/log-out",
						icon: "{{ getIcon('log-out') }}",
						onClick: () => alert("Logging out..."),
					},
				],
			},
			sections: [
				{
					label: "",
					items: [{ label: "Notifications", icon: "{{ getIcon('bell') }}", to: "" }],
				},
				{
					label: "",
					items: [
						{ label: "Home", icon: "{{ getIcon('house') }}", to: "" },
						{ label: "Profile", icon: "{{ getIcon('user-pen') }}", to: "" },
						{ label: "Settings", icon: "{{ getIcon('settings') }}", to: "" },
					],
				},
			],
		},
	},
	Slider: {
		name: "Slider",
		title: "Slider",
		icon: LucideSlidersHorizontal,
		initialState: {
			modelValue: [40],
			min: 0,
			max: 100,
			step: 1,
		},
	},
	Spinner: {
		name: "Spinner",
		title: "Spinner",
		icon: LucideLoaderCircle,
		initialState: {
			size: "md",
			theme: "gray",
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
			tabs: [{ label: "Github" }, { label: "Twitter" }, { label: "Linkedin" }],
		},
		expandArrayProps: true,
	},
	TabButtons: {
		name: "TabButtons",
		title: "Tab Buttons",
		icon: LucideArrowRightLeft,
		initialState: {
			options: [
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
			modelValue: "Type something...",
			editorClass: "prose-sm max-w-none min-h-[4rem] border rounded-b-lg border-t-0 p-2",
			editable: true,
			fixedMenu: true,
			bubbleMenu: true,
		},
		overrideProps: {
			bubbleMenu: {
				type: "boolean",
				inputType: "checkbox",
			},
			fixedMenu: {
				type: "boolean",
				inputType: "checkbox",
			},
			floatingMenu: {
				type: "boolean",
				inputType: "checkbox",
			},
			starterkitOptions: {
				type: "object",
				inputType: "code",
			},
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
	Repeater: {
		name: "Repeater",
		title: "Repeater",
		icon: LucideRepeat,
	},
	HTML: {
		name: "HTML",
		title: "HTML",
		icon: LucideCode,
		initialState: {
			html: "<p>Your HTML content here</p>",
		},
		overrideProps: {
			html: {
				type: "string",
				inputType: "html",
			},
		},
	},
	// block template based components
	Header: {
		name: "Header",
		title: "Header",
		icon: LucideFrame,
		blockTemplate: "header",
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
	// charts
	NumberChart: {
		name: "NumberChart",
		title: "Number Chart",
		icon: LucideDollarSign,
		initialState: {
			config: {
				title: "Total Sales",
				value: 123456,
				prefix: "$",
				delta: 10,
				deltaSuffix: "% MoM",
				negativeIsBetter: false,
			},
		},
	},
	AxisChart: {
		name: "AxisChart",
		title: "Axis Chart",
		icon: LucideChartLine,
		initialState: {
			config: {
				data: [
					{
						month: "2021-01-01",
						sales: 200,
					},
					{
						month: "2021-02-01",
						sales: 300,
					},
					{
						month: "2021-03-01",
						sales: 250,
					},
					{
						month: "2021-04-01",
						sales: 350,
					},
					{
						month: "2021-05-01",
						sales: 400,
					},
					{
						month: "2021-06-01",
						sales: 300,
					},
				],
				title: "Monthly Sales",
				subtitle: "Sales data for first half of the year",
				xAxis: {
					key: "month",
					type: "time",
					title: "Month",
					timeGrain: "month",
				},
				yAxis: {
					title: "Amount ($)",
					echartOptions: {
						min: 0,
						max: 800,
					},
				},
				series: [
					{
						name: "sales",
						type: "bar",
					},
				],
			},
		},
	},
	DonutChart: {
		name: "DonutChart",
		title: "Donut Chart",
		icon: LucideChartPie,
		initialState: {
			config: {
				data: [
					{
						product: "Apple Watch",
						sales: 400,
					},
					{
						product: "Services",
						sales: 400,
					},
					{
						product: "iMac",
						sales: 350,
					},
					{
						product: "Accessories",
						sales: 350,
					},
					{
						product: "iPad",
						sales: 300,
					},
					{
						product: "AirPods",
						sales: 300,
					},
					{
						product: "Apple TV",
						sales: 300,
					},
					{
						product: "Others",
						sales: 300,
					},
					{
						product: "Macbook",
						sales: 250,
					},
					{
						product: "Beats",
						sales: 250,
					},
					{
						product: "iPhone",
						sales: 200,
					},
					{
						product: "HomePod",
						sales: 200,
					},
				],
				title: "Product Sales Distribution",
				subtitle: "Sales distribution across products",
				categoryColumn: "product",
				valueColumn: "sales",
			},
		},
	},
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

function get(name: string): FrappeUIComponent | undefined {
	return COMPONENTS[name] || undefined
}

export default {
	...COMPONENTS,
	list: Object.values(COMPONENTS),
	names: Object.keys(COMPONENTS),
	getProxyComponent,
	isFrappeUIComponent,
	get,
}

