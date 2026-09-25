// Which source is speaking right now: registration attributes new handlers,
// running attributes surface ops. "host" is the app's own bundled code.
export const HOST_SOURCE = "host";

let registering = HOST_SOURCE;
// Newest last; an async handler stays in until it settles, so an overlap cannot restore a stale name.
const running: string[] = [];

export function registeringSource() {
	return registering;
}

export function runningSource() {
	return running.at(-1) ?? HOST_SOURCE;
}

export async function withRegisteringSource(source: string, work: () => Promise<any>) {
	registering = source;
	try {
		await work();
	} finally {
		registering = HOST_SOURCE;
	}
}

/** Runs `work` as `source`; a promise it returns keeps the name until it settles. */
export function withRunningSource<T>(source: string, work: () => T): T {
	running.push(source);
	const done = () => void running.splice(running.lastIndexOf(source), 1);
	try {
		const result = work();
		if (result instanceof Promise) return result.finally(done) as T;
		done();
		return result;
	} catch (error) {
		done();
		throw error;
	}
}
