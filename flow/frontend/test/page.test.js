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
const { createApp, nextTick, reactive } = await import("vue");
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
	owner: "tester@example.com",
	owner_name: "Tester",
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
	transport.answers["flow.api.session"] = {
		...session,
		name: "theirs",
		owner: "owner@example.com",
		owner_name: "Olive Owner",
		read_only: true,
	};
	t.after(() => (transport.answers["flow.api.session"] = session));
	const el = document.createElement("div");
	document.body.append(el);
	const app = createApp(FlowPage, { boot }).use(router);
	app.mount(el);
	t.after(() => {
		app.unmount();
		el.remove();
	});
	// and says whose chat it is
	await until(() => el.textContent.includes("Only Olive Owner can send messages in this chat."));
	assert.equal(el.querySelector("textarea"), null);
	assert.equal(el.querySelector("[data-stub=ShareChat]"), null, "only its owner shares a chat");
});

test("a chat someone else owns offers no Share, even to a user who may write to it", async (t) => {
	await router.replace("/s/admins");
	transport.answers["flow.api.session"] = {
		...session,
		name: "admins",
		title: "Ann's chat",
		owner: "owner@example.com",
	};
	t.after(() => (transport.answers["flow.api.session"] = session));
	const el = document.createElement("div");
	document.body.append(el);
	const app = createApp(FlowPage, { boot }).use(router);
	app.mount(el);
	t.after(() => {
		app.unmount();
		el.remove();
	});
	// the title shows once the session has loaded, and with it who owns it
	await until(() => el.querySelector("header")?.textContent.includes("Ann's chat"));
	assert.ok(el.querySelector("textarea"));
	assert.equal(el.querySelector("[data-stub=ShareChat]"), null);
});

test("the owner's chat offers Share in its header", async (t) => {
	await router.replace("/s/S1");
	const el = document.createElement("div");
	document.body.append(el);
	const app = createApp(FlowPage, { boot }).use(router);
	app.mount(el);
	t.after(() => {
		app.unmount();
		el.remove();
	});
	await until(() => el.querySelector("header [data-stub=ShareChat]"));
});

test("the share dialog lists the owner and who may view, adds people found and takes a view back", async (t) => {
	const ShareChat = await loadComponent("chat/ShareChat.vue");
	const calls = [];
	let viewers = [{ name: "ann@example.com", full_name: "Ann", user_image: null }];
	const client = {
		async shares(sid) {
			calls.push(["shares", sid]);
			return viewers;
		},
		async findUsers(query) {
			calls.push(["find", query]);
			return [
				{ name: "tester@example.com", full_name: "Tester" },
				{ name: "ann@example.com", full_name: "Ann" },
				{ name: "bob@example.com", full_name: "Bob" },
			];
		},
		async share(sid, user) {
			calls.push(["share", sid, user]);
			return (viewers = [...viewers, { name: user, full_name: "Bob", user_image: null }]);
		},
		async unshare(sid, user) {
			calls.push(["unshare", sid, user]);
			return (viewers = viewers.filter((viewer) => viewer.name !== user));
		},
	};
	const el = document.createElement("div");
	document.body.append(el);
	const app = createApp(ShareChat).use(router);
	app.provide("flow", {
		state: reactive({ sessionId: "S1", session: { title: "Q3 plan" } }),
		client,
	});
	app.provide("flowPage", { state: { boot } });
	app.mount(el);
	t.after(() => {
		app.unmount();
		el.remove();
	});
	assert.equal(el.querySelector("[role=dialog]"), null);

	el.querySelector("button[title='Share this chat']").click();
	await until(() => el.textContent.includes("ann@example.com"));
	assert.equal(
		el.querySelector("[role=dialog]").getAttribute("aria-label"),
		'Sharing "Q3 plan"'
	);
	// the owner leads the list, and each person added may view
	const row = (who) => [...el.querySelectorAll("li")].find((li) => li.textContent.includes(who));
	assert.equal(el.querySelectorAll("li").length, 2);
	assert.ok(row("tester@example.com").textContent.includes("Owner (you)"));
	assert.ok(row("ann@example.com").textContent.includes("Can view"));
	// the link is the chat's own page, which opens only for the people it is shared with
	const copy = el.querySelector("[data-stub=CopyButton]");
	assert.equal(copy.getAttribute("text"), "http://localhost/flow/s/S1");
	assert.equal(copy.textContent.trim(), "Copy link");
	const input = el.querySelector("[data-control=combobox] input");
	input.value = "o";
	input.dispatchEvent(new Event("input"));
	await until(() => calls.some(([kind, query]) => kind === "find" && query === "o"));
	// the people found leave out the owner and whoever may view already
	const options = () =>
		[...el.querySelectorAll("[data-control=combobox] button")].map((b) => b.textContent);
	await until(() => options().length);
	assert.deepEqual(options(), ["Bob"]);
	el.querySelector("[data-control=combobox] button").click();
	await until(() => el.textContent.includes("bob@example.com"));
	assert.deepEqual(options(), []);

	const removeAccess = (who) =>
		[...row(who).querySelectorAll("button")]
			.find((button) => button.textContent === "Remove access")
			.click();
	removeAccess("ann@example.com");
	await until(() => !el.textContent.includes("ann@example.com"));
	removeAccess("bob@example.com");
	await until(() => !el.textContent.includes("bob@example.com"));
	assert.equal(el.querySelectorAll("li").length, 1, "the owner stays");
	assert.deepEqual(
		calls.filter(([kind]) => kind !== "find"),
		[
			["shares", "S1"],
			["share", "S1", "bob@example.com"],
			["unshare", "S1", "ann@example.com"],
			["unshare", "S1", "bob@example.com"],
		]
	);
});

test("the share dialog opens with its members in, so it keeps its size; a slow list opens it anyway", async (t) => {
	const ShareChat = await loadComponent("chat/ShareChat.vue");
	const share = (shares) => {
		const el = document.createElement("div");
		document.body.append(el);
		const app = createApp(ShareChat).use(router);
		app.provide("flow", {
			state: reactive({ sessionId: "S1", session: { title: "Q3 plan" } }),
			client: { shares, findUsers: async () => [] },
		});
		app.provide("flowPage", { state: { boot } });
		app.mount(el);
		t.after(() => {
			app.unmount();
			el.remove();
		});
		el.querySelector("button[title='Share this chat']").click();
		return el;
	};
	let answer;
	const el = share(() => new Promise((resolve) => (answer = resolve)));
	await nextTick();
	assert.equal(el.querySelector("[role=dialog]"), null, "not before its members are in");
	answer([{ name: "ann@example.com", full_name: "Ann", user_image: null }]);
	await until(() => el.querySelector("[role=dialog]"));
	assert.equal(el.querySelectorAll("li").length, 2, "the owner and Ann, no loading row");
	assert.ok(el.textContent.includes("ann@example.com"));

	// a list that doesn't come opens the dialog after a moment, saying it is loading
	const slow = share(() => new Promise(() => {}));
	await until(() => slow.querySelector("[role=dialog]"));
	assert.ok(slow.textContent.includes("Loading…"));
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

test("a chat opened from its link names no agent or model until it loads", async (t) => {
	await router.replace("/s/slow");
	let answer;
	transport.answers["flow.api.session"] = () => new Promise((resolve) => (answer = resolve));
	t.after(() => (transport.answers["flow.api.session"] = session));
	const el = document.createElement("div");
	document.body.append(el);
	const app = createApp(FlowPage, { boot }).use(router);
	app.mount(el);
	t.after(() => {
		app.unmount();
		el.remove();
	});
	await until(() => answer);
	await nextTick();
	const agent = el.querySelector("button[title^='The agent is fixed']");
	assert.equal(agent.textContent.trim(), "");
	assert.ok(!el.textContent.includes("Choose Model"));

	answer({ ...session, name: "slow" });
	await until(() => agent.textContent.trim() === "Reviewer");
	assert.ok(el.textContent.includes("Sonnet"));
});

test("a chat picked in the sidebar shows its agent and model before it loads", async (t) => {
	await router.replace("/");
	let answer;
	transport.answers["flow.api.list_sessions"] = [
		{
			name: "listed",
			title: "Listed chat",
			agent: "reviewer",
			model: "Sonnet",
			modified: "2026-10-09",
		},
	];
	transport.answers["flow.api.session"] = () => new Promise((resolve) => (answer = resolve));
	t.after(() => {
		transport.answers["flow.api.list_sessions"] = [];
		transport.answers["flow.api.session"] = session;
	});
	const el = document.createElement("div");
	document.body.append(el);
	const app = createApp(FlowPage, { boot }).use(router);
	app.mount(el);
	t.after(() => {
		app.unmount();
		el.remove();
	});
	await until(() => el.textContent.includes("Listed chat"));
	[...el.querySelectorAll("[role=button]")]
		.find((row) => row.textContent.includes("Listed chat"))
		.click();
	await until(() => answer);
	await nextTick();
	assert.equal(
		el.querySelector("button[title^='The agent is fixed']").textContent.trim(),
		"Reviewer"
	);
	assert.ok(el.querySelector("button[title^='Sonnet']"));
	answer({ ...session, name: "listed" });
});

test("a chat opened just as its run ended syncs that run", async (t) => {
	await router.replace("/s/ended");
	transport.calls.length = 0;
	const saved = { ...transport.answers };
	t.after(() => Object.assign(transport.answers, saved));
	const runs = (status) => ({ ...session, name: "ended", runs: [{ name: "R1", status }] });
	Object.assign(transport.answers, {
		"flow.api.session": runs("Running"),
		"flow.api.entries": {
			entries: [
				{ type: "run_started", seq: 1, run_id: "a" },
				{ type: "run_ended", seq: 2, reason: "done" },
			],
			latest_seq: 2,
			preview: [],
		},
		"flow.api.sync_session": runs("Completed"),
	});
	const el = document.createElement("div");
	document.body.append(el);
	const app = createApp(FlowPage, { boot }).use(router);
	app.mount(el);
	t.after(() => {
		app.unmount();
		el.remove();
	});
	await until(() => called("flow.api.sync_session"));
	assert.deepEqual(args("flow.api.sync_session"), { session: "ended" });
});

test("a first message sent while the chat list loads keeps the page on its new chat", async (t) => {
	await router.replace("/");
	transport.calls.length = 0;
	const saved = { ...transport.answers };
	t.after(() => Object.assign(transport.answers, saved));
	const prefs = "flow.page.tester@example.com.prefs";
	localStorage.setItem(prefs, JSON.stringify({ lastSession: "OLD" }));
	t.after(() => localStorage.removeItem(prefs));
	// the page's own first list call is slow; the new chat's refresh is not
	let listed;
	let first = true;
	transport.answers["flow.api.list_sessions"] = () => {
		if (!first) return [{ name: "OLD", title: "Old chat" }];
		first = false;
		return new Promise((resolve) => (listed = resolve));
	};
	let created;
	transport.answers["flow.api.create_session"] = () =>
		new Promise((resolve) => (created = resolve));
	const el = document.createElement("div");
	document.body.append(el);
	const app = createApp(FlowPage, { boot }).use(router);
	app.mount(el);
	t.after(() => {
		app.unmount();
		el.remove();
	});
	await until(() => called("flow.api.list_sessions"));

	const textarea = el.querySelector("textarea");
	textarea.value = "hi";
	textarea.dispatchEvent(new Event("input"));
	await nextTick();
	el.querySelector("button[title='Send']").click();
	// the list lands while the new chat is still being made
	await until(() => called("flow.api.create_session"));
	listed([{ name: "OLD", title: "Old chat" }]);
	await new Promise((resolve) => setTimeout(resolve, 30));
	created(session);
	await until(() => called("flow.api.run"));
	assert.equal(router.currentRoute.value.path, "/s/S1");
	assert.ok(
		!transport.calls.some(([name, a]) => name === "flow.api.session" && a.session === "OLD")
	);
});
