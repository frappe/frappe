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
const { loadComponent, toast, transport } = await import("./helpers/components.js");
const DocPanel = await loadComponent("settings/DocPanel.vue");
const DocForm = await loadComponent("settings/DocForm.vue");
const FieldControl = await loadComponent("settings/FieldControl.vue");
const { SPECS, newDoc } = await import("../src/settings/specs.js");

const changes = [];
const renames = [];
const newRecords = new Set(); // the tabs asked to open on a blank record, each taken once
function mount(t, component, props, { can = () => true } = {}) {
	const el = document.createElement("div");
	document.body.append(el);
	const app = createApp(component, props);
	app.provide("flowPage", {
		can,
		changed: (doctype) => changes.push(doctype),
		renamed: (...args) => renames.push(args),
		takeNewRecord: (key) => newRecords.delete(key),
		state: { boot: {} },
	});
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

test("settings load and search beyond the first 200 records, keeping the rows shown until a search's arrive", async (t) => {
	const records = Array.from({ length: 401 }, (_, i) => ({
		name: `tool-${i}`,
		title: `Tool ${i}`,
	}));
	let finish;
	transport.answers["frappe.client.get_list"] = (args) => {
		const query = args.or_filters?.[0]?.[2]?.slice(1, -1);
		const rows = query ? records.filter((row) => row.title.includes(query)) : records;
		const page = rows.slice(args.limit_start, args.limit_start + args.limit_page_length);
		return query ? new Promise((resolve) => (finish = () => resolve(page))) : page;
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
	await until(() => finish);
	assert.equal(el.querySelectorAll("li").length, 401);
	finish();
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

test("saving keeps the form open; deleting goes back to the list, without the record before it reloads; asked for from outside settings, the page opens on a blank record once", async (t) => {
	transport.answers["frappe.client.get_list"] = () => [
		{ name: "tool-1", title: "Tool 1" },
		{ name: "tool-2", title: "Tool 2" },
	];
	const el = mount(t, DocPanel, { spec });
	await until(() => el.querySelectorAll("li").length === 2);
	[...el.querySelectorAll("button")].find((b) => b.textContent === "New tool").click();
	await nextTick();
	// the form is a stub here, so emit its events for it
	const form = () => el.querySelector("[data-stub=DocForm]");
	form().__vueParentComponent.emit("saved", { name: "tool-2", title: "Tool 2" });
	await nextTick();
	assert.equal(form().getAttribute("name"), "tool-2");
	assert.equal(form().getAttribute("title"), "Edit tool");
	transport.answers["frappe.client.get_list"] = () => new Promise(() => {});
	form().__vueParentComponent.emit("deleted");
	await nextTick();
	assert.equal(form(), null);
	assert.deepEqual(
		[...el.querySelectorAll("li")].map((li) => li.textContent.trim()),
		["Tool 1"]
	);

	newRecords.add("tools");
	const asked = mount(t, DocPanel, { spec: { ...spec, key: "tools" } });
	assert.equal(asked.querySelector("[data-stub=DocForm]").getAttribute("title"), "New tool");
	const again = mount(t, DocPanel, { spec: { ...spec, key: "tools" } });
	assert.equal(again.querySelector("[data-stub=DocForm]"), null);
});

test("link and multilink search the server, keeping their options while it loads and the selection always", async (t) => {
	for (const typeName of ["link", "multilink"]) {
		transport.calls.length = 0;
		let finish;
		transport.answers["frappe.desk.search.search_link"] = ({ txt }) =>
			txt ? new Promise((resolve) => (finish = resolve)) : [{ value: "tool-1" }];
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
		await until(() => finish);
		assert.ok(el.textContent.includes("tool-1"), typeName);
		finish([{ value: "tool-900", label: "A later tool" }]);
		await until(() => el.textContent.includes("A later tool"));
		assert.ok(!el.textContent.includes("tool-1"), typeName);
		assert.ok(el.textContent.includes("selected"), typeName);
		assert.equal(transport.calls.at(-1)[1].txt, "later");
		assert.equal(transport.calls.at(-1)[1].reference_doctype, "Flow Agent");
	}
	// with nothing picked, only the server's options show
	const empty = mount(t, FieldControl, {
		field: { name: "tools", type: "link", label: "Tools", link: "Flow Tool" },
		doc: { doctype: "Flow Agent", tools: "" },
	});
	await until(() => empty.querySelector("button"));
	assert.deepEqual(
		[...empty.querySelectorAll("button")].map((b) => b.textContent),
		["tool-1"]
	);
});

test("a read-only multilink still opens, showing only its picks and nothing to change, by name where its records can't be read", async (t) => {
	transport.answers["frappe.desk.search.search_link"] = () => [
		{ value: "tool-1", label: "Tool One" },
		{ value: "tool-2", label: "Tool Two" },
	];
	const props = {
		field: { name: "tools", type: "multilink", label: "Tools", link: "Flow Tool" },
		doc: { doctype: "Flow Agent", tools: ["selected", "tool-1"] },
		disabled: true,
	};
	const el = mount(t, FieldControl, props);
	await until(() => el.textContent.includes("Tool One"));
	const control = el.querySelector("[data-control=Tools]").__vueParentComponent;
	assert.equal(control.attrs.disabled, undefined);
	assert.deepEqual(control.props.options, [
		{ value: "selected", label: "selected", disabled: true },
		{ value: "tool-1", label: "Tool One", disabled: true },
	]);
	// an empty footer in place of Clear All / Select All
	assert.ok(control.slots.footer);

	// a Flow User may not search tools: the names show, with no search to refuse and no spinner
	transport.calls.length = 0;
	const names = mount(t, FieldControl, props, { can: () => false });
	await new Promise((resolve) => setTimeout(resolve, 350)); // past the search's debounce
	const shown = names.querySelector("[data-control=Tools]").__vueParentComponent;
	assert.deepEqual(transport.calls, []);
	assert.equal(shown.props.loading, false);
	assert.deepEqual(
		shown.props.options.map((option) => option.label),
		["selected", "tool-1"]
	);
});

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

test("a provider's models show without its prefix, a late answer for another is dropped, and a typed id stays when none come", async (t) => {
	const field = SPECS.models.fields.find((f) => f.name === "model_id");
	const pending = {};
	transport.answers["frappe.flow.doctype.flow_model.flow_model.get_provider_models"] = ({
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

	// an id typed while the list loads stays when no list comes back
	doc.provider = "litellm_proxy";
	await until(() => pending.litellm_proxy);
	type(el, "acme/model-x");
	pending.litellm_proxy([]);
	await until(() => doc.model_id === "acme/model-x");
	await nextTick();
	assert.equal(el.querySelector("input").value, "acme/model-x");
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

test("an untouched JSON field is saved as no value and a filled one as written; the toast says Created or Saved", async (t) => {
	toast.shown.length = 0;
	const created = await saveSource(t, null, {
		"frappe.client.insert": ({ doc }) => ({ ...doc, name: "source-1" }),
	});
	assert.equal(created.filters, null);
	assert.equal(created.title, "ToDo");
	await until(() => toast.shown.length === 1);
	const saved = await saveSource(t, "source-1", {
		"frappe.client.get": () => ({
			name: "source-1",
			title: "Old",
			filters: '{"status": "Open"}',
		}),
		"frappe.client.save": ({ doc }) => doc,
	});
	assert.equal(saved.filters, '{"status": "Open"}');
	await until(() => toast.shown.length === 2);
	assert.deepEqual(toast.shown, ["Created", "Saved"]);
});

test("a new record leaves read-only fields out, so the server fills their defaults", () => {
	assert.equal("source" in newDoc(SPECS.memories), false);
	assert.equal("status" in newDoc(SPECS.knowledge_sources), false);
});

const agentSpec = {
	doctype: "Flow Agent",
	label: "Agents",
	singular: "agent",
	titleField: "title",
	listFields: ["name", "title"],
	fields: [
		{ name: "title", label: "Title", type: "text", rename: true },
		{ name: "description", label: "Description", type: "text" },
	],
};

// opens the agent "Helper" (or a new one), types the edits and presses the button
const saves = [];
async function editAgent(t, name, edits, answers = {}) {
	transport.calls.length = 0;
	changes.length = 0;
	renames.length = 0;
	saves.length = 0;
	toast.shown.length = 0;
	Object.assign(transport.answers, {
		"frappe.client.get": (args) => ({ name: args.name, title: args.name, description: "Old" }),
		"frappe.client.insert": ({ doc }) => ({ ...doc, name: doc.title }),
		"frappe.client.save": ({ doc }) => doc,
		"frappe.client.rename_doc": ({ new_name }) => new_name,
		...answers,
	});
	const el = mount(t, DocForm, { spec: agentSpec, name, onSaved: (doc) => saves.push(doc) });
	await until(() => el.querySelector("input"));
	for (const [label, value] of Object.entries(edits))
		type(el.querySelector(`[data-control="${label}"]`), value);
	await nextTick();
	[...el.querySelectorAll("button")]
		.find((b) => b.textContent.trim() === (name ? "Save" : "Create"))
		.click();
	return el;
}
const methods = () => transport.calls.map(([method]) => method);

test("a saved record's changed title renames it, after saving its other edits; a new record's is only inserted", async (t) => {
	await editAgent(t, null, { Title: "Helper" });
	await until(() => toast.shown.length);
	assert.deepEqual(methods(), ["frappe.client.insert"]);
	assert.deepEqual(toast.shown, ["Created"]);

	const calls = (method) => transport.calls.filter(([name]) => name === method);
	for (const [edits, first] of [
		[{ Title: " Support Helper " }, []],
		[{ Title: "Support Helper", Description: "New" }, ["frappe.client.save"]],
	]) {
		const el = await editAgent(t, "Helper", edits);
		await until(() => toast.shown.length);
		assert.deepEqual(methods(), [
			"frappe.client.get",
			...first,
			"frappe.client.rename_doc",
			"frappe.client.get",
		]);
		// the other edits save under the current name
		for (const [, { doc }] of calls("frappe.client.save"))
			assert.deepEqual([doc.title, doc.description], ["Helper", "New"]);
		assert.deepEqual(calls("frappe.client.rename_doc")[0][1], {
			doctype: "Flow Agent",
			old_name: "Helper",
			new_name: "Support Helper",
		});
		assert.equal(transport.calls.at(-1)[1].name, "Support Helper");
		assert.deepEqual(renames, [["Flow Agent", "Helper", "Support Helper"]]);
		assert.deepEqual(toast.shown, ["Renamed"]);
		assert.equal(el.querySelector('[data-control="Title"] input').value, "Support Helper");
	}
});

test("a refused rename keeps the typed title and says why; edits saved before it still reach the list and the page", async (t) => {
	const el = await editAgent(
		t,
		"Helper",
		{ Title: "Support", Description: "New" },
		{
			"frappe.client.rename_doc": () => {
				throw new Error("Another Flow Agent with name Support exists");
			},
		}
	);
	await until(() => el.textContent.includes("Another Flow Agent with name Support exists"));
	assert.equal(el.querySelector('[data-control="Title"] input').value, "Support");
	assert.deepEqual(renames, []);
	assert.deepEqual(toast.shown, []);
	assert.deepEqual(changes, ["Flow Agent"]);
	assert.deepEqual(
		saves.map((doc) => [doc.name, doc.description]),
		[["Helper", "New"]]
	);
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
