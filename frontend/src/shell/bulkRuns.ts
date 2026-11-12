// The shell's follower of bulk runs: one `task_update` listener, the state of each run a page asked for, and a toast when it settles.
import { computed, reactive } from "vue";
import { toast } from "frappe-ui";
import { getDocument } from "@framework/ui/api";
import type { RealtimeSocket } from "@framework/ui/socket";
import { __ } from "@/i18n";
import { bulkSocket } from "@/shell/bulkSocket";

const TASK_UPDATE = "task_update";
const BACKGROUND_TASK = "Background Task";
const STAGE: Record<string, number> = { Queued: 0, Running: 1, Completed: 2, Failed: 2, Cancelled: 2 };
const READ_ATTEMPTS = 3;
const READ_RETRY_MS = 1000;

export type BulkRunStatus =
	| "Queued"
	| "Running"
	| "Completed"
	| "Failed"
	| "Cancelled";

/** A record of the run: its name, or name and doctype when the run spans doctypes. */
export type BulkRecordRef = string | { name: string; doctype: string };

export interface BulkFailure {
	name: string;
	doctype?: string;
	error: string;
}

/** What the server's runner stores on the Background Task. */
export interface BulkResult {
	total: number;
	done: BulkRecordRef[];
	failed: BulkFailure[];
	queued?: BulkRecordRef[];
	/** A bulk print's merged PDF; absent when every record failed. */
	file_url?: string;
}

export interface BulkRun {
	taskId: string;
	taskName: string;
	status: BulkRunStatus;
	/** 0 to 100. */
	progress: number;
	/** The runner's "3 of 40", or empty. */
	stage: string;
	/** Read once the task is `Completed`. */
	result: BulkResult | null;
	/** Why the run crashed (`Failed`), or why its result could not be read. */
	error: string | null;
}

type Settled = (run: BulkRun) => void;

interface Followed {
	run: BulkRun;
	settled: boolean;
	dismissed: boolean;
	/** A read loop is running; an event that lands meanwhile asks it to read once more. */
	reading: boolean;
	reread: boolean;
	listeners: Settled[];
}

interface TaskMessage {
	task_id?: unknown;
	task_name?: unknown;
	status?: unknown;
	progress?: unknown;
	stage?: unknown;
}

let stopWatching: (() => void) | undefined;
const followed = reactive(new Map<string, Followed>());

/** Starts following the run behind a `202 {task_id}`; the same id twice follows once. */
export function followBulkRun(taskId: string, onSettled?: Settled): BulkRun {
	const existing = followed.get(taskId);
	if (existing) {
		if (onSettled)
			existing.settled
				? onSettled(existing.run)
				: existing.listeners.push(onSettled);
		return existing.run;
	}
	const entry: Followed = {
		run: {
			taskId,
			taskName: "",
			status: "Queued",
			progress: 0,
			stage: "",
			result: null,
			error: null,
		},
		settled: false,
		dismissed: false,
		reading: false,
		reread: false,
		listeners: onSettled ? [onSettled] : [],
	};
	followed.set(taskId, entry);
	const socket = bulkSocket();
	if (!stopWatching && socket) stopWatching = watchBulkRuns(socket);
	// Reading through the map gives the reactive entry, which the reply must update.
	const tracked = followed.get(taskId)!;
	void readTask(tracked);
	return tracked.run;
}

/** The runs this tab follows, oldest first. */
export function useBulkRuns() {
	return computed(() => [...followed.values()].map((entry) => entry.run));
}

/** Drops a run from the list; a settled run stays until its reader says so. */
export function dismissBulkRun(taskId: string) {
	const entry = followed.get(taskId);
	if (entry) entry.dismissed = true;
	followed.delete(taskId);
}

/** Listens for `task_update` and rereads the runs still moving on a reconnect; returns the stop. */
export function watchBulkRuns(socket: RealtimeSocket | undefined): () => void {
	const onUpdate = (...args: unknown[]) =>
		applyMessage((args[0] ?? {}) as TaskMessage);
	const onReconnect = () => {
		for (const entry of followed.values())
			if (isLive(entry)) void readTask(entry);
	};
	socket?.on(TASK_UPDATE, onUpdate);
	socket?.on("connect", onReconnect);
	return () => {
		socket?.off(TASK_UPDATE, onUpdate);
		socket?.off("connect", onReconnect);
	};
}

function applyMessage(message: TaskMessage) {
	const entry =
		typeof message.task_id === "string"
			? followed.get(message.task_id)
			: undefined;
	if (!entry || !isLive(entry)) return;
	const { run } = entry;
	if (typeof message.task_name === "string") run.taskName = message.task_name;
	if (typeof message.progress === "number") run.progress = message.progress;
	if (typeof message.stage === "string") run.stage = message.stage;
	advance(run, message.status);
	if (isFinal(run.status)) void readTask(entry);
}

/** Reads the row until it agrees with the run: the final row, or any row while no event said final. */
async function readTask(entry: Followed) {
	if (entry.reading) {
		entry.reread = true;
		return;
	}
	entry.reading = true;
	let failure: unknown;
	let caughtUp = false;
	for (let attempt = 1; attempt <= READ_ATTEMPTS && isLive(entry); attempt++) {
		if (attempt > 1) await new Promise((resolve) => setTimeout(resolve, READ_RETRY_MS));
		try {
			caughtUp = await applyRow(entry);
			failure = undefined;
		} catch (error) {
			failure = error;
		}
		if (caughtUp) break;
	}
	entry.reading = false;
	if (!isLive(entry)) return;
	if (!caughtUp && isFinal(entry.run.status)) {
		entry.run.error = failure ? errorText(failure) : unreadable(entry.run.status);
		settle(entry);
	} else if (entry.reread) {
		entry.reread = false;
		void readTask(entry);
	}
}

/** True when nothing is left to wait for. A row behind a final event is not caught up. */
async function applyRow(entry: Followed): Promise<boolean> {
	const { run } = entry;
	const { data } = await getDocument(BACKGROUND_TASK, run.taskId);
	if (!isLive(entry)) return true;
	run.taskName = String(data.task_name ?? run.taskName);
	advance(run, data.status);
	if (!isStatus(data.status) || !isFinal(data.status)) return !isFinal(run.status);
	// The row holds progress and stage only at the end; the events carry them while it runs.
	if (run.status === "Completed") {
		run.progress = 100;
		run.result = parseResult(data.result);
		run.error = run.result ? null : unreadable(run.status);
	}
	// `exception` is for System Managers only, so the owner may get no reason.
	if (run.status === "Failed") run.error = lastLine(data.exception) ?? unreadable(run.status);
	settle(entry);
	return true;
}

function unreadable(status: BulkRunStatus) {
	return status === "Completed" ? __("The result could not be read.") : __("The run stopped before it finished.");
}

function errorText(error: unknown) {
	return error instanceof Error ? error.message : String(error);
}

function isLive(entry: Followed) {
	return !entry.settled && !entry.dismissed;
}

function settle(entry: Followed) {
	entry.settled = true;
	announce(entry.run);
	for (const listener of entry.listeners.splice(0)) {
		try {
			listener(entry.run);
		} catch (error) {
			console.error(error);
		}
	}
}

function announce(run: BulkRun) {
	const name = run.taskName || __("Bulk action");
	const { result } = run;
	if (!result) {
		toast.error(
			run.error ? `${name}: ${run.error}` : `${name}: ${__(run.status)}`
		);
		return;
	}
	const counts = [
		__("{0} done", [result.done.length]),
		__("{0} failed", [result.failed.length]),
	];
	if (result.queued?.length)
		counts.push(__("{0} queued", [result.queued.length]));
	const message = `${name}: ${counts.join(", ")}`;
	if (result.failed.length) toast.warning(message);
	else toast.success(message);
}

function parseResult(raw: unknown): BulkResult | null {
	if (typeof raw !== "string" || !raw) return null;
	try {
		const result = JSON.parse(raw);
		return Array.isArray(result?.done) && Array.isArray(result?.failed)
			? result
			: null;
	} catch {
		return null;
	}
}

function lastLine(text: unknown): string | null {
	if (typeof text !== "string") return null;
	return text.trim().split("\n").pop() ?? null;
}

/** Moves the run's status forward only: a read that was sent earlier may land after a newer event. */
function advance(run: BulkRun, status: unknown) {
	if (!isStatus(status) || isFinal(run.status) || STAGE[status] < STAGE[run.status]) return;
	run.status = status;
}

function isStatus(value: unknown): value is BulkRunStatus {
	return typeof value === "string" && value in STAGE;
}

function isFinal(status: BulkRunStatus) {
	return STAGE[status] === STAGE.Completed;
}
