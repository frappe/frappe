// What the page beside the panel shows, read from its window: the address and the visible text,
// laid out the way a reader sees it: `#` before a heading, `Label: value` for a field, `Tabs:` for
// a tab bar, a row's cells joined by ` | `, and a count in place of a list's later rows. Desk adds
// what text cannot show: whether a form is unsaved and which required fields are empty. A Desk
// list or report sends only its filters; the model reads the records itself.
const TEXT = 6000; // characters of a page's text
const VALUE = 1000; // characters of one field's value
const SELECTION = 2000;
const LABEL = 60; // longer text before a control is not its label
const CELL = 80; // longer text is prose, not a cell
// frappe-ui's Select and Switch are buttons; Desk shows a read-only value in a div. A password
// never leaves the page
const CONTROLS =
	"input:not([type=hidden]):not([type=password]):not([type=radio]):not([type=range])" +
	":not([type=button]):not([type=submit]):not([type=file]), textarea, select, [role=combobox], " +
	"[role=switch], .control-value";
const HEADINGS = "h1, h2, h3, h4, h5, h6, .section-head";
// the chrome around a page says the same on every page; Desk's sidebar is a plain div, and its
// fieldname tooltips show on hover only
const SKIP = "nav, aside, footer, [role=navigation], script, style, noscript, template";
const DESK_SKIP = `${SKIP}, .body-sidebar-container, .tooltip-content`;
// an app's list rows and cards: this many alike siblings, each a link or holding one. Desk's
// own lists are read from its globals, and its link fields hold links too
const RUN = 5;

export function readScreen(page) {
	const screen = {
		url: page.location.pathname + page.location.search,
		title: page.document.title,
	};
	const selection = page.getSelection?.()?.toString().trim();
	if (selection) screen.selection = clip(selection, SELECTION);
	const onDesk = typeof page.frappe?.get_route === "function";
	const desk = onDesk ? readDesk(page) : {};
	Object.assign(screen, desk);
	if (!desk.list && !desk.report) screen.text = clip(readPage(page.document, onDesk), TEXT);
	return screen;
}

function readDesk(page) {
	const { frappe, cur_list } = page;
	const route = frappe.get_route();
	const frm = frappe.container?.page?.frm; // the form view keeps its form on its page
	const screen = {};
	if (route[0] === "Form" && frm?.doc) {
		screen.unsaved = Boolean(frm.is_new() || frm.is_dirty());
		screen.missing_mandatory = missingMandatory(frm, frappe);
	} else if (route[0] === "query-report" && frappe.query_report) {
		screen.report = {
			name: frappe.query_report.report_name,
			filters: frappe.query_report.get_filter_values?.() ?? {},
		};
	} else if (cur_list && route[1] === cur_list.doctype) {
		screen.list = {
			doctype: cur_list.doctype,
			view: route[2] || "List",
			filters: cur_list.get_filters_for_args?.() ?? [],
		};
		if (cur_list.sort_by)
			screen.list.order_by = `${cur_list.sort_by} ${cur_list.sort_order ?? ""}`.trim();
		if (cur_list.total_count != null) screen.list.total = cur_list.total_count;
		const selected = cur_list.get_checked_items?.(true) ?? [];
		if (selected.length) screen.list.selected = selected;
	}
	return screen;
}

// toggle_reqd and mandatory_depends_on change the live docfield, not the meta's
function missingMandatory(frm, frappe) {
	return frm.meta.fields
		.filter((df) => {
			const live =
				frappe.meta?.get_docfield?.(frm.doctype, df.fieldname, frm.doc.name) ?? df;
			const value = frm.doc[df.fieldname];
			return (
				live.reqd &&
				(value == null || value === "" || (Array.isArray(value) && !value.length))
			);
		})
		.map((df) => df.fieldname);
}

function readPage(document, onDesk) {
	const main = document.querySelector("main") ?? document.body;
	// an app's dialog opens on the body, outside <main>
	const dialogs = [...document.querySelectorAll("[role=dialog]")].filter(
		(d) => !main.contains(d)
	);
	const skip = onDesk ? DESK_SKIP : SKIP;
	return [main, ...dialogs]
		.flatMap((root) => textOf(root, skip, onDesk ? new Map() : runsOf(root)))
		.join("\n");
}

function textOf(root, skip, runs) {
	const fields = fieldsOf(root);
	const consumed = new Set();
	for (const [at, { label }] of fields) if (label && label !== at) consumed.add(label);
	// the elements to look inside; any other reads whole
	const open = ancestorsOf([
		...fields.keys(),
		...consumed,
		...runs.keys(),
		...root.querySelectorAll(`${skip}, ${HEADINGS}, [role=tablist]`),
	]);
	const parts = [];
	// a lone separator or bullet says nothing
	const push = (text) => /[\p{L}\p{N}]/u.test(text) && parts.push(text);
	const walk = (node) => {
		if (node.nodeType === 3) {
			push(node.textContent.replace(/\s+/g, " ").trim());
			return;
		}
		if (node.nodeType !== 1 || node.matches(skip) || hidden(node) || consumed.has(node))
			return;
		if (fields.has(node)) {
			const { label, control } = fields.get(node);
			parts.push(`${labelText(label, control)}: ${clip(valueOf(control), VALUE)}`.trimEnd());
		} else if (node.matches("[role=tablist]")) {
			parts.push(`Tabs: ${tabsOf(node)}`);
		} else if (node.matches(HEADINGS)) {
			parts.push(`# ${node.innerText.trim()}`);
		} else if (!open.has(node)) {
			push(leafText(node));
		} else {
			let noted = false;
			for (const child of node.childNodes) {
				if (!runs.has(child)) walk(child);
				else if (!noted) {
					parts.push(`… ${runs.get(child)} more like the one above`);
					noted = true;
				}
			}
		}
	};
	walk(root);
	return parts;
}

// every visible control under `root` with its label, keyed by the element that reads as the
// field: the label when it wraps the control, as a checkbox's does, else the control itself
function fieldsOf(root) {
	const found = new Map();
	for (const control of root.querySelectorAll(CONTROLS)) {
		if (hidden(control)) continue;
		const label = labelOf(control);
		if (!label && control.type === "checkbox") continue;
		found.set(label?.contains(control) ? label : control, { label, control });
	}
	return found;
}

// a <label for>, Desk's .control-label, or the short text just before the control's box, as
// CRM and Helpdesk lay their fields out
function labelOf(control) {
	if (control.labels?.[0]) return control.labels[0];
	// a grid's row checks sit inside the table's control, which is not theirs
	const box = control.closest(".frappe-control, .grid-row, .grid-heading-row");
	const desk = box?.matches(".frappe-control") && box.querySelector(".control-label");
	if (desk) return desk;
	let node = control;
	for (let up = 0; up < 6 && node; up++, node = node.parentElement) {
		const before = node.previousElementSibling;
		const text = before?.innerText?.trim();
		if (
			text &&
			text.length <= LABEL &&
			!text.includes("\n") &&
			!before.querySelector(CONTROLS)
		) {
			return before;
		}
	}
	return null;
}

function labelText(label, control) {
	return (
		label?.innerText.trim().replace(/\s*\*$/, "") ||
		control.getAttribute("aria-label") ||
		control.placeholder ||
		control.name ||
		"Field"
	);
}

function valueOf(el) {
	if (el.matches("[role=switch]"))
		return el.getAttribute("aria-checked") === "true" ? "on" : "off";
	if (el.type === "checkbox") return el.checked ? "yes" : "no";
	if (el.tagName === "SELECT") return el.selectedOptions?.[0]?.text ?? el.value;
	if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") return String(el.value);
	return el.hasAttribute("data-placeholder") ? "" : el.innerText.trim();
}

function tabsOf(tablist) {
	return [...tablist.querySelectorAll("[role=tab]")]
		.filter((tab) => !hidden(tab))
		.map((tab) => {
			const label = tab.innerText.trim();
			const active =
				tab.getAttribute("aria-selected") === "true" || tab.classList.contains("active");
			return active ? `[${label}]` : label;
		})
		.join(" | ");
}

// a block with no text of its own reads as its parts: cells side by side as one line, stacked
// parts each on their own; a block with text of its own reads as innerText gives it
function leafText(node) {
	const cells = worded(node);
	if (ownText(node) || !cells.length) return node.innerText.trim();
	if (cells.length === 1) return leafText(cells[0]);
	const texts = cells.map((cell) => cell.innerText.trim().replace(/\s*\n\s*/g, " "));
	const { top, bottom } = cells[0].getBoundingClientRect();
	const online = (cell) => {
		const rect = cell.getBoundingClientRect();
		const middle = (rect.top + rect.bottom) / 2;
		return middle >= top && middle <= bottom;
	};
	if (texts.every((text) => text.length <= CELL) && cells.every(online))
		return texts.join(" | ");
	return cells.map(leafText).join("\n");
}

// the visible children with something to read
const worded = (el) =>
	[...el.children].filter((child) => !hidden(child) && child.innerText?.trim());
const ownText = (el) =>
	[...el.childNodes].some((child) => child.nodeType === 3 && child.textContent.trim());

// the rows past the first of every run under `root`, each mapped to how many it stands for.
// Inner runs come first, so a kanban's columns, each holding a run of cards, stay apart
function runsOf(root) {
	const found = new Map();
	const holders = new Set();
	for (const parent of [root, ...root.querySelectorAll("*")].reverse()) {
		const alike = new Map();
		for (const child of parent.children) {
			if (hidden(child) || !child.textContent.trim()) continue;
			const key = `${child.tagName}|${child.className}`;
			alike.set(key, [...(alike.get(key) ?? []), child]);
		}
		for (const rows of alike.values()) {
			if (rows.length < RUN || !isRow(rows[0]) || rows.some((row) => holders.has(row)))
				continue;
			for (const row of rows.slice(1)) found.set(row, rows.length - 1);
			for (let node = parent; node; node = node.parentElement) holders.add(node);
		}
	}
	return found;
}

const isRow = (el) => el.matches("a[href]") || el.querySelectorAll("a[href]").length === 1;

function ancestorsOf(nodes) {
	const found = new Set();
	for (let node of nodes) {
		for (node = node.parentElement; node && !found.has(node); node = node.parentElement) {
			found.add(node);
		}
	}
	return found;
}

function hidden(el) {
	if (!el.getClientRects().length) {
		// an element with `display: contents` draws no box of its own but its children show
		const view = el.ownerDocument?.defaultView;
		return !view || view.getComputedStyle(el).display !== "contents";
	}
	// a box of no size or off the page: hints for screen readers, hover tooltips, parked pickers
	const { width, height, right, bottom } = el.getBoundingClientRect();
	return (width <= 1 && height <= 1) || right <= 0 || bottom <= 0;
}

function clip(value, limit) {
	if (typeof value !== "string" || value.length <= limit) return value;
	return `${value.slice(0, limit)}… ${value.length - limit} more characters`;
}
