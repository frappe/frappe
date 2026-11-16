// The tab's end of the UI relay: it answers each `ui_relay` event through `window.desk`, one call at a time.
import { runMethod } from "@framework/ui/api";
import type { RealtimeSocket } from "@framework/ui/socket";
import type { ActResult } from "@/acts/dispatcher";
import type { DeskApi } from "./install";
import { claimTabId } from "./tabId";

const REPLY = "frappe.desk.ui_relay.reply";

interface RelayEvent {
	call_id: string;
	op: "tabs" | "acts" | "state" | "dialogs" | "run";
	tab?: string;
	act?: string;
	args?: any;
}

/** Listens on the tab's socket; the person turned the setting on, or this is not called. */
export async function startRelay(socket: RealtimeSocket) {
	const tab = await claimTabId();
	const focus = trackFocus();
	let queue: Promise<unknown> = Promise.resolve();
	socket.on("ui_relay", (event) => {
		const call = event as RelayEvent;
		if (call.op === "tabs") return void post(call, tab, { tab, route: route(), title: document.title, focused_at: focus() });
		if (call.tab === tab) queue = queue.then(() => answer(call, tab)).catch((error) => post(call, tab, failed(String(error))));
	});
}

async function answer(call: RelayEvent, tab: string) {
	const open = call.op === "run" ? await openDialogs() : [];
	const result = await perform(call);
	if (result.ok || result.error.code !== "waiting_for_user" || result.error.call === undefined) return post(call, tab, result);

	// `window.desk` hands a run the result of a confirm that was already open and starts nothing: do not borrow its end.
	const dialog = result.error.dialog;
	if (dialog && open.includes(dialog.id)) return post(call, tab, failed("A dialog was already open. Answer it first; this call did not run."));
	await post(call, tab, result, false);
	// The confirm waits on the person; the next call must not wait behind it.
	const parked = result.error.call;
	void window.desk!.acts.wait(parked)
		.catch((error) => failed(String(error)))
		.then((ended) => post(call, tab, ended));
}

async function openDialogs(): Promise<number[]> {
	try {
		return (await window.desk!.dialogs()).map((dialog: { id: number }) => dialog.id);
	} catch {
		return [];
	}
}

async function perform(call: RelayEvent): Promise<ActResult> {
	const desk = window.desk as DeskApi | undefined;
	try {
		if (!desk) return failed("window.desk is not installed in this tab.");
		if (call.op === "run") return call.act ? await desk.acts.run(call.act, call.args) : failed("run needs an act.", "invalid");
		if (call.op === "acts") return await ended(desk, await desk.acts.list().then((all) => onSurface(all, call.args?.surface)));
		if (call.op === "state") return await ended(desk, await desk.state(call.args ?? undefined));
		return await ended(desk, await desk.dialogs());
	} catch (error) {
		return failed(String(error));
	}
}

function onSurface<T extends { surface: string }>(all: T[], surface?: string) {
	return surface ? all.filter((act) => act.surface === surface) : all;
}

async function ended(desk: DeskApi, data: unknown): Promise<ActResult> {
	return { ok: true, data, route: route(), dialogs: await desk.dialogs() };
}

function failed(message: string, code: "failed" | "invalid" = "failed"): ActResult {
	return { ok: false, error: { code, message }, route: route(), dialogs: [] };
}

function post(call: RelayEvent, tab: string, result: unknown, final = true) {
	return runMethod(REPLY, { call_id: call.call_id, tab, result, final }).catch(() => {});
}

function route() {
	return `${location.pathname}${location.search}${location.hash}`;
}

/** The time this tab last had the person's attention; the default target is the tab with the latest. */
function trackFocus() {
	let at = document.hasFocus() ? Date.now() : 0;
	const mark = () => document.visibilityState === "visible" && (at = Date.now());
	window.addEventListener("focus", mark);
	document.addEventListener("visibilitychange", mark);
	return () => at;
}
