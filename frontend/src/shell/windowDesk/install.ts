// `window.desk`: the frozen facade an agent drives the tab through. It is a layer of wrappers; each member loads its code on first call.
import type { ActResult } from "@/acts/dispatcher";
import { run, wait } from "./runs";
import type { ListedAct } from "./actList";
import type { DeskState, StateOptions } from "./pageState";
import { readDialogs } from "../dialogs/readableDialogs";

export interface DeskApi {
	readonly version: 1;
	readonly acts: {
		list(): Promise<ListedAct[]>;
		options(name: string, query?: string): Promise<ActResult>;
		run(name: string, value?: unknown): Promise<ActResult>;
		wait(call: number, options?: { timeout?: number }): Promise<ActResult>;
	};
	state(options?: StateOptions): Promise<DeskState>;
	dialogs(): Promise<ReturnType<typeof readDialogs>>;
}

declare global {
	interface Window {
		desk?: DeskApi;
	}
}

const list = () => import("./actList");
const state = () => import("./pageState");

/** Sets `window.desk` once; a second call changes nothing. */
export function installDesk() {
	if (window.desk) return;
	const desk: DeskApi = Object.freeze({
		version: 1,
		acts: Object.freeze({
			list: () => list().then((m) => m.listActs()),
			options: (name: string, query = "") => list().then((m) => m.optionsOf(name, query)),
			run,
			wait,
		}),
		state: (options?: StateOptions) => state().then((m) => m.readState(options)),
		dialogs: async () => readDialogs(),
	});
	// A page script cannot swap it out either.
	Object.defineProperty(window, "desk", { value: desk, writable: false, configurable: false });
}
