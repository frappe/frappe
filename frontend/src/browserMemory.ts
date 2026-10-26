// A value one user keeps in this browser or tab, under a name. A browser profile is shared and
// a choice is not, so each name holds one entry per user.

const PREFIX = "frappe:desk:";

type Stored = Record<string, unknown>;
// Read on each call: the global itself throws in a sandboxed frame.
type Area = () => Storage;

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
	return memoryIn(() => localStorage, name, user, is, formerKey);
}

/** The same, in `sessionStorage`, so each tab keeps its own. */
export function tabMemory<T>(
	name: string,
	user: string,
	is: (value: unknown) => value is T
): BrowserMemory<T> {
	return memoryIn(() => sessionStorage, name, user, is);
}

function memoryIn<T>(
	area: Area,
	name: string,
	user: string,
	is: (value: unknown) => value is T,
	formerKey?: string
): BrowserMemory<T> {
	const key = PREFIX + name;

	function keep(value: unknown): boolean {
		return write(area, key, JSON.stringify({ ...readAll(area, key), [user]: value }));
	}

	function recall(): T | undefined {
		const kept = readAll(area, key)[user];
		if (kept !== undefined || !formerKey) return is(kept) ? kept : undefined;

		const former = read(area, formerKey);
		if (former === null) return undefined;
		// A former key may hold a bare string, which is not JSON.
		const moved = [parse(former), former].find(is);
		if (moved === undefined || keep(moved)) remove(area, formerKey);
		return moved;
	}

	return { recall, remember: keep };
}

function readAll(area: Area, key: string): Stored {
	const parsed = parse(read(area, key));
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
function read(area: Area, key: string): string | null {
	try {
		return area().getItem(key);
	} catch {
		return null;
	}
}

function write(area: Area, key: string, raw: string): boolean {
	try {
		area().setItem(key, raw);
		return true;
	} catch {
		return false;
	}
}

function remove(area: Area, key: string) {
	try {
		area().removeItem(key);
	} catch {}
}
