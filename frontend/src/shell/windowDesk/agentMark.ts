// What the person sees of an agent in this tab: shown while relay calls are open and for 30 s after, or after they pressed Stop.
import { ref } from "vue";

const LINGER_MS = 30_000;

export class AgentMark {
	readonly state = ref<"hidden" | "running" | "idle" | "stopped">("hidden");
	readonly client = ref<string | null>(null);
	private timer: ReturnType<typeof setTimeout> | undefined;

	constructor(private readonly onStop: () => void) {}

	/** Calls are open: names the agent that made the latest. */
	driving(client: string | null) {
		this.client.value = client;
		this.show("running");
	}

	/** The last call ended: the mark stays for a while so a quick next call does not blink it. */
	idle() {
		this.show("idle", LINGER_MS);
	}

	stop() {
		this.onStop();
		this.show("stopped", LINGER_MS);
	}

	/** A call came in after Stop: tell the person again why it was refused. */
	refused() {
		this.show("stopped", LINGER_MS);
	}

	private show(state: "running" | "idle" | "stopped", lingerMs?: number) {
		clearTimeout(this.timer);
		this.state.value = state;
		if (lingerMs) this.timer = setTimeout(() => (this.state.value = "hidden"), lingerMs);
	}
}
