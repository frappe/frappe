import assert from "node:assert/strict";
import test from "node:test";

import { JSDOM } from "jsdom";

// Vue's DOM runtime captures document at import time.
const dom = new JSDOM("<body></body>", { url: "http://localhost/flow", pretendToBeVisual: true });
const globals = [
	"window",
	"document",
	"location",
	"history",
	"localStorage",
	"requestAnimationFrame",
	"cancelAnimationFrame",
];
const types = ["Document", "Element", "SVGElement", "HTMLElement", "Node", "Event"];
for (const name of [...globals, ...types]) {
	globalThis[name] = dom.window[name];
}
dom.window.HTMLElement.prototype.scrollIntoView = () => {};
// jsdom has no matchMedia: the page mounts at desktop width
dom.window.matchMedia = (query) => ({
	matches: query === "(min-width: 768px)",
	addEventListener() {},
});
const { createApp, nextTick } = await import("vue");
const { router } = await import("../src/router.js");
const { loadComponent, transport } = await import("./helpers/components.js");
const FlowPage = await loadComponent("chat/FlowPage.vue");

const boot = {
	csrf_token: "token",
	site_name: "flowtest",
	socketio_port: 9000,
	user: { name: "tester@example.com", full_name: "Tester" },
	permissions: {},
	models: [
		{
			name: "Sonnet",
			model_id: "anthropic/claude-sonnet-4-6",
			provider: "anthropic",
			context_window: 200000,
		},
	],
	agents: [
		{ name: "flow", title: "Flow" },
		{ name: "reviewer", title: "Reviewer" },
	],
	default_agent: "flow",
};
const session = {
	name: "S1",
	title: null,
	agent: "reviewer",
	model: "Sonnet",
	auto_approve: 0,
	runs: [],
};
Object.assign(transport.answers, {
	"flow.api.boot": boot,
	"flow.api.list_sessions": [],
	"flow.api.create_session": session,
	"flow.api.session": session,
	"flow.api.entries": { entries: [], latest_seq: 0, preview: [] },
	"flow.api.run": { status: "running" },
	"flow.api.skills": { skills: [] },
});

const called = (method) => transport.calls.some(([name]) => name === method);
const args = (method) => transport.calls.find(([name]) => name === method)[1];
async function until(check) {
	for (let attempt = 0; attempt < 100; attempt++) {
		if (check()) return;
		await new Promise((resolve) => setTimeout(resolve, 5));
	}
	throw new Error("timed out");
}

test("the agent is picked in a palette, before the model, and a new chat starts with it", async (t) => {
	const el = document.createElement("div");
	document.body.append(el);
	const app = createApp(FlowPage, { boot }).use(router);
	app.mount(el);
	t.after(() => {
		app.unmount();
		el.remove();
	});
	await until(() => called("flow.api.list_sessions"));
	await nextTick();
	assert.ok(!called("flow.api.boot"), "the page's own boot serves the first load");

	assert.ok(el.textContent.includes("What can I help you with?"));
	assert.equal(el.querySelector("textarea").placeholder, "Ask Flow…");
	const agent = el.querySelector("button[title='Agent']");
	const model = el.querySelector("button[title^='Choose Model']");
	assert.equal(agent.textContent.trim(), "Flow");
	assert.ok(agent.compareDocumentPosition(model) & Node.DOCUMENT_POSITION_FOLLOWING);
	assert.equal(
		agent.querySelector("[data-stub=FeatherIcon]"),
		null,
		"no chevron: it opens a panel"
	);

	// the /agents command and the button open the same palette above the composer
	const textarea = el.querySelector("textarea");
	textarea.value = "/agents";
	textarea.dispatchEvent(new Event("input"));
	await nextTick();
	const rows = () => [...el.querySelectorAll("[data-palette-item]")];
	assert.ok(rows()[0].textContent.includes("Agent"));
	rows()[0].click();
	await nextTick();
	assert.deepEqual(
		rows().map((row) => row.textContent.trim()),
		["Flow", "Reviewer"]
	);
	assert.equal(rows()[0].getAttribute("aria-current"), "true");
	rows()[1].click();
	await nextTick();
	assert.equal(rows().length, 0);
	assert.equal(agent.textContent.trim(), "Reviewer");
	// the skills a new chat may start follow the agent
	await until(() =>
		transport.calls.some(([name, a]) => name === "flow.api.skills" && a.agent === "reviewer")
	);
	agent.click();
	await nextTick();
	assert.equal(rows()[1].getAttribute("aria-current"), "true");
	rows()[1].click();
	await nextTick();

	textarea.value = "hi";
	textarea.dispatchEvent(new Event("input"));
	await nextTick();
	el.querySelector("button[title='Send']").click();
	await until(() => called("flow.api.run"));
	assert.equal(args("flow.api.create_session").agent, "reviewer");
	assert.deepEqual(args("flow.api.run"), { session: "S1", message: "hi", attachments: [] });
	await nextTick();
	assert.ok(agent.disabled, "the agent is fixed once the conversation starts");
	assert.equal(agent.textContent.trim(), "Reviewer");
});

test("boot is refetched only when a record it lists is saved or deleted", async () => {
	const { createPage } = await import("../src/page.js");
	let refreshes = 0;
	const page = createPage(boot, { refresh: () => refreshes++ });
	page.changed("Flow Skill");
	assert.equal(refreshes, 0);
	page.changed("Flow Model");
	page.changed("Flow Agent");
	assert.equal(refreshes, 2);
});

test("without a model the normal page shows the setup state and a disabled composer", async (t) => {
	const el = document.createElement("div");
	document.body.append(el);
	const app = createApp(FlowPage, { boot: { ...boot, models: [] } }).use(router);
	app.mount(el);
	t.after(() => {
		app.unmount();
		el.remove();
	});
	await until(() => called("flow.api.list_sessions"));
	await nextTick();
	assert.ok(el.querySelector("[data-stub=SetupState]"));
	assert.ok(!el.textContent.includes("What can I help you with?"));
	assert.ok(el.querySelector("textarea").matches(":disabled"));
	assert.ok(el.querySelector("button[title='Agent']").matches(":disabled"));
});

test("an explicit conversation URL opens even outside the recent session list", async (t) => {
	await router.replace("/s/older");
	transport.calls.length = 0;
	transport.answers["flow.api.session"] = { ...session, name: "older" };
	const el = document.createElement("div");
	document.body.append(el);
	const app = createApp(FlowPage, { boot }).use(router);
	app.mount(el);
	t.after(() => {
		app.unmount();
		el.remove();
	});
	await until(() => called("flow.api.session") || routeChanged());
	function routeChanged() {
		return router.currentRoute.value.path !== "/s/older";
	}
	assert.equal(called("flow.api.session"), true);
	assert.equal(args("flow.api.session").session, "older");
	assert.equal(router.currentRoute.value.path, "/s/older");
});

test("the chat list offers the next page on demand and asks for it past the last row", async (t) => {
	const page = Array.from({ length: 100 }, (_, i) => ({
		name: `P${i}`,
		title: `Chat ${i}`,
		agent: "reviewer",
		model: "Sonnet",
		modified: `t${100 - i}`,
	}));
	transport.answers["flow.api.list_sessions"] = (args) =>
		args.before ? [{ ...page[0], name: "OLD", title: "Older chat", modified: "t0" }] : page;
	t.after(() => (transport.answers["flow.api.list_sessions"] = []));
	const el = document.createElement("div");
	document.body.append(el);
	const app = createApp(FlowPage, { boot }).use(router);
	app.mount(el);
	t.after(() => {
		app.unmount();
		el.remove();
	});
	const loadMore = () =>
		[...el.querySelectorAll("button")].find((b) => b.textContent.trim() === "Load more");
	await until(() => loadMore());
	loadMore().click();
	await until(() => el.textContent.includes("Older chat"));
	const paged = transport.calls.filter(
		([name, a]) => name === "flow.api.list_sessions" && a.before
	);
	assert.deepEqual(
		paged.map(([, a]) => a.before),
		["t1"]
	);
	assert.equal(loadMore(), undefined, "a short page is the last");
});

test("a chat the user may only view shows no composer", async (t) => {
	await router.replace("/s/theirs");
	transport.answers["flow.api.session"] = { ...session, name: "theirs", read_only: true };
	t.after(() => (transport.answers["flow.api.session"] = session));
	const el = document.createElement("div");
	document.body.append(el);
	const app = createApp(FlowPage, { boot }).use(router);
	app.mount(el);
	t.after(() => {
		app.unmount();
		el.remove();
	});
	await until(() => el.textContent.includes("Only the owner of this chat can send messages."));
	assert.equal(el.querySelector("textarea"), null);
});

test("the thumbs show under a finished run, but not in a chat the user may only view", async (t) => {
	const FeedbackBar = await loadComponent("chat/FeedbackBar.vue");
	for (const [readOnly, buttons] of [
		[false, 2],
		[true, 0],
	]) {
		const el = document.createElement("div");
		document.body.append(el);
		const app = createApp(FeedbackBar, { turnKey: "turn:1" });
		app.provide("flow", { state: { sessionId: "S1" } });
		app.provide("flowPage", {
			state: { readOnly: { S1: readOnly } },
			runForTurn: () => ({ name: "R1", status: "Completed" }),
		});
		app.mount(el);
		t.after(() => {
			app.unmount();
			el.remove();
		});
		assert.equal(el.querySelectorAll("button").length, buttons);
	}
});
