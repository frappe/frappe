// The tab's socket for the bulk run follower, kept apart so its code loads with the first run.
import type { RealtimeSocket } from "@framework/ui/socket";

let socket: RealtimeSocket | undefined;

export function setBulkSocket(value: RealtimeSocket | undefined) {
	socket = value;
}

export function bulkSocket() {
	return socket;
}
