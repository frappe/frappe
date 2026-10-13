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
const { createApp, nextTick, reactive } = await import("vue");
const { loadComponent, transport } = await import("./helpers/components.js");
const DocPanel = await loadComponent("settings/DocPanel.vue");
const DocForm = await loadComponent("settings/DocForm.vue");
const FieldControl = await loadComponent("settings/FieldControl.vue");
const { SPECS } = await import("../src/settings/specs.js");

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

test("a settings search keeps what is shown until its results arrive", async (t) => {
	const pending = [];
	transport.answers["frappe.client.get_list"] = ({ or_filters }) =>
		or_filters.length
			? new Promise((resolve) => pending.push(resolve))
			: [
					{ name: "tool-1", title: "Tool 1" },
					{ name: "tool-2", title: "Tool 2" },
			  ];
	const el = mount(t, DocPanel, { spec });
	await until(() => el.querySelectorAll("li").length === 2);
	type(el, "Tool 3");
	await until(() => pending.length === 1);
	assert.equal(el.querySelectorAll("li").length, 2);
	pending[0]([]);
	await until(() => el.textContent.includes("No tools yet."));
	type(el, "Tool 33");
	await until(() => pending.length === 2);
	assert.ok(el.textContent.includes("No tools yet."));
	assert.ok(!el.textContent.includes("Loading"));
});

test("a deleted record leaves the list before it reloads", async (t) => {
	transport.answers["frappe.client.get_list"] = () => [
		{ name: "tool-1", title: "Tool 1" },
		{ name: "tool-2", title: "Tool 2" },
	];
	const el = mount(t, DocPanel, { spec });
	await until(() => el.querySelectorAll("li").length === 2);
	el.querySelectorAll("li button")[1].click();
	await nextTick();
	transport.answers["frappe.client.get_list"] = () => new Promise(() => {});
	el.querySelector("[data-stub=DocForm]").__vueParentComponent.emit("deleted");
	await nextTick();
	assert.deepEqual(
		[...el.querySelectorAll("li")].map((li) => li.textContent.trim()),
		["Tool 1"]
	);
});

test("saving keeps the form open; deleting goes back to the list", async (t) => {
	transport.answers["frappe.client.get_list"] = () => [{ name: "tool-1", title: "Tool 1" }];
	const el = mount(t, DocPanel, { spec });
	await until(() => el.querySelector("li"));
	[...el.querySelectorAll("button")].find((b) => b.textContent === "New tool").click();
	await nextTick();
	// the form is a stub here, so emit its events for it
	const form = () => el.querySelector("[data-stub=DocForm]");
	form().__vueParentComponent.emit("saved", { name: "tool-2", title: "Tool 2" });
	await nextTick();
	assert.equal(form().getAttribute("name"), "tool-2");
	assert.equal(form().getAttribute("title"), "Edit tool");
	form().__vueParentComponent.emit("deleted");
	await until(() => el.querySelector("li"));
	assert.equal(form(), null);
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

	test(`${typeName} keeps its options while a new search loads`, async (t) => {
		let finish;
		transport.answers["frappe.desk.search.search_link"] = ({ txt }) =>
			txt ? new Promise((resolve) => (finish = resolve)) : [{ value: "tool-1" }];
		const el = mount(t, FieldControl, {
			field: { name: "tools", type: typeName, label: "Tools", link: "Flow Tool" },
			doc: { doctype: "Flow Agent", tools: typeName === "multilink" ? [] : "" },
		});
		await until(() => el.textContent.includes("tool-1"));
		type(el, "later");
		await until(() => finish);
		assert.ok(el.textContent.includes("tool-1"));
		finish([{ value: "tool-900", label: "A later tool" }]);
		await until(() => el.textContent.includes("A later tool"));
		assert.ok(!el.textContent.includes("tool-1"));
	});
}

test("a provider is picked from the list, and a saved one outside it still shows", (t) => {
	const field = SPECS.providers.fields.find((f) => f.name === "provider");
	const labels = (el) => [...el.querySelectorAll("button")].map((b) => b.textContent);
	const doc = { doctype: "Flow Provider", provider: "" };
	const el = mount(t, FieldControl, { field, doc });
	assert.ok(labels(el).includes("LiteLLM proxy"));
	[...el.querySelectorAll("button")].find((b) => b.textContent === "Anthropic").click();
	assert.equal(doc.provider, "anthropic");

	const saved = mount(t, FieldControl, {
		field,
		doc: { doctype: "Flow Provider", provider: "azure" },
	});
	assert.equal(labels(saved).at(-1), "azure");
});

test("a provider's models show without its prefix; a late answer for another is dropped", async (t) => {
	const field = SPECS.models.fields.find((f) => f.name === "model_id");
	const pending = {};
	transport.answers["flow.flow.doctype.flow_model.flow_model.get_provider_models"] = ({
		provider,
	}) => new Promise((resolve) => (pending[provider] = resolve));
	const doc = reactive({ doctype: "Flow Model", provider: "openrouter", model_id: "" });
	const el = mount(t, FieldControl, { field, doc });
	await until(() => pending.openrouter);
	doc.provider = "custom_openai";
	await until(() => pending.custom_openai);
	pending.custom_openai(["custom_openai/openai/gpt-6-sol"]);
	await until(() => el.textContent.includes("gpt-6-sol"));
	pending.openrouter(["openrouter/anthropic/claude-sonnet-4.6"]);
	await new Promise((resolve) => setImmediate(resolve));

	const options = [...el.querySelectorAll("button")];
	assert.deepEqual(
		options.map((b) => b.textContent),
		["openai/gpt-6-sol", "Use the typed id"]
	);
	options[0].click();
	assert.equal(doc.model_id, "custom_openai/openai/gpt-6-sol");
});

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

test("a settings list and an opened record show the spinner until they load", async (t) => {
	const saved = { ...transport.answers };
	t.after(() => Object.assign(transport.answers, saved));
	let list, record;
	transport.answers["frappe.client.get_list"] = () => new Promise((resolve) => (list = resolve));
	transport.answers["frappe.client.get"] = () => new Promise((resolve) => (record = resolve));

	const panel = mount(t, DocPanel, { spec });
	await until(() => list);
	assert.ok(panel.querySelector("[data-stub=Spinner]"));
	list([]);
	await until(() => !panel.querySelector("[data-stub=Spinner]"));

	const form = mount(t, DocForm, { spec: sourceSpec, name: "source-1" });
	await until(() => record);
	assert.ok(form.querySelector("[data-stub=Spinner]"));
	record({ name: "source-1", title: "Old" });
	await until(() => form.querySelector("input"));
	assert.equal(form.querySelector("[data-stub=Spinner]"), null);
});
