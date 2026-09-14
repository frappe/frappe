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
const { createApp, nextTick } = await import("vue");
const { loadComponent, loadModule } = await import("./helpers/components.js");
const { presentTool } = await loadModule("chat/toolMeta.js");
const CreateView = await loadComponent("chat/tools/CreateView.vue");
const ReadView = await loadComponent("chat/tools/ReadView.vue");
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

	const step = mount(t, CreateView, {
		arguments: createArgs,
		result: json({
			doctype: "Sales Invoice",
			created: ["INV-001"],
			failures: [{ row: 1, error: "Customer is required" }],
		}),
	});
	assert.equal(texts(step, "th")[0], "Name");
	assert.deepEqual(hrefs(step), ["/app/sales-invoice/INV-001"]);
	assert.ok(step.textContent.includes("Customer is required"));
	assert.equal(
		presentTool("create", createArgs, json({ created: ["INV-001"], failures: [{ row: 1 }] }))
			.stat,
		"1 created · 1 failed"
	);
});

test("read links each record to its Desk form, skipping fields nothing filled", (t) => {
	const rows = [
		{ name: "INV-001", status: "Paid", remarks: "", customer: "" },
		{ name: "INV-002", status: "Paid", remarks: "", customer: "Alpha" },
	];
	const el = mount(t, ReadView, { arguments: { doctype: "Sales Invoice" }, result: json(rows) });
	assert.deepEqual(texts(el, "th"), ["Name", "Status", "Customer"]);
	assert.deepEqual(hrefs(el), ["/app/sales-invoice/INV-001", "/app/sales-invoice/INV-002"]);
	assert.equal(presentTool("read", {}, json(rows)).stat, "2 records");
});

test("delete links its targets until they are gone", (t) => {
	const args = { doctype: "Sales Invoice", names: ["INV-001", "INV-002"] };
	const card = mount(t, NamesView, { arguments: args });
	assert.deepEqual(texts(card, "th"), ["Name"]);
	assert.deepEqual(hrefs(card), ["/app/sales-invoice/INV-001", "/app/sales-invoice/INV-002"]);

	const result = json({
		doctype: "Sales Invoice",
		deleted: ["INV-001"],
		failures: [{ name: "INV-002", error: "Linked with Payment Entry" }],
	});
	const step = mount(t, NamesView, { arguments: args, result });
	assert.deepEqual(hrefs(step), []);
	assert.deepEqual(texts(step, "th"), ["Error", "Name"]);
	assert.ok(step.textContent.includes("Linked with Payment Entry"));
	assert.equal(presentTool("delete", args, result).stat, "1 deleted · 1 failed");
});

test("update shows the values it applies to its targets", (t) => {
	const args = { doctype: "Sales Invoice", names: ["INV-001"], values: { status: "Paid" } };
	const el = mount(t, NamesView, { arguments: args, result: json({ updated: ["INV-001"] }) });
	assert.deepEqual(texts(el, "td").slice(0, 2), ["Status", "Paid"]);
	assert.deepEqual(texts(el, "th"), ["Name"]);
	assert.deepEqual(texts(el, "tbody tr:last-child td").at(-1), "INV-001");
	assert.equal(presentTool("update", args, json({ updated: ["INV-001"] })).stat, "1 updated");
});

test("run_action names its verb and shows what each record did", (t) => {
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
		["find_doctypes", json([{ name: "A" }, { name: "B" }]), "2 matches"],
		["describe", json({ fields: [1, 2, 3] }), "3 fields"],
		["update_memory", json({ memory_id: "m1", action: "added" }), "added"],
		["load_skill", { content: "do the thing" }, ""],
	];
	for (const [name, result, stat] of cases) {
		const presented = presentTool(name, {}, result);
		assert.equal(presented.stat, stat, name);
		assert.equal(presented.expandable, false, name);
		assert.equal(presented.resultComponent, undefined, name);
	}
});

test("a custom tool always shows its output, unfolded", (t) => {
	const presented = presentTool("send_email", { to: "a@b.c" }, json({ sent: true }));
	assert.equal(presented.resultComponent, JsonView);
	const el = mount(t, JsonView, { arguments: {}, result: json({ sent: true }) });
	assert.equal(el.querySelector("pre").textContent, '{\n  "sent": true\n}');
});

test("an approval card gets the view, a bare row does not", () => {
	assert.equal(presentTool("create", createArgs).argsComponent, CreateView);
	assert.equal(presentTool("read", {}).argsComponent, undefined);
	assert.equal(presentTool("read", {}).resultComponent, ReadView);
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

test("bulk targets and failures beyond the first page can be revealed", async (t) => {
	const names = Array.from({ length: 41 }, (_, i) => `INV-${i + 1}`);
	const args = { doctype: "Sales Invoice", names };
	for (const result of [
		null,
		json({
			deleted: names.slice(0, 40),
			failures: [{ name: "INV-41", error: "Still linked" }],
		}),
	]) {
		const el = mount(t, NamesView, { arguments: args, result });
		assert.equal(el.querySelectorAll("tbody tr").length, 20);
		for (const count of [40, 41]) {
			const more = el.querySelector("button");
			assert.ok(more, "hidden rows must be reachable");
			more.click();
			await nextTick();
			assert.equal(el.querySelectorAll("tbody tr").length, count);
		}
		assert.ok(el.textContent.includes("INV-41"));
		if (result) assert.ok(el.textContent.includes("Still linked"));
		assert.equal(el.querySelector("button"), null);
	}
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
	card.querySelector("td button").click();
	await nextTick();
	assert.equal(card.querySelector("td table"), null);
});

test("document actions preserve structured returns", async (t) => {
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
