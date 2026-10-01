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

test("a new chat is created with the page's agent and reported back", async () => {
	const reported = [];
	const transport = fakeTransport({
		"flow.api.create_session": { ...session, auto_approve: true },
	});
	const client = new FrappeClient({
		boot,
		transport,
		hooks: { agent: () => "Support", onSession: (d) => reported.push(d.name) },
	});
	const created = await client.createSession({ model: "Sonnet", auto_approve: true });
	assert.deepEqual(transport.calls[0], [
		"flow.api.create_session",
		{ agent: "Support", model: "Sonnet", auto_approve: 1 },
	]);
	assert.equal(created.session_id, "S1");
	assert.equal(created.config.auto_approve, true);
	assert.equal(created.config.model, "Sonnet");
	assert.deepEqual(reported, ["S1"]);
});

test("session details carry the model's context window and a config the store can patch", async () => {
	const transport = fakeTransport({
		"flow.api.session": session,
		"flow.api.set_title": { title: "Renamed" },
		"flow.api.set_auto_approve": { auto_approve: true },
	});
	const client = new FrappeClient({ boot, transport });
	const info = await client.session("S1");
	assert.equal(info.context_window, 200000);
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
		"flow.api.set_auto_approve",
		{ session: "S1", auto_approve: 1 },
	]);
});

test("the log is presented and mirrored to the page, replaced by a snapshot and appended by a catch-up", async () => {
	const mirrored = [];
	const transport = fakeTransport({
		"flow.api.entries": ({ since, path }) => ({
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
		"flow.api.entries",
		{ session: "S1", since: 2, path: "all" },
	]);
});

test("attachments are uploaded as private Files and staged, and cleaned up by File name", async () => {
	const transport = fakeTransport({
		"flow.api.attach_file": ({ file }) => ({
			file,
			file_name: file.replace("FILE-", ""),
			file_size: 1,
		}),
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
		"flow.api.cleanup_attachments",
		{ session: "S1", attachments: ["FILE-shot.png"] },
	]);
});

test("preparation failures discard the upload without creating a session", async () => {
	const transport = fakeTransport({
		"flow.api.attach_file": () => {
			throw new Error("Cannot extract");
		},
	});
	const client = new FrappeClient({ boot, transport });
	await assert.rejects(client.prepareAttachment({ name: "broken.pdf" }), /Cannot extract/);
	assert.deepEqual(transport.calls.at(-1), [
		"flow.api.cleanup_attachments",
		{ attachments: ["FILE-broken.pdf"] },
	]);
});

test("the model list comes from the page's boot first, then refreshes from the server", async () => {
	const transport = fakeTransport({
		"flow.api.boot": {
			models: [
				{
					name: "GPT",
					model_id: "openai/gpt-4o",
					provider: null,
					context_window: 0,
				},
			],
		},
		"flow.api.set_model": ({ model }) => ({
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
			provider: "openai",
			model_id: "openai/gpt-4o",
			context_window: null,
		},
	]);
	const switched = await client.setModel("S1", { model: "GPT", reasoning_effort: "high" });
	assert.deepEqual(switched, { model: "GPT", context_window: null });
	assert.deepEqual(transport.calls.at(-1), [
		"flow.api.set_model",
		{ session: "S1", model: "GPT", reasoning_effort: "high" },
	]);
});

test("shared provider IDs preserve the session's model when its thinking level changes", async (t) => {
	const { createFlowStore } = await import("@flow/ui-core/store.js");
	const { fakeSocket } = await import("./helpers/socket.js");
	globalThis.localStorage = { getItem: () => null, setItem() {} };
	const models = [boot.models[0], { ...boot.models[0], name: "Other account" }];
	const transport = fakeTransport({
		"flow.api.session": session,
		"flow.api.entries": ({ path }) => ({
			entries:
				path === "active"
					? [{ type: "model_changed", seq: 1, model: models[0].model_id }]
					: [],
			latest_seq: 1,
		}),
		"flow.api.set_model": ({ model }) => ({ model }),
	});
	const client = new FrappeClient({ socket: fakeSocket(), boot: { models }, transport });
	const store = createFlowStore(client, { requireCwd: false, skillsEnabled: false });
	t.after(() => store.detach());
	await store.openSession("S1");
	assert.equal(store.state.conversation.model, "Sonnet");
	await store.selectEffort("high");
	assert.equal(
		transport.calls.find(([method]) => method === "flow.api.set_model")[1].model,
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
		"flow.api.session": session,
		"flow.api.entries": { entries: [], latest_seq: 0 },
		"flow.api.attach_file": ({ file }) => ({ file, file_name: "shot.png" }),
		"flow.api.run": { status: "steered" },
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

test("skills come from the session's agent, or the page's agent before a chat starts", async () => {
	const catalog = { skills: [{ name: "expense-approval", description: "Claims" }] };
	const transport = fakeTransport({ "flow.api.skills": catalog });
	const client = new FrappeClient({ boot, transport, hooks: { agent: () => "Support" } });
	assert.deepEqual(await client.skills("S1"), catalog);
	assert.deepEqual(await client.previewSkills({}), catalog);
	assert.deepEqual(transport.calls, [
		["flow.api.skills", { session: "S1" }],
		["flow.api.skills", { agent: "Support" }],
	]);
});

test("a resume names the batch it answers, so a sub-agent's can be told apart", async () => {
	const transport = fakeTransport({ "flow.api.resume": { run: "R1", status: "started" } });
	const client = new FrappeClient({ boot, transport });
	await client.resume("S1", 8, { c9: "Approve" });
	assert.deepEqual(transport.calls, [
		["flow.api.resume", { session: "S1", answers: { c9: "Approve" }, approval_seq: 8 }],
	]);
});
