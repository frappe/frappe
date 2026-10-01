// A value one user keeps in this browser, under a name. A browser profile is shared and a
// choice is not, so each name holds one entry per user, in `localStorage`.

const PREFIX = "frappe:desk:";

type Stored = Record<string, unknown>;

export interface BrowserMemory<T> {
	/** What this user last kept under the name, or `undefined` if it fails `is`. */
	recall(): T | undefined;
	remember(value: T): void;
}

/** `formerKey` held this user's value alone before the name did; it is moved over once. */
export function browserMemory<T>(
	name: string,
	user: string,
	is: (value: unknown) => value is T,
	formerKey?: string
): BrowserMemory<T> {
	const key = PREFIX + name;

	function keep(value: unknown): boolean {
		return write(key, JSON.stringify({ ...readAll(key), [user]: value }));
	}

	function recall(): T | undefined {
		let kept = readAll(key)[user];
		const former = formerKey ? read(formerKey) : null;
		if (kept === undefined && former !== null) {
			kept = parse(former);
			// A value that does not parse is dropped; one that cannot be written stays put.
			if (kept === undefined || keep(kept)) remove(formerKey!);
		}
		return is(kept) ? kept : undefined;
	}

	return { recall, remember: keep };
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

function write(key: string, raw: string): boolean {
	try {
		localStorage.setItem(key, raw);
		return true;
	} catch {
		return false;
	}
}

function remove(key: string) {
	try {
		localStorage.removeItem(key);
	} catch {}
}
