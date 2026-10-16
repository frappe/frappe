import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { readFileSync } from "node:fs";
import path from "node:path";
import vm from "node:vm";
import test from "node:test";

function relay() {
	const redis = new EventEmitter();
	redis.connect = async () => redis.emit("ready");
	redis.channels = new Map();
	redis.subscribe = async (channel, listener) => {
		redis.channels.set(channel, listener);
	};
	redis.unsubscribe = async () => {};
	const module = { exports: {} };
	vm.runInNewContext(
		readFileSync(new URL("../../realtime/handlers.js", import.meta.url), "utf8"),
		{
			module,
			process,
			console,
			require: (name) =>
				name === "path"
					? path
					: {
							get_conf: () => ({}),
							get_redis_subscriber: () => redis,
					  },
		}
	);
	const delivered = [];
	function socket(site, id) {
		const socket = new EventEmitter();
		Object.assign(socket, {
			id,
			site_name: site,
			connected: true,
			join() {},
			leave() {},
			nsp: {
				to: (room) => ({
					emit: (event, data) => delivered.push({ room, event, session: data.session }),
				}),
			},
			frappe_request: async () => ({ ok: true, json: async () => ({ message: true }) }),
		});
		module.exports(socket);
		return socket;
	}
	return { redis, delivered, socket };
}

test("Redis recovery resyncs all subscribed rooms even when no further event arrives", async () => {
	const { redis, delivered, socket } = relay();
	const first = socket("site-a", "one");
	const second = socket("site-b", "two");
	const subscribe = (s, session) =>
		new Promise((resolve) => s.emit("flow:subscribe", session, resolve));
	assert.equal((await subscribe(first, "s1")).subscribed, true);
	assert.equal((await subscribe(second, "s2")).subscribed, true);
	assert.deepEqual(delivered, []);
	redis.emit("reconnecting");
	redis.emit("ready");
	assert.deepEqual(delivered, [
		{ room: "harness:site-a:s1", event: "flow:resync", session: "s1" },
		{ room: "harness:site-b:s2", event: "flow:resync", session: "s2" },
	]);
	delivered.length = 0;
	first.emit("flow:unsubscribe", "s1");
	redis.emit("ready");
	assert.deepEqual(
		delivered.map((event) => event.session),
		["s2"]
	);
});

test("when the site says access to a session changed, its sockets are asked again and refused ones leave", async () => {
	const { redis, socket } = relay();
	const owner = socket("site-a", "owner");
	const viewer = socket("site-a", "viewer");
	const elsewhere = socket("site-b", "elsewhere");
	const subscribe = (s, session) =>
		new Promise((resolve) => s.emit("flow:subscribe", session, resolve));
	for (const s of [owner, viewer, elsewhere]) await subscribe(s, "s1");
	const refused = async () => ({ ok: false, status: 403 });
	viewer.frappe_request = refused;
	elsewhere.frappe_request = refused;
	// the site can't answer for the owner just then
	owner.frappe_request = async () => ({ ok: false, status: 502 });

	const notice = redis.channels.get("flow-access:site-a");
	await notice(JSON.stringify({ session: "s1" }), "flow-access:site-a");
	assert.deepEqual([...owner.flow_sessions], ["s1"], "a hiccup cuts no one off");
	assert.deepEqual([...viewer.flow_sessions], [], "the removed viewer left");
	assert.deepEqual([...elsewhere.flow_sessions], ["s1"], "another site's session is not asked");
});
