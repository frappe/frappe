// Copyright (c) 2026, Frappe Technologies and contributors
// License: MIT. See LICENSE

// Relays flow server events (Redis channel `harness:<site>:<session>`) to subscribed
// browsers from Frappe's socketio process, so no Python worker is held for a run.

const path = require("path");

// `apps/flow` may be a symlink out of the bench, so resolve frappe through the bench root
const bench = process.env.FRAPPE_BENCH_ROOT || process.cwd();
const node_utils = require(path.join(bench, "apps", "frappe", "node_utils"));

const EVENT = "flow:event";
const RESYNC = "flow:resync";
const RESYNC_ALL = "harness-resync:all";
const RESYNC_SITE = "harness-resync:site:";
const SESSION_NAME = /^[\w.-]{1,140}$/;

// channel -> { site, session, nsp, sockets, ready }; the socket.io room is the channel
const subscriptions = new Map();
// site -> promise of its resync channels being subscribed
const resyncWatches = new Map();
let connecting = null;

function flow_handlers(socket) {
	socket.flow_sessions = new Set();

	socket.on("flow:subscribe", (session, ack) => {
		subscribe(socket, session)
			.catch((err) => {
				console.warn("flow: subscribe failed", err);
				return false;
			})
			.then((ok) => typeof ack === "function" && ack({ subscribed: ok }));
	});

	socket.on("flow:unsubscribe", (session) => {
		if (valid_name(session)) release(socket, session);
	});

	socket.on("disconnect", () => {
		for (const session of [...socket.flow_sessions]) release(socket, session);
	});
}

// The ack must not beat the Redis subscription, or a run started on it loses events.
async function subscribe(socket, session) {
	if (!valid_name(session) || !(await can_stream(socket, session))) return false;
	// a socket that left meanwhile has already run its release
	if (!socket.connected) return false;
	const channel = channel_for(socket, session);
	let entry = subscriptions.get(channel);
	if (!entry) {
		entry = { site: site_of(socket), session, nsp: socket.nsp, sockets: new Set() };
		entry.ready = listen(channel, entry.site).catch((err) => {
			if (subscriptions.get(channel) === entry) subscriptions.delete(channel);
			throw err;
		});
		subscriptions.set(channel, entry);
	}
	entry.sockets.add(socket.id);
	socket.flow_sessions.add(session);
	socket.join(channel);
	try {
		await entry.ready;
	} catch (err) {
		release(socket, session);
		throw err;
	}
	return true;
}

// Asked with the caller's own credentials on the site the socket authenticated against.
async function can_stream(socket, session) {
	const response = await socket.frappe_request("/api/method/frappe.realtime.has_permission", {
		doctype: "Flow Session",
		name: session,
	});
	if (!response.ok) return false;
	const { message } = await response.json();
	return message === true;
}

async function listen(channel, site) {
	const client = await connect();
	await client.subscribe(channel, deliver);
	await watch_resync(site);
}

function deliver(message, channel) {
	const entry = subscriptions.get(channel);
	const event = parse(message);
	if (entry && event) entry.nsp.to(channel).emit(EVENT, event);
}

// The daemon asks for a resync when it had to drop events, naming the sessions if it can.
function watch_resync(site) {
	if (!resyncWatches.has(site)) {
		const watch = connect()
			.then((client) =>
				Promise.all([
					client.subscribe(RESYNC_SITE + site, resync),
					client.subscribe(RESYNC_ALL, resync),
				])
			)
			.catch((err) => {
				resyncWatches.delete(site);
				throw err;
			});
		resyncWatches.set(site, watch);
	}
	return resyncWatches.get(site);
}

function resync(message, channel) {
	const notice = parse(message);
	if (!notice) return;
	const site = channel === RESYNC_ALL ? null : channel.slice(RESYNC_SITE.length);
	const named = Array.isArray(notice.session_ids) ? new Set(notice.session_ids) : null;
	for (const [room, entry] of subscriptions) {
		if ((site && entry.site !== site) || (named && !named.has(entry.session))) continue;
		entry.nsp.to(room).emit(RESYNC, { session: entry.session });
	}
}

function release(socket, session) {
	if (!socket.flow_sessions.delete(session)) return;
	const channel = channel_for(socket, session);
	socket.leave(channel);
	const entry = subscriptions.get(channel);
	if (!entry) return;
	entry.sockets.delete(socket.id);
	if (entry.sockets.size) return;
	subscriptions.delete(channel);
	// queued behind a subscribe still in flight
	connect()
		.then((client) => client.unsubscribe(channel))
		.catch(() => {});
}

// One connection for the process; node-redis re-subscribes its channels after a reconnect.
function connect() {
	if (!connecting) {
		const kind = node_utils.get_conf().flow_redis_url ? "flow_redis_url" : "redis_queue";
		const client = node_utils.get_redis_subscriber(kind);
		client.on("error", (err) => console.warn("flow: redis error", err.message));
		let ready = false;
		client.on("ready", () => {
			// Pub/sub cannot replay events missed while this connection was down.
			if (ready) resync("{}", RESYNC_ALL);
			ready = true;
		});
		connecting = client.connect().then(
			() => client,
			(err) => {
				connecting = null;
				throw err;
			}
		);
	}
	return connecting;
}

function parse(message) {
	try {
		const value = JSON.parse(message);
		return value && typeof value === "object" ? value : null;
	} catch {
		return null;
	}
}

const valid_name = (session) => typeof session === "string" && SESSION_NAME.test(session);
// the site the socket authenticated against, where can_stream is answered
const site_of = (socket) => socket.site_name;
const channel_for = (socket, session) => `harness:${site_of(socket)}:${session}`;

module.exports = flow_handlers;
