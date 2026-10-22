import assert from "node:assert/strict";
import test from "node:test";

import { FrappeClient } from "../src/api/client.js";

function fakeTransport(answers = {}) {
	const calls = [];
	return {
		calls,
		async call(method, args) {
			calls.push([method, args]);
			const answer = answers[method];
			return typeof answer === "function" ? answer(args) : answer;
		},
		async uploadFile(file) {
			calls.push(["upload", file.name]);
			return { name: `FILE-${file.name}` };
		},
		async deleteFile(name) {
			calls.push(["delete", name]);
		},
	};
}

const boot = {
	models: [
		{
			name: "Sonnet",
			model_id: "anthropic/claude-sonnet-4-6",
			provider: "anthropic",
			context_window: 200000,
		},
	],
};
const session = {
	name: "S1",
	title: "Hello",
	agent: "Flow",
	model: "Sonnet",
	source: "Manual",
	auto_approve: false,
	runs: [],
};

test("a new chat is created with the page's agent and an offered model, and reported back", async () => {
	const reported = [];
	const transport = fakeTransport({
		"frappe.flow.api.create_session": { ...session, auto_approve: true },
	});
	const client = new FrappeClient({
		boot,
		transport,
		hooks: { agent: () => "Support", onSession: (d) => reported.push(d.name) },
	});
	const created = await client.createSession({ model: "Sonnet", auto_approve: true });
	assert.deepEqual(transport.calls[0], [
		"frappe.flow.api.create_session",
		{ agent: "Support", model: "Sonnet", auto_approve: 1 },
	]);
	assert.equal(created.session_id, "S1");
	assert.equal(created.config.auto_approve, true);
	assert.equal(created.config.model, "Sonnet");
	assert.deepEqual(reported, ["S1"]);
	// a remembered model the site no longer offers is left out, and the server picks
	await new FrappeClient({ boot, transport }).createSession({ model: "Retired" });
	assert.deepEqual(transport.calls[1][1], { agent: null, model: null, auto_approve: 0 });
});

test("session details carry the model's context window, a view-only flag and a config the store can patch", async () => {
	const transport = fakeTransport({
		"frappe.flow.api.session": ({ session: name }) => ({
			...session,
			name,
			read_only: name === "S2",
		}),
		"frappe.flow.api.set_title": { title: "Renamed" },
		"frappe.flow.api.set_auto_approve": { auto_approve: true },
	});
	const client = new FrappeClient({ boot, transport });
	const info = await client.session("S1");
	assert.equal(info.context_window, 200000);
	assert.equal(info.read_only, false);
	assert.equal((await client.session("S2")).read_only, true);
	assert.equal(info.config.auto_approve, false);
	const renamed = await client.patchConfig("S1", { title: "Renamed" });
	assert.equal(renamed.config.title, "Renamed");
	const approved = await client.patchConfig("S1", { auto_approve: true });
	assert.deepEqual(approved.config, {
		auto_approve: true,
		title: "Renamed",
		agent: "Flow",
		model: "Sonnet",
		cwd: null,
	});
	assert.deepEqual(transport.calls.at(-1), [
		"frappe.flow.api.set_auto_approve",
		{ session: "S1", auto_approve: 1 },
	]);
});

test("the log is presented and mirrored to the page, replaced by a snapshot and appended by a catch-up", async () => {
	const mirrored = [];
	const transport = fakeTransport({
		"frappe.flow.api.entries": ({ since, path }) => ({
			entries: [
				{ type: "run_started", seq: since + 1, run_id: "r" },
				{ type: "model_changed", seq: since + 2, model: "anthropic/claude-sonnet-4-6" },
			],
			latest_seq: since + 2,
			path,
		}),
	});
	const client = new FrappeClient({
		boot,
		transport,
		hooks: { onRows: (sid, rows, opts) => mirrored.push([sid, rows.length, opts.replace]) },
	});
	const seed = await client.entries("S1");
	assert.equal(seed.entries[1].model, "Sonnet");
	const more = await client.entries("S1", 2, "all");
	assert.equal(more.entries[0].seq, 3);
	assert.deepEqual(mirrored, [
		["S1", 2, true],
		["S1", 2, false],
	]);
	assert.deepEqual(transport.calls[1], [
		"frappe.flow.api.entries",
		{ session: "S1", since: 2, path: "all" },
	]);
});

test("attachments are staged as private Files for the picked model, discarded if staging fails, and cleaned up by File name", async () => {
	const transport = fakeTransport({
		"frappe.flow.api.attach_file": ({ file }) => {
			if (file === "FILE-broken.pdf") throw new Error("Cannot extract");
			return { file, file_name: file.replace("FILE-", ""), file_size: 1 };
		},
	});
	const client = new FrappeClient({ boot, transport });
	const { attachments } = await client.uploadAttachments("S1", [
		{ name: "shot.png" },
		{ name: "notes.txt" },
	]);
	assert.deepEqual(attachments, [
		{ id: "FILE-shot.png", name: "shot.png", kind: "image" },
		{ id: "FILE-notes.txt", name: "notes.txt", kind: "file" },
	]);
	// a later durable row for notes.txt is keyed by the File it was staged as
	const presented = client.present({
		type: "user_message",
		content: 'Read\n<file name="notes.txt">\nx\n</file>',
	});
	assert.equal(presented.content[1].id, "FILE-notes.txt");
	await client.cleanupAttachments("S1", ["FILE-shot.png"]);
	assert.deepEqual(transport.calls.at(-1), [
		"frappe.flow.api.cleanup_attachments",
		{ session: "S1", attachments: ["FILE-shot.png"] },
	]);
	// staging tells the server which model the picker holds
	await client.prepareAttachment({ name: "shot.png" }, "GPT");
	assert.deepEqual(transport.calls.at(-1), [
		"frappe.flow.api.attach_file",
		{ file: "FILE-shot.png", model: "GPT" },
	]);
	// a failure discards the upload without creating a session
	await assert.rejects(client.prepareAttachment({ name: "broken.pdf" }), /Cannot extract/);
	assert.deepEqual(transport.calls.at(-1), [
		"frappe.flow.api.cleanup_attachments",
		{ attachments: ["FILE-broken.pdf"] },
	]);
});

test("the model list comes from the page's boot first, then refreshes from the server", async () => {
	const transport = fakeTransport({
		"frappe.flow.api.boot": {
			models: [
				{
					name: "GPT",
					title: "GPT",
					model_id: "openai/gpt-4o",
					provider: null,
					context_window: 0,
				},
			],
		},
		"frappe.flow.api.set_model": ({ model }) => ({
			model,
			reasoning_effort: "high",
		}),
	});
	const client = new FrappeClient({ boot, transport });
	assert.deepEqual(
		(await client.models()).models.map((m) => m.name),
		["Sonnet"]
	);
	assert.deepEqual(transport.calls, []);
	const { models } = await client.models();
	assert.deepEqual(models, [
		{
			name: "GPT",
			display_name: "GPT",
			provider: "openai",
			model_id: "openai/gpt-4o",
			context_window: null,
		},
	]);
	const switched = await client.setModel("S1", { model: "GPT", reasoning_effort: "high" });
	assert.deepEqual(switched, { model: "GPT", context_window: null });
	assert.deepEqual(transport.calls.at(-1), [
		"frappe.flow.api.set_model",
		{ session: "S1", model: "GPT", reasoning_effort: "high" },
	]);
});

test("shared provider IDs preserve the session's model when its thinking level changes", async (t) => {
	const { createFlowStore } = await import("@flow/ui-core/store.js");
	const { fakeSocket } = await import("./helpers/socket.js");
	globalThis.localStorage = { getItem: () => null, setItem() {} };
	const models = [boot.models[0], { ...boot.models[0], name: "Other account" }];
	const transport = fakeTransport({
		"frappe.flow.api.session": session,
		"frappe.flow.api.entries": ({ path }) => ({
			entries:
				path === "active"
					? [{ type: "model_changed", seq: 1, model: models[0].model_id }]
					: [],
			latest_seq: 1,
		}),
		"frappe.flow.api.set_model": ({ model }) => ({ model }),
	});
	const client = new FrappeClient({ socket: fakeSocket(), boot: { models }, transport });
	const store = createFlowStore(client, { requireCwd: false, skillsEnabled: false });
	t.after(() => store.detach());
	await store.openSession("S1");
	assert.equal(store.state.conversation.model, "Sonnet");
	await store.selectEffort("high");
	assert.equal(
		transport.calls.find(([method]) => method === "frappe.flow.api.set_model")[1].model,
		"Sonnet"
	);
	await client.setModel("S1", { model: "Other account" });
	assert.equal(
		client.present({ type: "model_changed", model: models[0].model_id }, "S1").model,
		"Other account"
	);
});

test("a steered image's bubble goes when its daemon attachment arrives", async (t) => {
	const { createFlowStore } = await import("@flow/ui-core/store.js");
	const { fakeSocket } = await import("./helpers/socket.js");
	globalThis.localStorage = { getItem: () => null, setItem() {} };
	const socket = fakeSocket();
	const transport = fakeTransport({
		"frappe.flow.api.session": session,
		"frappe.flow.api.entries": { entries: [], latest_seq: 0 },
		"frappe.flow.api.attach_file": ({ file }) => ({ file, file_name: "shot.png" }),
		"frappe.flow.api.run": { status: "steered" },
	});
	const client = new FrappeClient({ socket, boot, transport });
	const store = createFlowStore(client, { requireCwd: false, skillsEnabled: false });
	t.after(() => store.detach());
	await store.openSession("S1");
	await store.send("Look", [{ file: { name: "shot.png" } }]);
	assert.equal(store.state.conversation.steering.length, 1);
	socket.fire("flow:event", {
		type: "user_message",
		session_id: "S1",
		seq: 1,
		content: [
			{ type: "text", text: "Look" },
			{ type: "attachment", id: "daemon-id", name: "shot.png", kind: "image" },
		],
	});
	await new Promise((resolve) => setImmediate(resolve));
	assert.equal(store.state.conversation.steering.length, 0);
});

test("each call reaches its frappe.flow.api endpoint and answers with the server's reply", async () => {
	const ann = "ann@example.com";
	const cases = [
		// skills come from the session's agent, or the page's agent before a chat starts
		[(c) => c.skills("S1"), "frappe.flow.api.skills", { session: "S1" }],
		[(c) => c.previewSkills({}), "frappe.flow.api.skills", { agent: "Support" }],
		// a resume names the batch it answers, so a sub-agent's can be told apart
		[
			(c) => c.resume("S1", 8, { c9: "Approve" }),
			"frappe.flow.api.resume",
			{ session: "S1", answers: { c9: "Approve" }, approval_seq: 8 },
		],
		[(c) => c.rewind("S1", 4), "frappe.flow.api.rewind", { session: "S1", target_seq: 4 }],
		[(c) => c.compact("S1"), "frappe.flow.api.compact", { session: "S1" }],
		[(c) => c.findUsers("an"), "frappe.flow.api.find_users", { query: "an" }],
		[(c) => c.shares("S1"), "frappe.flow.api.list_shares", { session: "S1" }],
		[(c) => c.share("S1", ann), "frappe.flow.api.share_session", { session: "S1", user: ann }],
		[(c) => c.unshare("S1", ann), "frappe.flow.api.unshare_session", { session: "S1", user: ann }],
		[
			(c) => c.setGeneralAccess("S1", "Everyone"),
			"frappe.flow.api.set_general_access",
			{ session: "S1", access: "Everyone" },
		],
	];
	const transport = fakeTransport(
		Object.fromEntries(cases.map(([, method]) => [method, { from: method }]))
	);
	const client = new FrappeClient({ boot, transport, hooks: { agent: () => "Support" } });
	for (const [call, method] of cases) assert.deepEqual(await call(client), { from: method });
	assert.deepEqual(
		transport.calls,
		cases.map(([, method, args]) => [method, args])
	);
});

test("a sync that fails after a run ends is retried once, then dropped quietly", async () => {
	const { fakeSocket } = await import("./helpers/socket.js");
	const reported = [];
	let failures = 1;
	const transport = fakeTransport({
		"frappe.flow.api.entries": { entries: [{ type: "run_ended", seq: 1, reason: "done" }] },
		"frappe.flow.api.sync_session": () => {
			if (failures-- > 0) throw new Error("Internal Server Error");
			return session;
		},
	});
	const client = new FrappeClient({
		socket: fakeSocket(),
		boot,
		transport,
		hooks: { onSession: (data) => reported.push(data.name) },
	});
	const stream = client.stream("S1");
	await stream[Symbol.asyncIterator]().next(); // the run_ended row
	stream.close();
	await new Promise((resolve) => setImmediate(resolve));
	assert.deepEqual(reported, ["S1"]);
	failures = 2;
	assert.equal(await client.syncSession("S1"), null);
	assert.equal(
		transport.calls.filter(([method]) => method === "frappe.flow.api.sync_session").length,
		4
	);
});
