import assert from "node:assert/strict";
import test from "node:test";
import { JSDOM } from "jsdom";

const dom = new JSDOM("<body></body>", { url: "http://localhost/flow" });
for (const name of [
	"window",
	"document",
	"Document",
	"Element",
	"SVGElement",
	"HTMLElement",
	"Node",
	"Event",
])
	globalThis[name] = dom.window[name];
const scrolled = [];
dom.window.HTMLElement.prototype.scrollIntoView = function (options) {
	scrolled.push([this, options]);
};
const { createApp, nextTick } = await import("vue");
const { loadComponent, loadModule } = await import("./helpers/components.js");
const { presentTool } = await loadModule("chat/toolMeta.js");
const CreateView = await loadComponent("chat/tools/CreateView.vue");
const ReadView = await loadComponent("chat/tools/ReadView.vue");
const ReportView = await loadComponent("chat/tools/ReportView.vue");
const NamesView = await loadComponent("chat/tools/NamesView.vue");
const CodeView = await loadComponent("chat/tools/CodeView.vue");
const SnippetView = await loadComponent("chat/tools/SnippetView.vue");
const JsonView = await loadComponent("chat/tools/JsonView.vue");

function mount(t, component, props) {
	const el = document.createElement("div");
	document.body.append(el);
	const app = createApp(component, props);
	app.mount(el);
	t.after(() => {
		app.unmount();
		el.remove();
	});
	return el;
}
const texts = (el, selector) =>
	[...el.querySelectorAll(selector)].map((node) => node.textContent.trim());
const hrefs = (el) => [...el.querySelectorAll("a")].map((node) => node.getAttribute("href"));
const json = (value) => ({ content: JSON.stringify(value) });

const records = [
	{ customer: "Alpha", grand_total: 10 },
	{ customer: "Beta", items: [{ qty: 1 }, { qty: 2 }] },
];
const createArgs = { doctype: "Sales Invoice", records };

test("create tables only the fields the records use, before and after the run", (t) => {
	const card = mount(t, CreateView, { arguments: createArgs });
	assert.deepEqual(texts(card, "th"), ["Customer", "Grand Total", "Items"]);
	assert.deepEqual(texts(card, "tbody tr:first-child td"), ["Alpha", "10", ""]);
	assert.deepEqual(texts(card, "tbody tr:last-child td"), ["Beta", "", "2 rows"]);

	const result = json({ doctype: "Sales Invoice", created: ["INV-001", "INV-002"] });
	const step = mount(t, CreateView, { arguments: createArgs, result });
	assert.equal(texts(step, "th")[0], "Name");
	assert.deepEqual(hrefs(step), ["/app/sales-invoice/INV-001", "/app/sales-invoice/INV-002"]);
	assert.equal(presentTool("create", createArgs, result).stat, "2 created");
});

test("read_records links each record to its Desk form, skipping fields nothing filled", (t) => {
	const rows = [
		{ name: "INV-001", status: "Paid", remarks: "", customer: "" },
		{ name: "INV-002", status: "Paid", remarks: "", customer: "Alpha" },
	];
	const result = json({ total: 2, records: rows });
	const el = mount(t, ReadView, { arguments: { doctype: "Sales Invoice" }, result });
	assert.deepEqual(texts(el, "th"), ["Name", "Status", "Customer"]);
	assert.deepEqual(hrefs(el), ["/app/sales-invoice/INV-001", "/app/sales-invoice/INV-002"]);
	assert.equal(presentTool("read_records", {}, result).stat, "2 records");
	assert.equal(
		presentTool("read_records", {}, json({ total: 134, records: rows })).stat,
		"2 of 134 records"
	);
});

test("run_report tables rows under the report's labels, its total pinned below and labelled where Frappe left it blank", (t) => {
	const args = { report_name: "Accounts Receivable" };
	// two columns share a label, and numeric fieldnames would sort first as object keys
	const report = {
		columns: [
			{ fieldname: "party", label: "Party" },
			{ fieldname: "2026", label: "Balance" },
			{ fieldname: "2027", label: "Balance" },
			{ fieldname: "remarks", label: "Remarks" },
		],
		rows: Array.from({ length: 25 }, (_, i) => ({
			party: `P${i + 1}`,
			2026: 1,
			2027: 2,
			remarks: "",
		})),
		row_count: 30,
		total_row: { party: "Total", 2026: 25, 2027: 50, remarks: "" },
	};
	const el = mount(t, ReportView, { arguments: args, result: json(report) });
	assert.deepEqual(texts(el, "th"), ["Party", "Balance", "Balance"]);
	assert.deepEqual(texts(el, "tbody tr:first-child td"), ["P1", "1", "2"]);
	// page one holds 20 rows; the total stays in view
	assert.equal(el.querySelectorAll("tbody tr").length, 20);
	assert.deepEqual(texts(el, "tfoot td"), ["Total", "25", "50"]);
	const presented = presentTool("run_report", args, json(report));
	assert.equal(presented.subject, "Accounts Receivable");
	assert.equal(presented.stat, "25 of 30 rows");
	assert.equal(
		presentTool("run_report", args, json({ ...report, row_count: 25 })).stat,
		"25 rows"
	);

	// a blank first cell is labelled only on the total row
	const dated = {
		columns: [
			{ fieldname: "posting_date", label: "Posting Date" },
			{ fieldname: "amount", label: "Amount" },
		],
		rows: [
			{ posting_date: "2026-08-19", amount: 10 },
			{ posting_date: "", amount: 5 },
		],
		row_count: 2,
		total_row: { posting_date: "", amount: 15 },
	};
	const unlabelled = mount(t, ReportView, { arguments: {}, result: json(dated) });
	assert.deepEqual(texts(unlabelled, "tbody tr:last-child td"), ["", "5"]);
	assert.deepEqual(texts(unlabelled, "tfoot td"), ["Total", "15"]);
});

test("delete lists its targets a page at a time, linked to their forms until they are gone", async (t) => {
	const names = Array.from({ length: 41 }, (_, i) => `INV-${i + 1}`);
	const args = { doctype: "Sales Invoice", names };
	const result = json({ doctype: "Sales Invoice", deleted: names });
	const linked = names.slice(0, 20).map((name) => `/app/sales-invoice/${name}`);
	for (const [outcome, links] of [
		[null, linked],
		[result, []],
	]) {
		const el = mount(t, NamesView, { arguments: args, result: outcome });
		assert.deepEqual(texts(el, "th"), ["Name"]);
		assert.deepEqual(hrefs(el), links);
		assert.equal(el.querySelectorAll("tbody tr").length, 20);
		for (const count of [40, 41]) {
			const more = el.querySelector("button");
			assert.ok(more, "hidden rows must be reachable");
			more.click();
			await nextTick();
			assert.equal(el.querySelectorAll("tbody tr").length, count);
		}
		assert.ok(el.textContent.includes("INV-41"));
		assert.equal(el.querySelector("button"), null);
	}
	assert.equal(presentTool("delete", args, result).stat, "41 deleted");
});

test("update shows the values it applies to its targets", (t) => {
	const args = { doctype: "Sales Invoice", names: ["INV-001"], values: { status: "Paid" } };
	const el = mount(t, NamesView, { arguments: args, result: json({ updated: ["INV-001"] }) });
	assert.deepEqual(texts(el, "td").slice(0, 2), ["Status", "Paid"]);
	assert.deepEqual(texts(el, "th"), ["Name"]);
	assert.deepEqual(texts(el, "tbody tr:last-child td").at(-1), "INV-001");
	assert.equal(presentTool("update", args, json({ updated: ["INV-001"] })).stat, "1 updated");
});

async function openDetails(el) {
	const details = el.querySelector("details");
	assert.ok(details, "structured values must have inspectable details");
	details.open = true;
	details.dispatchEvent(new Event("toggle"));
	await nextTick();
	return JSON.parse(details.querySelector("pre").textContent);
}

// A child table unfolds under its row on a click; in a values list it is already open.
async function childTable(el) {
	const toggle = el.querySelector("td button");
	if (toggle) {
		toggle.click();
		await nextTick();
	}
	const table = el.querySelector("td table");
	assert.ok(table, "child rows must render as a table");
	return { columns: texts(table, "th"), cells: texts(table, "td") };
}

test("run_action names its verb and shows what each record did, structured returns included", async (t) => {
	const rename = {
		doctype: "Item",
		names: ["OLD"],
		action: "rename",
		args: { new_name: "NEW" },
	};
	const result = json({ action: "rename", old: "OLD", new: "NEW" });
	const el = mount(t, NamesView, { arguments: rename, result });
	assert.deepEqual(texts(el, "th"), ["Name", "Renamed To"]);
	assert.deepEqual(texts(el, "tbody td").slice(-2), ["OLD", "NEW"]);
	assert.equal(presentTool("run_action", rename, result).label, "Renaming");
	assert.equal(presentTool("run_action", rename, result).stat, "renamed");

	const submit = { doctype: "Sales Invoice", names: ["INV-001", "INV-002"], action: "submit" };
	const submitted = json({
		action: "submit",
		results: [{ name: "INV-001", result: { docstatus: 1 } }],
	});
	assert.equal(presentTool("run_action", submit, submitted).label, "Submitting");
	assert.equal(presentTool("run_action", submit, submitted).stat, "1 done");

	const returning = (outcome) =>
		mount(t, NamesView, {
			arguments: { doctype: "Sales Invoice", names: ["INV-1"], action: "make_payment" },
			result: json({ results: [{ name: "INV-1", result: outcome }] }),
		});
	const record = { payment_entry: "PAY-1", amount: 123 };
	assert.deepEqual(await openDetails(returning(record)), record);
	assert.deepEqual(await childTable(returning([{ name: "PAY-1", amount: 123 }])), {
		columns: ["Name", "Amount"],
		cells: ["PAY-1", "123"],
	});
});

test("execute keeps the code and pretty-prints what it returned", (t) => {
	const el = mount(t, CodeView, {
		arguments: { code: "return 1", description: "Count invoices" },
		result: { content: '{"total":2}' },
	});
	assert.ok(el.textContent.includes("Result"));
	const [source, result] = [...el.querySelectorAll("pre")];
	assert.equal(source.textContent, "return 1");
	assert.equal(result.textContent, '{\n  "total": 2\n}');
	assert.equal(
		presentTool("execute", { description: "Count invoices" }).subject,
		"Count invoices"
	);
});

test("a result its view cannot read, saved before its tool's return changed or cut, shows as text without a count, except under execute's code", () => {
	const saved = json([{ name: "A" }, { name: "B" }]);
	const read = presentTool("read_records", {}, saved);
	assert.equal(read.stat, "");
	assert.equal(read.resultComponent, JsonView);
	assert.equal(presentTool("find_doctypes", {}, saved).stat, "");
	// a cut result is no longer JSON
	const cut = {
		content: '[{"name": "A"}, {"na\n\n[Cut to the first 50 KB of 2.0 MB.]',
		details: { truncation: { truncated: true } },
	};
	assert.equal(presentTool("read_records", {}, cut).resultComponent, JsonView);
	assert.equal(presentTool("run_report", {}, cut).resultComponent, JsonView);
	assert.equal(presentTool("execute", {}, cut).resultComponent, CodeView);
});

test("search hits group under the source they came from", (t) => {
	const hits = [
		{ source: "Policy", content: "Overdue after 30 days" },
		{ source: "Policy", content: "Reminders go out weekly" },
		{ source: "Handbook", content: "Escalate to finance" },
	];
	const el = mount(t, SnippetView, { arguments: { query: "overdue" }, result: json(hits) });
	const headings = [...el.firstElementChild.children].map((group) =>
		group.firstElementChild.textContent.trim()
	);
	assert.deepEqual(headings, ["Policy", "Handbook"]);
	assert.equal(presentTool("search_knowledge", {}, json(hits)).stat, "3 hits");
});

test("lookups report a count and open nothing", () => {
	const cases = [
		[
			"find_doctypes",
			json({ total: 2, doctypes: [{ name: "A" }, { name: "B" }] }),
			"2 matches",
		],
		[
			"find_doctypes",
			json({ total: 52, doctypes: [{ name: "A" }, { name: "B" }] }),
			"2 of 52 matches",
		],
		["describe", json({ fields: [1, 2, 3] }), "3 fields"],
		["update_memory", json({ memory_id: "m1", action: "added" }), "added"],
		["load_skill", { content: "do the thing" }, ""],
		// a sub-agent row keeps the core's own look
		["subagent", null, ""],
	];
	for (const [name, result, stat] of cases) {
		const presented = presentTool(name, {}, result);
		assert.equal(presented.stat, stat, name);
		assert.equal(presented.expandable, false, name);
		assert.equal(presented.resultComponent, undefined, name);
	}
});

test("an approval card gets the view, a custom tool always shows its output, and the server's file tools keep the core's rows", (t) => {
	assert.equal(presentTool("create", createArgs).argsComponent, CreateView);
	assert.equal(presentTool("read_records", {}).argsComponent, undefined);
	assert.equal(presentTool("read_records", {}).resultComponent, ReadView);

	const presented = presentTool("send_email", { to: "a@b.c" }, json({ sent: true }));
	assert.equal(presented.resultComponent, JsonView);
	const el = mount(t, JsonView, { arguments: {}, result: json({ sent: true }) });
	assert.equal(el.querySelector("pre").textContent, '{\n  "sent": true\n}');

	const read = { content: "import frappe", details: { total_lines: 1 } };
	assert.deepEqual(presentTool("read", { path: "flow/hooks.py" }, read), {});
	const grep = { content: "flow/hooks.py:1:import frappe", details: { matches: 1 } };
	assert.deepEqual(presentTool("grep", { pattern: "frappe" }, grep), {});
});

test("create and update approvals unfold child records as tables", async (t) => {
	const items = [{ item_code: "ITEM-1", qty: 9, rate: 500 }];
	const unfolded = { columns: ["Item Code", "Qty", "Rate"], cells: ["ITEM-1", "9", "500"] };
	for (const [component, args] of [
		[CreateView, { doctype: "Sales Invoice", records: [{ items }] }],
		[NamesView, { doctype: "Sales Invoice", names: ["INV-1"], values: { items } }],
		[NamesView, { doctype: "Sales Invoice", names: ["INV-1"], args: { items } }],
	]) {
		const el = mount(t, component, { arguments: args });
		assert.equal(el.querySelector("pre"), null, "no JSON dump");
		assert.deepEqual(await childTable(el), unfolded);
	}

	const card = mount(t, CreateView, {
		arguments: { doctype: "Sales Invoice", records: [{ items }] },
	});
	assert.equal(card.querySelector("td table"), null);
	assert.equal(texts(card, "td button")[0], "1 row");
	assert.deepEqual(await childTable(card), unfolded);
	// unfolding past the bottom edge nudges the new row into view, as a tool's dropdown does
	const [target, how] = scrolled.at(-1);
	assert.equal(target, card.querySelector("td table").closest("tr"));
	assert.equal(how.block, "nearest");
	card.querySelector("td button").click();
	await nextTick();
	assert.equal(card.querySelector("td table"), null);
});
