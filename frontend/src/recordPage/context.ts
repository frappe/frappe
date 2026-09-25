// Which source is speaking right now: registration attributes new handlers,
// running attributes surface ops. "host" is the app's own bundled code.
import { settle } from "./steps";

export const HOST_SOURCE = "host";

let registering = HOST_SOURCE;
let running = HOST_SOURCE;

export function registeringSource() {
	return registering;
}

export function runningSource() {
	return running;
}

export async function withRegisteringSource(source: string, work: () => Promise<any>) {
	registering = source;
	try {
		await work();
	} finally {
		registering = HOST_SOURCE;
	}
}

/** Runs `work` as `source`; synchronous work finishes, and is attributed, before this returns. */
export function withRunningSource<T>(source: string, work: () => T): T {
	const previous = running;
	running = source;
	return settle(work, () => (running = previous));
}
