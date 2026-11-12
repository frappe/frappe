// The tab's socket for the bulk run follower, set at boot so the follower's code loads with the first run a page follows.
import type { RealtimeSocket } from "@framework/ui/socket";

let socket: RealtimeSocket | undefined;

export function setBulkSocket(value: RealtimeSocket | undefined) {
	socket = value;
}

export function bulkSocket() {
	return socket;
}
