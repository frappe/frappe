// An app's global acts from its `acts.js`: imported at idle after the shell's first paint, and
// joined to the shell surface under the app's name, as `shell.<app>.<item>`.
import { onMounted, shallowRef } from "vue";
import type { ActItem } from "@/acts/dispatcher";
import { actsFiles } from "@/contributions/registry";

interface AppActs {
	/** Each app act as the shell surface holds it, named `<app>.<item>`. */
	items: () => ActItem[];
	/** A promise until every app's acts are in, which starts the import if it has not started; then nothing. */
	pending: () => Promise<void> | undefined;
}

/** The app acts for the shell's life. */
export function useAppActs(): AppActs {
	const loaded = shallowRef<Map<string, ActItem> | null>(actsFiles.length ? null : new Map());
	let loading: Promise<void> | undefined;
	const load = () => (loading ??= importAll().then((all) => void (loaded.value = all)));
	onMounted(() => atIdle(load));

	return {
		items: () =>
			[...(loaded.value ?? new Map())].map(([name, item]) => ({ ...item, name })),
		pending: () => (loaded.value ? undefined : load()),
	};
}

/** Every active app's acts by their name on the surface. */
async function importAll(): Promise<Map<string, ActItem>> {
	const files = [...actsFiles];
	const results = await Promise.allSettled(files.map((file) => file.load()));
	const all = new Map<string, ActItem>();
	results.forEach((result, index) => {
		const { app } = files[index];
		if (result.status === "rejected") {
			console.error(`[frappe] ${app}'s acts.js did not load; it adds no act.`, result.reason);
			return;
		}
		for (const item of actsOf(app, result.value.default)) {
			const name = `${app}.${item.name}`;
			if (all.has(name)) warn(`${app} ships two acts named '${item.name}'; the later one is used.`);
			all.set(name, item);
		}
	});
	return all;
}

function actsOf(app: string, exported: unknown): ActItem[] {
	if (!Array.isArray(exported)) {
		warn(`${app}'s acts.js has no list as its default export; it adds no act.`);
		return [];
	}
	return exported.filter((item) => validAct(app, item));
}

/** A named item with `run`, whose right, if any, is `{ doctype, ptype }`. */
function validAct(app: string, item: unknown): item is ActItem {
	const act = item as Partial<ActItem> | null;
	if (typeof act?.name !== "string" || typeof act.run !== "function") {
		warn(`${app}'s acts.js holds an entry with no name or no run; it is ignored.`);
		return false;
	}
	if (typeof act.right === "string") {
		warn(`shell.${app}.${act.name} is ignored: a shell act's right is { doctype, ptype }.`);
		return false;
	}
	return true;
}

// Safari has no `requestIdleCallback`.
function atIdle(work: () => unknown) {
	requestAnimationFrame(() => {
		if (typeof requestIdleCallback === "function") requestIdleCallback(() => void work());
		else setTimeout(() => void work());
	});
}

function warn(message: string) {
	console.warn(`[frappe] ${message}`);
}
