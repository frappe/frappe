import { FlowAPIError } from "@flow/ui-core/client.js";

const SUBSCRIBE_TIMEOUT = 15_000;

// Live events for one session, as the store's async event source. The relay room is
// joined first, then the log since `since` is fetched, so nothing published in between
// is lost; live events are then deduplicated by seq (durable) or revision (deltas). A
// seq gap, a resync notice, a reconnect or a changed stream_id re-fetches the log since
// the cursor. Live events pass through `present` (fetched rows arrive presented). Each
// durable run_ended of the session's own turn is reported once through `onTerminal`.
export class SessionStream {
	constructor({
		socket,
		session,
		since = 0,
		fetchEntries,
		present = (event) => event,
		onTerminal = null,
	}) {
		this.socket = socket;
		this.session = session;
		this.cursor = since;
		this.fetchEntries = fetchEntries;
		this.present = present;
		this.onTerminal = onTerminal;
		this.closed = false;
		this.subscribed = false;
		this.unsubscribeOnAck = false;
		this.streamId = null;
		this.revision = 0;
		this.synced = new Set();
		this.queue = [];
		this.waiting = null;
		this.listeners = {
			"flow:event": (event) => {
				if (event?.session_id === this.session) this.push({ kind: "event", event });
			},
			"flow:resync": (notice) => {
				if (notice?.session === this.session) this.push({ kind: "resync" });
			},
			connect: () => {
				if (this.subscribed) this.push({ kind: "reconnect" });
			},
			// the relay dropped this room on an access check: join again, as after a reconnect
			"flow:resubscribe": (notice) => {
				if (notice?.session === this.session) this.push({ kind: "reconnect" });
			},
		};
	}

	close() {
		if (this.closed) return;
		this.closed = true;
		for (const [name, listener] of Object.entries(this.listeners))
			this.socket.off(name, listener);
		if (this.subscribed) this.socket.emit("flow:unsubscribe", this.session);
		else this.unsubscribeOnAck = true;
		this.wake();
	}

	push(item) {
		this.queue.push(item);
		this.wake();
	}

	wake() {
		const resolve = this.waiting;
		if (!resolve) return;
		this.waiting = null;
		resolve(this.queue.length ? this.queue.shift() : null);
	}

	next() {
		if (this.queue.length) return Promise.resolve(this.queue.shift());
		if (this.closed) return Promise.resolve(null);
		return new Promise((resolve) => (this.waiting = resolve));
	}

	// resolves once the relay has joined the Redis channel, or false when refused
	subscribe() {
		return new Promise((resolve) => {
			const timer = setTimeout(() => resolve(false), SUBSCRIBE_TIMEOUT);
			this.socket.emit("flow:subscribe", this.session, (ack) => {
				clearTimeout(timer);
				const ok = ack?.subscribed === true;
				this.subscribed = ok;
				if (ok && this.unsubscribeOnAck)
					this.socket.emit("flow:unsubscribe", this.session);
				resolve(ok);
			});
		});
	}

	async *[Symbol.asyncIterator]() {
		try {
			for (const [name, listener] of Object.entries(this.listeners))
				this.socket.on(name, listener);
			if (!(await this.subscribe())) throw refused();
			yield* this.resnapshot();
			while (!this.closed) {
				const item = await this.next();
				if (item === null) return;
				if (item.kind === "resync") {
					yield* this.resnapshot();
					continue;
				}
				if (item.kind === "reconnect") {
					if (!(await this.subscribe())) throw refused();
					yield* this.resnapshot();
					continue;
				}
				const { event } = item;
				if (event.stream_id && this.streamId && event.stream_id !== this.streamId) {
					this.streamId = event.stream_id;
					this.revision = 0;
					yield* this.resnapshot();
				}
				if (event.stream_id) this.streamId ??= event.stream_id;
				if (typeof event.seq === "number") {
					if (event.seq <= this.cursor) continue;
					if (event.seq > this.cursor + 1) {
						yield* this.resnapshot(); // the log covers the gap, and this event with it
						if (event.seq <= this.cursor) continue;
					}
					this.cursor = event.seq;
				} else if (typeof event.revision === "number" && event.revision <= this.revision) {
					continue; // a replayed live-only event
				}
				if (typeof event.revision === "number") this.revision = event.revision;
				this.terminal(event);
				yield this.present(event);
			}
		} finally {
			this.close();
		}
	}

	// durable rows after the cursor, then the in-flight preview of a running turn
	async *resnapshot() {
		const data = await this.fetchEntries(this.cursor);
		if (this.closed) return;
		if (data.stream_id) this.streamId = data.stream_id;
		if (typeof data.revision === "number") this.revision = data.revision;
		const rows = (data.entries ?? [])
			.filter((row) => typeof row.seq === "number" && row.seq > this.cursor)
			.sort((a, b) => a.seq - b.seq);
		for (const row of rows) {
			this.cursor = row.seq;
			this.terminal(row);
			yield row;
		}
		if (data.preview?.length) yield { type: "preview_replay_started" };
		for (const event of data.preview ?? []) yield event;
	}

	terminal(event) {
		if (event.type !== "run_ended" || event.subagent_id || this.synced.has(event.seq)) return;
		this.synced.add(event.seq);
		this.onTerminal?.(event.seq, event);
	}
}

function refused() {
	return new FlowAPIError(
		403,
		"Live updates are unavailable for this conversation. Reopen it to refresh."
	);
}
