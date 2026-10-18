import assert from "node:assert/strict";
import test from "node:test";

import { SessionStream } from "../src/api/stream.js";

import { fakeSocket } from "./helpers/socket.js";
import { applyEvent, initialConversation } from "@flow/ui-core/transcript.js";

const ended = (seq, extra = {}) => ({
	type: "run_ended",
	seq,
	reason: "done",
	session_id: "s1",
	...extra,
});

async function collect(stream, count) {
	const events = [];
	for await (const event of stream) {
		events.push(event);
		if (events.length >= count) break;
	}
	return events;
}

test("the room is joined before the log is fetched, and live events are deduplicated by seq", async () => {
	const socket = fakeSocket();
	const fetches = [];
	const stream = new SessionStream({
		socket,
		session: "s1",
		since: 2,
		fetchEntries: async (cursor) => {
			fetches.push({
				cursor,
				subscribed: socket.emitted.some(([name]) => name === "flow:subscribe"),
			});
			return {
				entries: [
					{ type: "user_message", seq: 3 },
					{ type: "user_message", seq: 4 },
				],
				stream_id: "x",
				revision: 10,
			};
		},
	});
	const iterator = stream[Symbol.asyncIterator]();
	const first = await iterator.next();
	assert.deepEqual(fetches, [{ cursor: 2, subscribed: true }]);
	assert.equal(first.value.seq, 3);
	assert.equal((await iterator.next()).value.seq, 4);
	// seq 4 again is a replay; 5 is new; a delta carries only a revision
	socket.fire("flow:event", {
		type: "user_message",
		seq: 4,
		session_id: "s1",
		stream_id: "x",
		revision: 11,
	});
	socket.fire("flow:event", {
		type: "assistant_message",
		seq: 5,
		session_id: "s1",
		stream_id: "x",
		revision: 12,
	});
	socket.fire("flow:event", {
		type: "text_delta",
		text: "h",
		session_id: "s1",
		stream_id: "x",
		revision: 13,
	});
	socket.fire("flow:event", {
		type: "text_delta",
		text: "old",
		session_id: "s1",
		stream_id: "x",
		revision: 13,
	});
	socket.fire("flow:event", {
		type: "text_delta",
		text: "i",
		session_id: "other",
		stream_id: "x",
		revision: 14,
	});
	assert.equal((await iterator.next()).value.seq, 5);
	assert.equal((await iterator.next()).value.text, "h");
	stream.close();
	assert.equal((await iterator.next()).done, true);
	assert.deepEqual(socket.emitted.at(-1), ["flow:unsubscribe", "s1"]);
	assert.equal(socket.has("flow:event"), false);
});

test("a seq gap, a resync notice, a reconnect, a relay drop and a new stream id each re-fetch the log", async () => {
	const socket = fakeSocket();
	const fetches = [];
	let rows = [];
	const stream = new SessionStream({
		socket,
		session: "s1",
		since: 0,
		fetchEntries: async (cursor) => {
			fetches.push(cursor);
			return { entries: rows.filter((row) => row.seq > cursor) };
		},
	});
	const iterator = stream[Symbol.asyncIterator]();
	rows = [{ type: "user_message", seq: 1 }];
	assert.equal((await iterator.next()).value.seq, 1);
	// gap: 2 was missed, 3 arrives live
	rows = [...rows, { type: "assistant_message", seq: 2 }, { type: "tool_result", seq: 3 }];
	socket.fire("flow:event", {
		type: "tool_result",
		seq: 3,
		session_id: "s1",
		stream_id: "a",
		revision: 3,
	});
	assert.equal((await iterator.next()).value.seq, 2);
	assert.equal((await iterator.next()).value.seq, 3);
	// resync notice
	rows = [...rows, { type: "user_message", seq: 4 }];
	socket.fire("flow:resync", { session: "s1" });
	assert.equal((await iterator.next()).value.seq, 4);
	// reconnect: the room must be joined again, then the log re-read
	rows = [...rows, { type: "user_message", seq: 5 }];
	const subscribes = () => socket.emitted.filter(([name]) => name === "flow:subscribe").length;
	socket.fire("connect");
	assert.equal((await iterator.next()).value.seq, 5);
	assert.equal(subscribes(), 2);
	// dropped by the relay on an access check: the same
	rows = [...rows, { type: "user_message", seq: 6 }];
	socket.fire("flow:resubscribe", { session: "s1" });
	assert.equal((await iterator.next()).value.seq, 6);
	assert.equal(subscribes(), 3);
	// a restarted daemon publishes under a new stream id
	rows = [...rows, { type: "user_message", seq: 7 }, { type: "user_message", seq: 8 }];
	socket.fire("flow:event", {
		type: "user_message",
		seq: 8,
		session_id: "s1",
		stream_id: "b",
		revision: 1,
	});
	assert.equal((await iterator.next()).value.seq, 7);
	assert.equal((await iterator.next()).value.seq, 8);
	assert.deepEqual(fetches, [0, 1, 3, 4, 5, 6]);
	stream.close();
});

test("each terminal run_ended is reported exactly once, replayed or re-fetched; a sub-agent's is not terminal", async () => {
	const socket = fakeSocket();
	const terminals = [];
	const stream = new SessionStream({
		socket,
		session: "s1",
		since: 0,
		fetchEntries: async (cursor) => ({
			entries: [ended(2), ended(3, { subagent_id: "c1" }), ended(5)].filter(
				(row) => row.seq > cursor
			),
		}),
		onTerminal: (seq) => terminals.push(seq),
	});
	const iterator = stream[Symbol.asyncIterator]();
	assert.equal((await iterator.next()).value.seq, 2);
	assert.equal((await iterator.next()).value.seq, 3);
	assert.equal((await iterator.next()).value.seq, 5);
	socket.fire("flow:event", ended(5, { stream_id: "a", revision: 9 }));
	socket.fire("flow:event", ended(2, { stream_id: "a", revision: 9 }));
	socket.fire("flow:resync", { session: "s1" });
	socket.fire("flow:event", {
		type: "text_delta",
		text: "!",
		session_id: "s1",
		stream_id: "a",
		revision: 10,
	});
	assert.equal((await iterator.next()).value.text, "!");
	assert.deepEqual(terminals, [2, 5]);
	stream.close();
});

test("a refused subscription ends the stream with an error, and releases the room once acked", async () => {
	const socket = fakeSocket({ subscribed: false });
	const stream = new SessionStream({
		socket,
		session: "s1",
		fetchEntries: async () => ({ entries: [] }),
	});
	await assert.rejects(collect(stream, 1), /Live updates are unavailable/);
	assert.equal(
		socket.emitted.some(([name]) => name === "flow:unsubscribe"),
		false
	);

	// dropped by the relay and refused on asking again, as a removed viewer is: the same error
	const dropped = fakeSocket();
	const viewing = collect(
		new SessionStream({
			socket: dropped,
			session: "s1",
			fetchEntries: async () => ({ entries: [] }),
		}),
		1
	);
	await new Promise((resolve) => setTimeout(resolve, 0));
	dropped.subscribed = false;
	dropped.fire("flow:resubscribe", { session: "s1" });
	await assert.rejects(viewing, /Live updates are unavailable/);

	// closed before the ack arrives: the room is left as soon as it is joined
	const late = fakeSocket();
	const pending = new SessionStream({
		late,
		socket: late,
		session: "s1",
		fetchEntries: async () => ({ entries: [] }),
	});
	const iterator = pending[Symbol.asyncIterator]();
	const next = iterator.next();
	pending.close();
	assert.equal((await next).done, true);
	await new Promise((resolve) => setTimeout(resolve, 0));
	assert.deepEqual(late.emitted.at(-1), ["flow:unsubscribe", "s1"]);
});

test("a reconnect or a resync replaces the streaming preview instead of appending it", async (t) => {
	for (const notice of ["connect", "flow:resync"]) {
		const socket = fakeSocket();
		let preview = "Hello";
		const stream = new SessionStream({
			socket,
			session: "s1",
			fetchEntries: async () => ({
				entries: [],
				preview: [{ type: "text_delta", text: preview }],
			}),
		});
		t.after(() => stream.close());
		const state = initialConversation();
		const iterator = stream[Symbol.asyncIterator]();
		const readPreview = async () => {
			let event;
			do {
				event = (await iterator.next()).value;
				applyEvent(state, event);
			} while (event.type !== "text_delta");
		};
		await readPreview();
		preview = "Hello world";
		socket.fire(notice, { session: "s1" });
		await readPreview();
		assert.deepEqual(state.partial, [{ type: "text", text: "Hello world" }], notice);
	}
});
