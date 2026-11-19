// The order this person last opened the apps in, kept in this browser for the app switcher.
import { browserMemory, type BrowserMemory } from "@/browserMemory";
import type { Boot } from "@/boot";

const LIMIT = 20;

const isNames = (value: unknown): value is string[] =>
	Array.isArray(value) && value.every((name) => typeof name === "string");

let memory: { user: string; held: BrowserMemory<string[]> } | null = null;

function memoryOf(boot: Boot) {
	const user = boot.session.user.name;
	if (memory?.user === user) return memory.held;
	const held = browserMemory("app-use", user, isNames);
	memory = { user, held };
	return held;
}

/** Puts the app this page belongs to first; the index belongs to none. */
export function recordAppUse(boot: Boot) {
	if (!boot.app) return;
	const held = memoryOf(boot);
	held.remember([boot.app, ...(held.recall() ?? []).filter((name) => name !== boot.app)].slice(0, LIMIT));
}

/** App names, the last opened first. */
export function appsUsed(boot: Boot): string[] {
	return memoryOf(boot).recall() ?? [];
}
