import assert from "node:assert/strict";
import test from "node:test";

import { readScreen } from "../src/chat/screen.js";

// a DOM node as the reader sees it. `is` lists the selectors it answers to besides its tag;
// `top` is where its box sits, so siblings with one `top` read as a row; `shown: false` hides it
const el = (text, children = [], tag = "div", over = {}) => {
	const { is = [], className = "", top = 0, shown = true, ...rest } = over;
	const elements = children.filter((c) => c.nodeType === 1);
	const all = () => elements.flatMap((c) => [c, ...c.querySelectorAll("*")]);
	const answers = (selector) =>
		selector.split(/,\s*/).some((part) => {
			const excluded = [...part.matchAll(/:not\(\[type=(\w+)\]\)/g)].map((m) => m[1]);
			if (excluded.includes(rest.type)) return false;
			const plain = part.replace(/:not\([^)]*\)/g, "").trim();
			return plain === tag || is.includes(plain) || plain === `.${className}`;
		});
	const node = {
		nodeType: 1,
		tagName: tag.toUpperCase(),
		className,
		classList: { contains: (name) => className.split(" ").includes(name) },
		innerText: text,
		textContent: text,
		childNodes: children,
		children: elements,
		parentElement: null,
		previousElementSibling: null,
		labels: [],
		matches: answers,
		closest: (selector) => {
			for (let n = node; n; n = n.parentElement) if (n.matches(selector)) return n;
			return null;
		},
		querySelector: (selector) => all().find((c) => c.matches(selector)) ?? null,
		querySelectorAll: (selector) =>
			selector === "*" ? all() : all().filter((c) => c.matches(selector)),
		getAttribute: (name) => rest.attrs?.[name] ?? null,
		hasAttribute: (name) => rest.attrs?.[name] != null,
		getClientRects: () => (shown ? [{}] : []),
		getBoundingClientRect: () => ({
			top,
			bottom: top + 20,
			height: 20,
			width: 50,
			right: 100,
		}),
		contains: (other) => node === other || all().includes(other),
		...rest,
	};
	elements.forEach((child, i) => {
		child.parentElement = node;
		child.previousElementSibling = elements[i - 1] ?? null;
	});
	return node;
};
const text = (content) => ({ nodeType: 3, textContent: content });
const input = (value, over = {}) => el("", [], "input", { value, type: "text", ...over });
const label = (control) => {
	const node = el(`${control.label} *`, [], "label");
	control.labels = [node];
	return node;
};

const page = (document, over = {}) => ({
	location: { pathname: "/app/todo", search: "" },
	document: {
		title: "ToDo",
		querySelector: () => null,
		querySelectorAll: () => [],
		...document,
	},
	getSelection: () => ({ toString: () => "" }),
	...over,
});

test("a Desk form reads as its tabs, sections, labelled values and rows, and what it still needs", () => {
	// Desk puts the label and the control in one .frappe-control; a hidden twin shows a value read-only
	const field = (name, control) =>
		el(
			`${name}\n`,
			[el(name, [el(name, [], "label", { className: "control-label" })]), el("", [control])],
			"div",
			{ className: "frappe-control" }
		);
	const customer = input("Palmer Productions Ltd.", { is: ["[role=combobox]"] });
	const dueDate = input("");
	// Desk's checkbox sits inside its label
	const stock = input("", { type: "checkbox", checked: true });
	const stockLabel = el("Update Stock", [stock], "label");
	stock.labels = [stockLabel];
	const total = el("₹ 100", [], "div", { className: "control-value" });
	const hiddenTotal = input("100", { shown: false });
	const grid = el(
		"1\nPen\n2",
		[
			el("1", [], "div", { top: 40 }),
			el("Pen", [], "div", { top: 40 }),
			el("2", [], "div", { top: 40 }),
		],
		"div",
		{ className: "grid-row" }
	);
	const alike = Array.from({ length: 6 }, (_, i) =>
		el(`Link ${i}`, [text(`Link ${i}`), el("", [], "a", { is: ["a[href]"] })], "div", {
			className: "link",
			top: i * 30,
		})
	);
	const body = el("Hello", [
		el("Home", [text("Home")], "nav"),
		el("Menu", [text("Menu")], "div", { className: "body-sidebar-container" }),
		el("New Sales Invoice Not Saved", [
			el("New Sales Invoice", [], "span", { top: 10 }),
			el("Not Saved", [], "span", { top: 10 }),
		]),
		el(
			"Details More Info",
			[
				el("Details", [], "button", { is: ["[role=tab]"], className: "nav-link active" }),
				el("More Info", [], "button", { is: ["[role=tab]"] }),
			],
			"ul",
			{ is: ["[role=tablist]"] }
		),
		el("Details", [], "div", { className: "section-head" }),
		field("Customer", customer),
		field("Due Date", dueDate),
		el("Update Stock", [stockLabel], "div", { className: "frappe-control" }),
		el(
			"Grand Total",
			[
				el("Grand Total", [
					el("Grand Total", [], "label", { className: "control-label" }),
				]),
				el("", [total, hiddenTotal]),
			],
			"div",
			{ className: "frappe-control" }
		),
		grid,
		el("links", alike),
	]);
	const screen = readScreen(
		page(
			{ title: "New Sales Invoice", body },
			{
				location: { pathname: "/app/sales-invoice/new-1", search: "" },
				getSelection: () => ({ toString: () => " the total " }),
				frappe: {
					get_route: () => ["Form", "Sales Invoice", "new-1"],
					meta: {
						get_docfield: (_, fieldname) =>
							fieldname === "due_date" ? { reqd: 1 } : null,
					},
					container: {
						page: {
							frm: {
								doctype: "Sales Invoice",
								doc: {
									name: "new-1",
									customer: "Palmer Productions Ltd.",
									due_date: "",
									items: [],
									total_qty: 0,
								},
								meta: {
									fields: [
										{ fieldname: "customer", fieldtype: "Link", reqd: 1 },
										{ fieldname: "due_date", fieldtype: "Date" },
										{ fieldname: "items", fieldtype: "Table", reqd: 1 },
										{ fieldname: "total_qty", fieldtype: "Float", reqd: 1 },
									],
								},
								is_new: () => true,
								is_dirty: () => false,
							},
						},
					},
				},
			}
		)
	);
	assert.deepEqual(screen, {
		url: "/app/sales-invoice/new-1",
		title: "New Sales Invoice",
		selection: "the total",
		unsaved: true,
		// a zero total is a value to Desk; a blank date and an empty table are not
		missing_mandatory: ["due_date", "items"],
		text: [
			"New Sales Invoice | Not Saved",
			"Tabs: [Details] | More Info",
			"# Details",
			"Customer: Palmer Productions Ltd.",
			"Due Date:",
			"Update Stock: yes",
			"Grand Total: ₹ 100",
			"1 | Pen | 2",
			// Desk's link fields hold links, so alike fields do not read as a list
			...Array.from({ length: 6 }, (_, i) => `Link ${i}`),
		].join("\n"),
	});
});

test("a Desk list or report sends its filters and nothing the model can read itself", () => {
	const list = readScreen(
		page(
			{},
			{
				frappe: { get_route: () => ["List", "ToDo", "Report"] },
				cur_list: {
					doctype: "ToDo",
					data: [{ name: "T1", status: "Open" }],
					get_filters_for_args: () => [["ToDo", "status", "=", "Open"]],
					get_checked_items: () => ["T1"],
					sort_by: "modified",
					sort_order: "desc",
					total_count: 2500,
				},
			}
		)
	);
	assert.deepEqual(list, {
		url: "/app/todo",
		title: "ToDo",
		list: {
			doctype: "ToDo",
			view: "Report",
			filters: [["ToDo", "status", "=", "Open"]],
			order_by: "modified desc",
			total: 2500,
			selected: ["T1"],
		},
	});

	const report = readScreen(
		page(
			{},
			{
				frappe: {
					get_route: () => ["query-report", "General Ledger"],
					query_report: {
						report_name: "General Ledger",
						get_filter_values: () => ({ company: "Acme" }),
						data: [{ account: "Cash", debit: 10 }],
					},
				},
			}
		)
	);
	assert.deepEqual(report, {
		url: "/app/todo",
		title: "ToDo",
		report: { name: "General Ledger", filters: { company: "Acme" } },
	});
});

test("an app's record reads its labelled values, whether the label is a <label> or the text before the control", () => {
	const organization = input("Acme Corp", { label: "Organization" });
	const status = el("Open", [], "button", { is: ["[role=combobox]"] });
	const placeholder = el("Select source", [], "button", {
		is: ["[role=combobox]"],
		attrs: { "data-placeholder": "" },
	});
	const alerts = el("", [], "button", {
		is: ["[role=switch]"],
		attrs: { "aria-checked": "true" },
	});
	const search = input("", { placeholder: "Search" });
	const unlabelled = input("", { type: "checkbox" });
	const secret = input("hunter2", { type: "password", label: "Password" });
	const note = el(
		"See this and that",
		[text("See "), el("this", [], "a"), text(" and "), el("that", [], "b")],
		"p"
	);
	const body = el("unused", [
		el("CRM\nLeads", [text("CRM\nLeads")], "nav"),
		el("John Doe", [], "h1"),
		el("Organization", [label(organization), organization], "div", { className: "field" }),
		el("Status", [el("Status *", [el("Status *", [], "span")]), el("", [status])], "div", {
			className: "field",
		}),
		el("Source", [el("Source", [el("Source", [], "span")]), el("", [placeholder])], "div", {
			className: "field",
		}),
		el("Email alerts", [el("Email alerts", [], "span"), alerts]),
		el("", [search]),
		el("", [unlabelled]),
		el("Password", [label(secret), secret], "div", { className: "field" }),
		note,
		el("·", [], "span"),
		el("y".repeat(7000)),
	]);
	const screen = readScreen(
		page({ title: "John Doe", body }, { location: { pathname: "/crm/leads/L1", search: "" } })
	);
	assert.equal(screen.url, "/crm/leads/L1");
	assert.ok(
		screen.text.startsWith(
			[
				"# John Doe",
				"Organization: Acme Corp",
				"Status: Open",
				"Source:",
				"Email alerts: on",
				"Search:",
				"Password *", // a password field shows its label and nothing else
				"See this and that",
				"yyy",
			].join("\n")
		),
		screen.text
	);
	assert.ok(!screen.text.includes("Leads"));
	assert.ok(!screen.text.includes("hunter2"));
	assert.ok(screen.text.endsWith("… 1110 more characters"));
	assert.equal(screen.fields, undefined);
});

test("an app's list reads as a header row, its first row and a count; a few alike items stay", () => {
	const header = el("ID Subject Status", [
		el("ID", [], "div"),
		el("Subject", [], "div"),
		el("Status", [], "div"),
	]);
	const row = (i) =>
		el(
			`00${i} Ticket ${i} Open`,
			[
				el(`00${i} Ticket ${i} Open`, [
					el(`00${i} Ticket ${i} Open`, [
						el(`00${i}`, [], "div", { top: 50 + i }),
						el(`Ticket ${i}`, [], "div", { top: 50 + i }),
						el("Open", [], "div", { top: 50 + i }),
					]),
				]),
			],
			"a",
			{ is: ["a[href]"], className: "row" }
		);
	const rows = Array.from({ length: 6 }, (_, i) => row(i));
	const contacts = Array.from({ length: 3 }, (_, i) =>
		el(`Contact ${i}`, [], "a", { is: ["a[href]"], className: "contact", top: i * 30 })
	);
	const body = el("unused", [
		header,
		el("rows", rows, "div", { className: "list" }),
		el("contacts", contacts, "div", { className: "people" }),
		el("6 of 6"),
	]);
	const screen = readScreen(
		page(
			{ title: "Tickets", body },
			{ location: { pathname: "/helpdesk/tickets", search: "" } }
		)
	);
	assert.equal(
		screen.text,
		[
			"ID | Subject | Status",
			"000 | Ticket 0 | Open",
			"… 5 more like the one above",
			"Contact 0",
			"Contact 1",
			"Contact 2",
			"6 of 6",
		].join("\n")
	);
});

test("a kanban keeps every column and collapses the cards inside each", () => {
	const card = (col, i) =>
		el(`Deal ${col}-${i}\n₹ ${i}00`, [], "a", { is: ["a[href]"], className: "card" });
	const column = (name) =>
		el(
			name,
			[
				el(name, [], "div", { className: "head" }),
				el(
					"cards",
					Array.from({ length: 5 }, (_, i) => card(name, i)),
					"div",
					{ className: "cards" }
				),
			],
			"div",
			{ className: "column" }
		);
	const body = el(
		"board",
		["Qualification", "Demo", "Proposal", "Negotiation", "Won"].map(column)
	);
	const screen = readScreen(
		page(
			{ title: "Deals", body },
			{ location: { pathname: "/crm/deals/view/kanban", search: "" } }
		)
	);
	assert.equal(
		screen.text,
		[
			"Qualification",
			"Deal Qualification-0\n₹ 000",
			"… 4 more like the one above",
			"Demo",
			"Deal Demo-0\n₹ 000",
			"… 4 more like the one above",
			"Proposal",
			"Deal Proposal-0\n₹ 000",
			"… 4 more like the one above",
			"Negotiation",
			"Deal Negotiation-0\n₹ 000",
			"… 4 more like the one above",
			"Won",
			"Deal Won-0\n₹ 000",
			"… 4 more like the one above",
		].join("\n")
	);
});

test("a page's <main> is read in place of its body, with any dialog open beside it", () => {
	const main = el("Courses\nERPNext Essentials");
	const dialog = el(
		"Enroll?\nYes",
		[el("Enroll?", [], "header"), el("Yes", [], "button", { top: 40 })],
		"div",
		{ is: ["[role=dialog]"] }
	);
	const screen = readScreen(
		page(
			{
				title: "Courses",
				querySelector: (selector) => (selector === "main" ? main : null),
				querySelectorAll: (selector) => (selector === "[role=dialog]" ? [dialog] : []),
				body: el("Sidebar\nCourses\nERPNext Essentials"),
			},
			{ location: { pathname: "/lms/courses", search: "" } }
		)
	);
	assert.deepEqual(screen, {
		url: "/lms/courses",
		title: "Courses",
		text: "Courses\nERPNext Essentials\nEnroll?\nYes",
	});
});
