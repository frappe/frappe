// An agent's runs through `window.desk.acts`: a run that opens a confirm or danger returns at once, and `wait` gives its end.
import { acts, type ActDialog, type ActResult } from "@/acts/dispatcher";
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
			const dialog = readDialogs().find((held) => held.id > above && isConfirm(held) && !owned(held));
			if (dialog) resolve(dialog);
		});
	});
	call.ended = acts.call(name, value);
	return call;
}

function owned(dialog: ActDialog) {
	return [...parked.values()].some((held) => !held.done && held.dialog?.id === dialog.id);
}

function park(call: Call) {
	parked.set(call.id, call);
	// The act may open a later confirm (a `beforeSubmit` after the built-in one); it holds the other runs too.
	const stop = watchListed(() => {
		const later = readDialogs().find((held) => held.id > call.dialog!.id && isConfirm(held) && !owned(held));
		if (later) call.dialog = later;
	});
	void call.ended.then(() => {
		stop();
		call.done = true;
		const finished = [...parked.values()].filter((held) => held.done);
		for (const old of finished.slice(0, Math.max(0, finished.length - KEPT))) parked.delete(old.id);
	});
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
