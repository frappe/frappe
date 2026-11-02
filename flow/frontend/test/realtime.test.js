import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { readFileSync } from "node:fs";
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
		readFileSync(new URL("../../../realtime/flow_handlers.js", import.meta.url), "utf8"),
		{
			module,
			console,
			require: () => ({
				get_conf: () => ({}),
				get_redis_subscriber: () => redis,
			}),
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

test("a view taken back: the owner is left alone, whoever may have lost it stays only on a clear yes, and one who leaves is told", async () => {
	const { redis, socket } = relay();
	const join = async (site, user) => {
		const s = socket(site, `${site}/${user}`);
		s.user = user;
		await new Promise((resolve) => s.emit("flow:subscribe", "s1", resolve));
		s.asked = 0;
		s.told = [];
		s.on("flow:resubscribe", (notice) => s.told.push(notice.session));
		return s;
	};
	const ann = await join("site-a", "ann"); // the owner
	const bob = await join("site-a", "bob");
	const cara = await join("site-a", "cara");
	const elsewhere = await join("site-b", "bob");
	// from here on each one answers with this status, counting the times it is asked
	const answer = (s, status) =>
		(s.frappe_request = async () => {
			s.asked++;
			return { ok: status === 200, status, json: async () => ({ message: status === 200 }) };
		});
	answer(ann, 502);
	answer(bob, 502); // the site can't answer for Bob just then: he leaves anyway
	answer(cara, 200);
	answer(elsewhere, 403);
	const notice = (body) =>
		redis.channels.get("flow-access:site-a")(JSON.stringify(body), "flow-access:site-a");

	await notice({ session: "s1", user: "bob", owner: "ann" });
	assert.deepEqual(
		[ann.asked, bob.asked, cara.asked, elsewhere.asked],
		[0, 1, 0, 0],
		"only Bob is asked"
	);
	assert.deepEqual([...bob.flow_sessions], [], "Bob left");
	assert.deepEqual([...cara.flow_sessions, ...elsewhere.flow_sessions], ["s1", "s1"]);
	// so his page asks again: it resumes if he still may read, or says live updates stopped
	assert.deepEqual([ann.told, bob.told, cara.told, elsewhere.told], [[], ["s1"], [], []]);

	// an everyone share taken back names no one: all but the owner are asked
	await notice({ session: "s1", user: null, owner: "ann" });
	assert.deepEqual([ann.asked, cara.asked, elsewhere.asked], [0, 1, 0]);
	assert.deepEqual(
		[...ann.flow_sessions, ...cara.flow_sessions],
		["s1", "s1"],
		"the owner and Cara stay"
	);
});
