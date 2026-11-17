// The relay calls open in this tab, and the mark that shows them to the person.
import { h, render, type AppContext } from "vue";
import { AgentMark } from "./agentMark";

export interface RelayEvent {
	call_id: string;
	op: "tabs" | "acts" | "state" | "dialogs" | "run";
	tab?: string;
	act?: string;
	args?: any;
	client?: string | null;
}

export class RelayCalls {
	readonly mark: AgentMark;
	private readonly open = new Map<string, RelayEvent>();
	private shown: Promise<void> | undefined;
	/** True after Stop: the tab refuses every call until it reloads. */
	stopped = false;

	constructor(
		private readonly context: AppContext | undefined,
		private readonly onStop: (calls: RelayEvent[]) => void,
	) {
		this.mark = new AgentMark(() => this.stop());
	}

	start(call: RelayEvent) {
		this.open.set(call.call_id, call);
		this.mark.driving(call.client ?? null);
	}

	/** Resolves once the mark is on the page, so no act runs before the person can see who drives and press Stop. A failed load rejects, and the next call tries again. */
	ready(): Promise<void> {
		this.shown ??= this.mount().catch((error) => {
			this.shown = undefined;
			throw error;
		});
		return this.shown;
	}

	/** A call came in after Stop: show again why it was refused. */
	refused() {
		this.mark.refused();
	}

	/** False once the call ended or Stop ended it: it has no further answer. */
	live(call: RelayEvent) {
		return this.open.has(call.call_id);
	}

	finish(call: RelayEvent) {
		if (this.open.delete(call.call_id) && !this.open.size) this.mark.idle();
	}

	private stop() {
		this.stopped = true;
		const calls = [...this.open.values()];
		this.open.clear();
		this.onStop(calls);
	}

	/** The mark loads with the first call, not with the page. */
	private async mount() {
		const { default: Mark } = await import("./AgentMark.vue");
		const vnode = h(Mark, { mark: this.mark });
		vnode.appContext = this.context ?? null;
		render(vnode, document.body.appendChild(document.createElement("div")));
	}
}
