import assert from "node:assert/strict";
import test from "node:test";

import { answerPageCall, readDeskState } from "../src/chat/pageCall.js";

// a stand-in for window.desk: every member but `version` answers with a Promise
const stubDesk = (over = {}) => ({
	version: 1,
	acts: {
		list: async () => [{ name: "header.save", description: "Save.", input: null, asks: [] }],
		run: async (name, value) => ({ ok: true, data: { name, value }, route: "/apps/todo", dialogs: [] }),
		wait: async (call, options) => ({ ok: true, data: { call, options }, route: "/", dialogs: [] }),
	},
	state: async () => ({ route: "/apps/todo", page: "list", dialogs: [] }),
	...over,
});

// runs one call and gives what the panel claimed and what it answered
async function callPage(message, page, { inPanel = true, claimed = true } = {}) {
	const seen = { claims: 0, replies: [] };
	await answerPageCall(message, {
		page,
		inPanel,
		claim: async () => (seen.claims++, claimed),
		reply: (answer) => seen.replies.push(answer),
		deskWait: 300,
		lateDelay: 10,
	});
	return seen;
}

test("list_acts answers with the page's acts and claims nothing", async () => {
	const seen = await callPage({ op: "list_acts", args: {} }, { desk: stubDesk() });
	assert.equal(seen.claims, 0);
	assert.deepEqual(seen.replies, [
		{ screen: { acts: [{ name: "header.save", description: "Save.", input: null, asks: [] }] } },
	]);
});

test("run_act claims the call first, then runs the act with its value", async () => {
	const order = [];
	const desk = stubDesk();
	desk.acts.run = async (name, value) => (order.push(["run", name, value]), { ok: true, data: null });
	const reply = [];
	await answerPageCall(
		{ op: "run_act", args: { name: "shell.open", args: { doctype: "ToDo" } } },
		{
			page: { desk },
			inPanel: true,
			claim: async () => (order.push("claim"), true),
			reply: (answer) => reply.push(answer),
			deskWait: 300,
			lateDelay: 10,
		}
	);
	assert.deepEqual(order, ["claim", ["run", "shell.open", { doctype: "ToDo" }]]);
	assert.deepEqual(reply, [{ screen: { ok: true, data: null } }]);
});

test("a run_act that another tab claimed first runs nothing and answers nothing", async () => {
	let ran = false;
	const desk = stubDesk();
	desk.acts.run = async () => (ran = true);
	const seen = await callPage(
		{ op: "run_act", args: { name: "header.save" } },
		{ desk },
		{ claimed: false }
	);
	assert.equal(ran, false);
	assert.deepEqual(seen.replies, []);
});

test("a waiting_for_user result goes back as it is, and a follow-up waits on its call", async () => {
	const error = { code: "waiting_for_user", call: 7, message: "A person must confirm." };
	const waiting = { ok: false, error };
	const desk = stubDesk();
	desk.acts.run = async () => waiting;
	const first = await callPage({ op: "run_act", args: { name: "header.submit" } }, { desk });
	assert.deepEqual(first.replies, [{ screen: waiting }]);
	const second = await callPage({ op: "run_act", args: { call: 7 } }, { desk });
	assert.equal(second.replies[0].screen.data.call, 7);
	assert.ok(second.replies[0].screen.data.options.timeout < 60000, "ends before the server stops waiting");
});

test("a page that throws answers with an error, not silence", async () => {
	const desk = stubDesk();
	desk.acts.list = async () => {
		throw new Error("boom");
	};
	const seen = await callPage({ op: "list_acts", args: {} }, { desk });
	assert.match(seen.replies[0].error, /boom/);
});

test("a page with no desk, a newer desk and a tab of its own each answer with an error", async () => {
	const none = await callPage({ op: "list_acts", args: {} }, {});
	assert.match(none.replies[0].error, /not a desk v2 page/);
	const newer = await callPage({ op: "list_acts", args: {} }, { desk: { version: 2 } });
	assert.match(newer.replies[0].error, /version 2/);
	const tab = await callPage({ op: "list_acts", args: {} }, { desk: stubDesk() }, { inPanel: false });
	assert.match(tab.replies[0].error, /tab of its own/);
});

test("an error from a tab that cannot drive waits for a claim, so a driving tab runs the act", async () => {
	const seen = await callPage({ op: "run_act", args: { name: "x" } }, {}, { claimed: false });
	assert.equal(seen.claims, 1);
	assert.deepEqual(seen.replies, []);
});

test("window.desk that appears after the call arrives is still used", async () => {
	const page = {};
	setTimeout(() => (page.desk = stubDesk()), 150);
	const seen = await callPage({ op: "list_acts", args: {} }, page);
	assert.ok(seen.replies[0].screen.acts);
});

test("read_screen's desk state is the page's state, or nothing without a desk", async () => {
	const state = { route: "/apps/todo", page: "list", dialogs: [] };
	assert.deepEqual(await readDeskState({ desk: stubDesk() }), state);
	assert.equal(await readDeskState({}), undefined);
	assert.equal(await readDeskState({ desk: { version: 2, state: async () => ({}) } }), undefined);
	const failing = stubDesk({ state: () => Promise.reject(new Error("x")) });
	assert.equal(await readDeskState({ desk: failing }), undefined);
	const hung = stubDesk({ state: () => new Promise(() => {}) });
	assert.equal(await readDeskState({ desk: hung }, 10), undefined);
});
