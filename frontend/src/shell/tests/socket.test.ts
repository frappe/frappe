// The realtime server's address, on `bench start` and behind nginx.
import { describe, expect, it } from "vitest";
import { subscribeToDoc } from "@framework/ui/socket";
import { repairRooms, socketUrl } from "../socket";

const location = { origin: "https://crm.example.com", protocol: "https:", hostname: "crm.example.com" };

describe("socketUrl", () => {
	it("is the origin plus the site namespace behind nginx", () => {
		expect(
			socketUrl({ site_name: "crm.example.com", socketio_port: 9000, dev_server: false }, location)
		).toBe("https://crm.example.com/crm.example.com");
	});

	it("swaps in the realtime port on a dev server, dropping the site's own port", () => {
		expect(
			socketUrl(
				{ site_name: "crm.localhost", socketio_port: 9099, dev_server: true },
				{ origin: "http://crm.localhost:8099", protocol: "http:", hostname: "crm.localhost" }
			)
		).toBe("http://crm.localhost:9099/crm.localhost");
	});

	it("falls back to 9000 when the config names no port", () => {
		expect(
			socketUrl(
				{ site_name: "crm.localhost", socketio_port: 0, dev_server: true },
				{ origin: "http://crm.localhost:8099", protocol: "http:", hostname: "crm.localhost" }
			)
		).toBe("http://crm.localhost:9000/crm.localhost");
	});
});

describe("repairRooms", () => {
	it("rejoins every held room on each connect", () => {
		const emitted: unknown[][] = [];
		const handlers: Record<string, (...args: unknown[]) => void> = {};
		const socket = {
			emit: (...args: unknown[]) => void emitted.push(args),
			on: (event: string, handler: (...args: unknown[]) => void) => void (handlers[event] = handler),
			off: () => {},
		};
		repairRooms(socket);
		const release = subscribeToDoc(socket, "Lead", "L-1");
		handlers.connect();
		expect(emitted).toEqual([
			["doc_subscribe", "Lead", "L-1"],
			["doc_subscribe", "Lead", "L-1"],
		]);
		release();
		handlers.connect();
		expect(emitted).toHaveLength(3);
		expect(emitted[2]).toEqual(["doc_unsubscribe", "Lead", "L-1"]);
	});
});
