// A value one user keeps in this browser, under a name. A browser profile is shared and a
// choice is not, so each name holds one entry per user, in `localStorage`.

const PREFIX = "frappe:desk:";

type Stored = Record<string, unknown>;

export interface BrowserMemory<T> {
	/** What this user last kept under the name, or `undefined`. Callers check its shape. */
	recall(): T | undefined;
	remember(value: T): void;
}

/** `formerKey` held this user's value alone before the name did; it is moved over once. */
export function browserMemory<T>(name: string, user: string, formerKey?: string): BrowserMemory<T> {
	const key = PREFIX + name;

	function remember(value: T) {
		write(key, JSON.stringify({ ...readAll(key), [user]: value }));
	}

	function recall(): T | undefined {
		const kept = readAll(key)[user];
		if (kept !== undefined || !formerKey) return kept as T | undefined;
		const former = parse(read(formerKey));
		if (former === undefined) return undefined;
		remember(former as T);
		remove(formerKey);
		return former as T;
	}

	return { recall, remember };
}

function readAll(key: string): Stored {
	const parsed = parse(read(key));
	return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as Stored) : {};
}

function parse(raw: string | null): unknown {
	try {
		return raw === null ? undefined : JSON.parse(raw);
	} catch {
		return undefined;
	}
}

// Storage throws in a sandboxed frame and when it is full. The value then lasts for this page.
function read(key: string): string | null {
	try {
		return localStorage.getItem(key);
	} catch {
		return null;
	}
}

function write(key: string, raw: string) {
	try {
		localStorage.setItem(key, raw);
	} catch {}
}

function remove(key: string) {
	try {
		localStorage.removeItem(key);
	} catch {}
}
