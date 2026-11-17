// `window.desk`: the frozen facade an agent drives the tab through. It is a layer of wrappers; each member loads its code on first call.
import type { AppContext } from "vue";
import type { ActResult } from "@/acts/dispatcher";
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

const runs = () => import("./runs");
const list = () => import("./actList");
const state = () => import("./pageState");

/** Sets `window.desk` once; a second call changes nothing. With the person's opt-in, the tab also answers the UI relay. */
export function installDesk(app?: AppContext) {
	if (window.desk) return;
	// A separate chunk, loaded only for a person who turned the setting on.
	if (app?.provides.boot?.agent_ui_relay) import("./relay").then((m) => m.startRelay(app.config.globalProperties.$socket, app));
	const desk: DeskApi = Object.freeze({
		version: 1,
		acts: Object.freeze({
			list: () => list().then((m) => m.listActs()),
			options: (name: string, query = "") => list().then((m) => m.optionsOf(name, query)),
			run: (name: string, value?: unknown) => runs().then((m) => m.run(name, value)),
			wait: (call: number, options?: { timeout?: number }) => runs().then((m) => m.wait(call, options)),
		}),
		state: (options?: StateOptions) => state().then((m) => m.readState(options)),
		dialogs: async () => readDialogs(),
	});
	// A page script cannot swap it out either.
	Object.defineProperty(window, "desk", { value: desk, writable: false, configurable: false });
}
