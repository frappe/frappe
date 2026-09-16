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
const { loadComponent, transport } = await import("./helpers/components.js");
const DocPanel = await loadComponent("settings/DocPanel.vue");
const DocForm = await loadComponent("settings/DocForm.vue");
const FieldControl = await loadComponent("settings/FieldControl.vue");

function mount(t, component, props) {
	const el = document.createElement("div");
	document.body.append(el);
	const app = createApp(component, props);
	app.provide("flowPage", { can: () => true, changed: () => {}, state: { boot: {} } });
	app.mount(el);
	t.after(() => {
		app.unmount();
		el.remove();
	});
	return el;
}
async function until(check) {
	for (let i = 0; i < 100; i++) {
		if (check()) return;
		await new Promise((resolve) => setTimeout(resolve, 5));
	}
	assert.fail("timed out");
}
function type(el, value) {
	const input = el.querySelector("input");
	input.value = value;
	input.dispatchEvent(new Event("input", { bubbles: true }));
}
const spec = {
	doctype: "Flow Tool",
	label: "Tools",
	singular: "tool",
	titleField: "title",
	listFields: ["name", "title"],
	fields: [],
};

test("settings can load and search beyond the first 200 records", async (t) => {
	const records = Array.from({ length: 401 }, (_, i) => ({
		name: `tool-${i}`,
		title: `Tool ${i}`,
	}));
	transport.answers["frappe.client.get_list"] = (args) => {
		const query = args.or_filters?.[0]?.[2]?.slice(1, -1);
		const rows = query ? records.filter((row) => row.title.includes(query)) : records;
		return rows.slice(args.limit_start, args.limit_start + args.limit_page_length);
	};
	const el = mount(t, DocPanel, { spec });
	await until(() => el.querySelectorAll("li").length === 200);
	[...el.querySelectorAll("button")]
		.find((button) => button.textContent === "Load more")
		.click();
	await until(() => el.querySelectorAll("li").length === 400);
	[...el.querySelectorAll("button")]
		.find((button) => button.textContent === "Load more")
		.click();
	await until(() => el.querySelectorAll("li").length === 401);
	assert.ok(
		![...el.querySelectorAll("button")].some((button) => button.textContent === "Load more")
	);
	type(el, "Tool 400");
	await until(() => el.querySelectorAll("li").length === 1);
	assert.ok(el.querySelector("li").textContent.includes("Tool 400"));
	assert.equal(transport.calls.at(-1)[1].limit_start, 0);
	el.querySelector("li button").click();
	await nextTick();
	assert.equal(el.querySelector("[data-stub=DocForm]").getAttribute("name"), "tool-400");
});

test("an older settings search cannot overwrite a newer result", async (t) => {
	let finishOld;
	transport.answers["frappe.client.get_list"] = ({ or_filters }) => {
		if (or_filters.length) return [{ name: "new", title: "Matching" }];
		return new Promise((resolve) => (finishOld = resolve));
	};
	const el = mount(t, DocPanel, { spec });
	type(el, "Matching");
	await until(() => el.querySelector("li"));
	finishOld([{ name: "old", title: "Stale" }]);
	await new Promise((resolve) => setImmediate(resolve));
	assert.equal(el.querySelectorAll("li").length, 1);
	assert.ok(el.querySelector("li").textContent.includes("Matching"));
});

for (const typeName of ["link", "multilink"]) {
	test(`${typeName} searches the server and retains the current selection`, async (t) => {
		transport.calls.length = 0;
		transport.answers["frappe.desk.search.search_link"] = ({ txt }) =>
			txt ? [{ value: "tool-900", label: "A later tool" }] : [{ value: "tool-1" }];
		const el = mount(t, FieldControl, {
			field: { name: "tools", type: typeName, label: "Tools", link: "Flow Tool" },
			doc: {
				doctype: "Flow Agent",
				tools: typeName === "multilink" ? ["selected"] : "selected",
			},
		});
		await until(() => el.textContent.includes("tool-1"));
		assert.ok(el.textContent.includes("selected"));
		type(el, "later");
		await until(() => el.textContent.includes("A later tool"));
		assert.ok(el.textContent.includes("selected"));
		assert.equal(transport.calls.at(-1)[1].txt, "later");
		assert.equal(transport.calls.at(-1)[1].reference_doctype, "Flow Agent");
	});
}

// a Frappe JSON column carries a json_valid check, which an empty string fails
const sourceSpec = {
	doctype: "Flow Knowledge Source",
	label: "Knowledge",
	singular: "source",
	titleField: "title",
	listFields: ["name", "title"],
	fields: [
		{ name: "title", label: "Title", type: "text" },
		{ name: "filters", label: "Filters", type: "code", language: "json" },
	],
};

async function saveSource(t, name, answers) {
	transport.calls.length = 0;
	Object.assign(transport.answers, answers);
	const el = mount(t, DocForm, { spec: sourceSpec, name });
	await until(() => el.querySelector("input"));
	type(el, "ToDo");
	await nextTick();
	[...el.querySelectorAll("button")]
		.find((b) => b.textContent.trim() === (name ? "Save" : "Create"))
		.click();
	await until(() =>
		transport.calls.some(
			([method]) => method.startsWith("frappe.client.") && method !== "frappe.client.get"
		)
	);
	return transport.calls.find(([method]) =>
		["frappe.client.insert", "frappe.client.save"].includes(method)
	)[1].doc;
}

test("an untouched JSON field is saved as no value, not an empty string", async (t) => {
	const sent = await saveSource(t, null, {
		"frappe.client.insert": ({ doc }) => ({ ...doc, name: "source-1" }),
	});
	assert.equal(sent.filters, null);
	assert.equal(sent.title, "ToDo");
});

test("a JSON field the user filled in is saved as written", async (t) => {
	const sent = await saveSource(t, "source-1", {
		"frappe.client.get": () => ({
			name: "source-1",
			title: "Old",
			filters: '{"status": "Open"}',
		}),
		"frappe.client.save": ({ doc }) => doc,
	});
	assert.equal(sent.filters, '{"status": "Open"}');
});
