// An agent's runs through `window.desk.acts`: a run that opens a confirm or danger returns at once, and `wait` gives its end.
import { acts, agentAsk, type ActDialog, type ActResult } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { readDialogs, watchListed } from "../dialogs/readableDialogs";
import { missingCall, waitingResult } from "./waiting";

interface Call {
	id: number;
	ended: Promise<ActResult>;
	done: boolean;
	/** The confirm the act waits on, once it opened one. */
	dialog?: ActDialog;
}

const KEPT = 20;
let last = 0;
// Only calls that returned `waiting_for_user`, oldest first; a finished one stays for a late `wait`.
const parked = new Map<number, Call>();
// Runs that have not returned yet; a new confirm is the newest one's, as an agent acts one step at a time.
const racing: Call[] = [];

// A confirm that opens while a run is in flight, or after a parked call's own confirm closed, is the agent's, and says so.
// A confirm the act's own starter is known for (`agentAsk.agent`) skips that guess.
agentAsk.note = () => {
	if (agentAsk.agent !== null) return agentAsk.agent ? __("An agent asked for this.") : "";
	return racing.length || [...parked.values()].some((call) => !call.done && !openDialog(call)) ? __("An agent asked for this.") : "";
};
// Confirms a person's act opened: no run claims them.
const people = new Set<number>();

export async function run(name: string, value?: unknown): Promise<ActResult> {
	const holding = holder();
	if (holding) return waiting(holding.call, holding.dialog);

	const call = start(name, value);
	const first = await Promise.race([call.ended.then((result) => ({ result })), call.opened.then((dialog) => ({ dialog }))]);
	call.stop();
	racing.splice(racing.indexOf(call), 1);
	if ("result" in first) return first.result;
	call.dialog = first.dialog;
	park(call);
	return waiting(call, first.dialog);
}

export async function wait(id: number, { timeout }: { timeout?: number } = {}): Promise<ActResult> {
	const call = parked.get(id);
	if (!call) return missingCall(id, readDialogs);
	let timer: ReturnType<typeof setTimeout> | undefined;
	const late = new Promise<null>((resolve) => timeout !== undefined && (timer = setTimeout(resolve, timeout, null)));
	const result = await Promise.race([call.ended, late]);
	clearTimeout(timer);
	return result ?? waiting(call, openDialog(call));
}

function start(name: string, value: unknown) {
	const above = Math.max(-1, ...readDialogs().map((dialog) => dialog.id));
	const call = { id: ++last, done: false } as Call & { opened: Promise<ActDialog>; stop: () => void };
	// Listed before the act starts: it may open its confirm in the tick it starts.
	racing.push(call);
	call.opened = new Promise<ActDialog>((resolve) => {
		call.stop = watchListed(() => {
			if (racing.at(-1) !== call) return;
			markPeople();
			const dialog = readDialogs().find((held) => held.id > above && isConfirm(held) && !owned(held) && !people.has(held.id));
			if (dialog) resolve(dialog);
		});
	});
	call.ended = acts.call(name, value, { agent: true });
	return call;
}

function markPeople() {
	const open = readDialogs();
	for (const id of people) if (!open.some((held) => held.id === id)) people.delete(id);
	if (agentAsk.agent !== false) return;
	// The list changes once per dialog, so the newest unowned confirm is the one this person's act just opened.
	const newest = open.filter((held) => isConfirm(held) && !owned(held)).at(-1);
	if (newest) people.add(newest.id);
}

function owned(dialog: ActDialog) {
	return [...parked.values()].some((held) => !held.done && held.dialog?.id === dialog.id);
}

function park(call: Call) {
	parked.set(call.id, call);
	// The act may open a later confirm (a `beforeSubmit` after the built-in one); it holds the other runs too.
	// A run in flight claims a new confirm first, as it was started last.
	const stop = watchListed(() => (markPeople(), adopt(call)));
	void call.ended.then(() => {
		stop();
		call.done = true;
		adoptAll();
		const finished = [...parked.values()].filter((held) => held.done);
		for (const old of finished.slice(0, Math.max(0, finished.length - KEPT))) parked.delete(old.id);
	});
}

/** A run that ends frees the confirm it claimed, and ends the wait for new ones: the older parked acts look again. */
function adoptAll() {
	for (const call of parked.values()) adopt(call);
}

function adopt(call: Call) {
	if (racing.length || call.done) return;
	const later = readDialogs().find((held) => held.id > call.dialog!.id && isConfirm(held) && !owned(held) && !people.has(held.id));
	if (later) call.dialog = later;
}

/** A parked call whose own confirm is still open: every other run waits behind it. */
function holder() {
	for (const call of parked.values()) {
		const dialog = !call.done && openDialog(call);
		if (dialog) return { call, dialog };
	}
}

function openDialog(call: Call) {
	return readDialogs().find((held) => held.id === call.dialog?.id);
}

function isConfirm(dialog: ActDialog) {
	return dialog.kind === "confirm" || dialog.kind === "danger";
}

function waiting(call: Call, dialog: ActDialog | undefined) {
	return waitingResult(call.id, dialog, readDialogs);
}
