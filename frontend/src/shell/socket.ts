// The shell's realtime connection: one per tab, on the `$socket` global that `getSocketInstance` reads.
import { io } from "socket.io-client";
import { resubscribeHeldDocs, type RealtimeSocket } from "@framework/ui/socket";
import type { Boot } from "@/boot";

type SocketBoot = Pick<Boot, "site_name" | "socketio_port" | "dev_server">;

export function createSocket(boot: SocketBoot) {
	const socket = io(socketUrl(boot, window.location), { withCredentials: true });
	repairRooms(socket);
	return socket;
}

// A reconnect is a new socket id, so the server's room membership is gone with it.
export function repairRooms(socket: RealtimeSocket) {
	socket.on("connect", () => resubscribeHeldDocs(socket));
}

/** The realtime server's address for this site, as desk v1's `get_host` builds it. */
export function socketUrl(boot: SocketBoot, location: Pick<Location, "origin" | "protocol" | "hostname">) {
	const host = boot.dev_server
		? `${location.protocol}//${location.hostname}:${boot.socketio_port || 9000}`
		: location.origin;
	return `${host}/${boot.site_name}`;
}
