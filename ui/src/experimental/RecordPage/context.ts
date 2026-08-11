// Which source is speaking right now: registration attributes new handlers,
// running attributes surface ops. "host" is the app's own bundled code.
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

export async function withRunningSource(source: string, work: () => Promise<any>) {
	const previous = running;
	running = source;
	try {
		await work();
	} finally {
		running = previous;
	}
}
