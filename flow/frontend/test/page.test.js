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
const ShareChat = await loadComponent("chat/ShareChat.vue");

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
const chatMenu = (el) => el.querySelector("header button[title='Chat options']");
const menuItems = (el) =>
	[...el.querySelectorAll("header [role=menuitem]")].map((item) => item.textContent);
async function until(check) {
	for (let attempt = 0; attempt < 100; attempt++) {
		if (check()) return;
		await new Promise((resolve) => setTimeout(resolve, 5));
	}
	throw new Error("timed out");
}

const ann = { name: "ann@example.com", full_name: "Ann", user_image: null };
const bob = { name: "bob@example.com", full_name: "Bob", user_image: null };
function mountPage(t, props = { boot }) {
	const el = document.createElement("div");
	document.body.append(el);
	const app = createApp(FlowPage, props).use(router);
	app.mount(el);
	t.after(() => {
		app.unmount();
		el.remove();
	});
	return el;
}

// the share dialog on its own, for chat S1 unless the test passes the chat's state
function shareDialog(t, client, { state, page = { boot } } = {}) {
	const el = document.createElement("div");
	document.body.append(el);
	const app = createApp(ShareChat).use(router);
	app.provide("flow", {
		state: state ?? reactive({ sessionId: "S1", session: { title: "Q3 plan" } }),
		client,
	});
	app.provide("flowPage", { state: page });
	const vm = app.mount(el);
	t.after(() => {
		app.unmount();
		el.remove();
	});
	return { el, vm };
}

test("the agent is picked in a palette, before the model, and a new chat starts with it", async (t) => {
	const el = mountPage(t);
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

test("boot is refetched only for the records it lists, and a renamed agent or model stays the one a new chat starts with", async () => {
	const { createPage } = await import("../src/page.js");
	let refreshes = 0;
	const models = [];
	const page = createPage(boot, {
		refresh: () => refreshes++,
		renamedModel: (...args) => models.push(args),
	});
	page.changed("Flow Skill");
	assert.equal(refreshes, 0);
	page.changed("Flow Model");
	page.changed("Flow Agent");
	assert.equal(refreshes, 2);

	page.renamed("Flow Agent", "someone-else", "Other");
	page.renamed("Flow Skill", "flow", "Other");
	assert.equal(page.state.agent, "flow");
	page.renamed("Flow Agent", "flow", "Support");
	assert.equal(page.state.agent, "Support");
	assert.deepEqual(models, []);
	page.renamed("Flow Model", "GPT", "GPT Fast");
	assert.deepEqual(models, [["GPT", "GPT Fast"]]);
});

test("without a model the normal page shows the setup state and a disabled composer", async (t) => {
	const el = mountPage(t, { boot: { ...boot, models: [] } });
	await until(() => called("flow.api.list_sessions"));
	await nextTick();
	assert.ok(el.querySelector("[data-stub=SetupState]"));
	assert.ok(!el.textContent.includes("What can I help you with?"));
	assert.ok(el.querySelector("textarea").matches(":disabled"));
	assert.ok(el.querySelector("button[title='Agent']").matches(":disabled"));
});

test("an explicit conversation URL opens even outside the recent session list, syncing a run that ended as it opened", async (t) => {
	await router.replace("/s/older");
	transport.calls.length = 0;
	const saved = { ...transport.answers };
	t.after(() => Object.assign(transport.answers, saved));
	const runs = (status) => ({ ...session, name: "older", runs: [{ name: "R1", status }] });
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
	mountPage(t);
	await until(
		() => called("flow.api.sync_session") || router.currentRoute.value.path !== "/s/older"
	);
	assert.equal(args("flow.api.session").session, "older");
	assert.equal(router.currentRoute.value.path, "/s/older");
	assert.deepEqual(args("flow.api.sync_session"), { session: "older" });
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
	const el = mountPage(t);
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

test("a chat the user may only view shows no composer or menu, and only the owner's menu offers Share", async (t) => {
	transport.calls.length = 0;
	const chats = {
		theirs: { owner: "owner@example.com", owner_name: "Olive Owner", read_only: true },
		admins: { title: "Ann's chat", owner: "owner@example.com" },
		S1: { title: "Q3 plan" },
	};
	Object.assign(transport.answers, {
		"flow.api.session": ({ session: name }) => ({ ...session, name, ...chats[name] }),
		"flow.api.list_shares": [],
		"flow.api.find_users": [],
	});
	t.after(() => {
		transport.answers["flow.api.session"] = session;
		delete transport.answers["flow.api.list_shares"];
		delete transport.answers["flow.api.find_users"];
	});
	const header = (el) => el.querySelector("header")?.textContent ?? "";
	await router.replace("/s/theirs");
	const el = mountPage(t);
	// a viewer is told whose chat it is
	await until(() => el.textContent.includes("Only Olive Owner can send messages in this chat."));
	assert.equal(el.querySelector("textarea"), null);
	assert.equal(chatMenu(el), null, "nor a menu to share, rename or delete it");

	// someone else's chat offers no Share, even to a user who may write to it
	await router.replace("/s/admins");
	await until(() => header(el).includes("Ann's chat"));
	assert.ok(el.querySelector("textarea"));
	chatMenu(el).click();
	await nextTick();
	assert.deepEqual(menuItems(el), ["Rename", "Delete"]);
	chatMenu(el).click();

	// the owner's leads with Share, which opens the share dialog
	await router.replace("/s/S1");
	await until(() => header(el).includes("Q3 plan"));
	chatMenu(el).click();
	await nextTick();
	assert.deepEqual(menuItems(el), ["Share", "Rename", "Delete"]);
	[...el.querySelectorAll("header [role=menuitem]")][0].click();
	await until(() => el.querySelector("[role=dialog]"));
	assert.deepEqual(args("flow.api.list_shares"), { session: "S1" });
});

test("the share dialog opens with its members in, lists the owner and who may view, adds people found and removes them", async (t) => {
	const calls = [];
	let viewers = [ann];
	let listed;
	const { el, vm } = shareDialog(t, {
		shares(sid) {
			calls.push(["shares", sid]);
			return new Promise((resolve) => (listed = () => resolve(viewers)));
		},
		async findUsers(query) {
			calls.push(["find", query]);
			return [{ name: "tester@example.com", full_name: "Tester" }, ann, bob];
		},
		async share(sid, user) {
			calls.push(["share", sid, user]);
			return (viewers = [...viewers, bob]);
		},
		async unshare(sid, user) {
			calls.push(["unshare", sid, user]);
			return (viewers = viewers.filter((viewer) => viewer.name !== user));
		},
	});
	assert.equal(el.querySelector("[role=dialog]"), null);

	// it opens once its members are in, so it keeps its size
	vm.show();
	await nextTick();
	assert.equal(el.querySelector("[role=dialog]"), null, "not before its members are in");
	listed();
	await until(() => el.textContent.includes("ann@example.com"));
	assert.equal(
		el.querySelector("[role=dialog]").getAttribute("aria-label"),
		'Sharing "Q3 plan"'
	);
	// the owner leads the list and stays; each person added has a remove (×) button
	const row = (who) => [...el.querySelectorAll("li")].find((li) => li.textContent.includes(who));
	assert.equal(el.querySelectorAll("li").length, 2, "the owner and Ann, no loading row");
	assert.ok(row("tester@example.com").textContent.includes("Owner (you)"));
	assert.equal(row("tester@example.com").querySelector("button"), null);
	assert.equal(row("ann@example.com").querySelector("button").title, "Remove Ann's access");
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

	for (const who of ["ann@example.com", "bob@example.com"]) {
		row(who).querySelector("button").click();
		await until(() => !el.textContent.includes(who));
	}
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

	// a list that doesn't come opens the dialog after a moment, saying it is loading
	const slow = shareDialog(t, {
		shares: () => new Promise(() => {}),
		findUsers: async () => [],
	});
	slow.vm.show();
	await until(() => slow.el.querySelector("[role=dialog]"));
	assert.ok(slow.el.textContent.includes("Loading…"));
});

test("the share dialog acts only on the chat it opened for, and a late list never undoes a newer one", async (t) => {
	const lists = [];
	const shared = [];
	const state = reactive({ sessionId: "S1", session: { title: "Q3 plan" } });
	const { el, vm } = shareDialog(
		t,
		{
			shares: () => new Promise((resolve) => lists.push(resolve)),
			findUsers: async () => [bob],
			share: async (sid, user) => {
				shared.push([sid, user]);
				return [ann, bob];
			},
		},
		{ state }
	);
	const dialog = () => el.querySelector("[role=dialog]");

	// another chat opening closes the dialog
	vm.show();
	await until(dialog);
	state.sessionId = "S2";
	await nextTick();
	assert.equal(dialog(), null, "it closes with its chat");

	// reopened there, the first chat's late list stays out, and adding asks for this chat
	vm.show();
	lists[0]([{ name: "carol@example.com", full_name: "Carol", user_image: null }]);
	await until(() => el.querySelector("[data-control=combobox] button"));
	assert.ok(!el.textContent.includes("carol@example.com"), "not the other chat's list");
	el.querySelector("[data-control=combobox] button").click();
	await until(() => el.textContent.includes("bob@example.com"));
	assert.deepEqual(shared, [["S2", "bob@example.com"]]);

	// this chat's own list, asked for before Bob was added, arrives last: Bob stays
	lists[1]([ann]);
	await new Promise((resolve) => setTimeout(resolve, 20));
	assert.ok(el.textContent.includes("bob@example.com"), "Bob stays");
});

test("the share dialog shows who else may view, and its owner opens the chat to every Flow user", async (t) => {
	const set = [];
	const state = reactive({ sessionId: "S1", session: { title: "Q3 plan" } });
	const pageState = reactive({ boot, generalAccess: { S1: "Restricted", S2: "Everyone" } });
	const { el, vm } = shareDialog(
		t,
		{
			shares: async () => [],
			findUsers: async () => [],
			// each reply waits for the test to send it
			setGeneralAccess: (sid, access) =>
				new Promise((resolve) => set.push([sid, access, () => resolve(access)])),
		},
		{ state, page: pageState }
	);
	vm.show();
	await until(() => el.querySelector("[role=dialog]"));
	const access = () => el.querySelector("[data-control=select]");
	const choices = () => [...access().querySelectorAll("button")];
	assert.equal(access().dataset.value, "Restricted");
	assert.deepEqual(
		choices().map((button) => button.textContent),
		["Only people you add", "Every Flow user"]
	);
	choices()[1].click();
	set[0][2]();
	await until(() => access().dataset.value === "Everyone");

	// a reply that comes back after another chat's dialog opened changes only its own chat
	choices()[0].click();
	state.sessionId = "S2";
	await nextTick();
	vm.show();
	await until(() => el.querySelector("[role=dialog]"));
	set[1][2]();
	await new Promise((resolve) => setTimeout(resolve, 20));
	assert.deepEqual(
		set.map(([sid, value]) => [sid, value]),
		[
			["S1", "Everyone"],
			["S1", "Restricted"],
		]
	);
	assert.deepEqual(pageState.generalAccess, { S1: "Restricted", S2: "Everyone" });
	assert.equal(access().dataset.value, "Everyone");
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

test("a loading chat shows the agent and model of its sidebar row, and names none opened from a link", async (t) => {
	await router.replace("/");
	const pending = [];
	transport.answers["flow.api.list_sessions"] = [
		{
			name: "listed",
			title: "Listed chat",
			agent: "reviewer",
			model: "Sonnet",
			modified: "2026-10-09",
		},
	];
	transport.answers["flow.api.session"] = ({ session: name }) =>
		new Promise((resolve) => pending.push(() => resolve({ ...session, name })));
	t.after(() => {
		transport.answers["flow.api.list_sessions"] = [];
		transport.answers["flow.api.session"] = session;
	});
	const el = mountPage(t);
	const agent = () => el.querySelector("button[title^='The agent is fixed']");
	await until(() => el.textContent.includes("Listed chat"));
	[...el.querySelectorAll("[role=button]")]
		.find((row) => row.textContent.includes("Listed chat"))
		.click();
	await until(() => pending.length === 1);
	await nextTick();
	assert.equal(agent().textContent.trim(), "Reviewer");
	assert.ok(el.querySelector("button[title^='Sonnet']"));
	pending[0]();

	// opened from its link, a chat outside the list names neither until it loads
	await router.replace("/s/slow");
	await until(() => pending.length === 2);
	await nextTick();
	assert.equal(agent().textContent.trim(), "");
	assert.ok(!el.textContent.includes("Choose Model"));
	pending[1]();
	await until(() => agent().textContent.trim() === "Reviewer");
	assert.ok(el.textContent.includes("Sonnet"));
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
	const el = mountPage(t);
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
