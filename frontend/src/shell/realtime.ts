// `shell.realtime`: the tab's socket events for a script, dropped with the component that asked.
import { getCurrentInstance, getCurrentScope, onScopeDispose } from "vue";
import { getSocketInstance, type RealtimeSocket } from "@framework/ui/socket";

export interface ShellRealtime {
	/** Calls `handler` with each `event`; returns `off`. In a component's setup it unsubscribes when the component unmounts. */
	on(event: string, handler: (...payload: any[]) => void): () => void;
}

/** Reads the tab's socket in setup; outside a component there is none, and `on` does nothing. */
export function useRealtime(): ShellRealtime {
	const socket = getCurrentInstance() ? getSocketInstance() : undefined;
	return { on: (event, handler) => subscribe(socket, event, handler) };
}

function subscribe(socket: RealtimeSocket | undefined, event: string, handler: (...payload: any[]) => void) {
	if (!socket) return () => {};
	// A wrapper of its own, so `off` removes this subscription and no other of the same handler.
	const listener = (...payload: unknown[]) => {
		try {
			handler(...payload);
		} catch (error) {
			console.error(`[frappe] A realtime handler for "${event}" failed.`, error);
		}
	};
	socket.on(event, listener);
	const off = () => socket.off(event, listener);
	if (getCurrentScope()) onScopeDispose(off);
	return off;
}
