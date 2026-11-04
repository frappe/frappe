// Each permitted app's shell hook, `<module>/frontend/shell.js`: its `setup(shell)` runs once per
// tab at idle after the shell's first paint, in the site's app order.
import { onMounted, shallowReactive, type Component } from "vue";
import { registerAfterSave, type AfterSave } from "@/afterSave";
import type { ShellHook } from "@/boot";
import { shellHookFiles } from "@/contributions/registry";
import { atIdle } from "./atIdle";
import type { Shell } from "./shellActs";
import type { StandingWindow, StandingWindowHandle, StandingWindowOptions } from "./standingWindows";

/** What a shell hook's `setup` receives: the whole `Shell` an act's `run` gets, and what attaches the app's hooks. */
export interface ShellHookApi extends Shell {
	/** Runs `handler` after each save of a settings binding of `doctype`. */
	afterSave(doctype: string, handler: AfterSave): void;
	/** Mounts the app's one standing window, closed; a second call warns and returns nothing. */
	window(component: Component, options?: StandingWindowOptions): StandingWindowHandle | undefined;
}

type Setup = (shell: ShellHookApi) => unknown;
type Attach = (
	app: string,
	title: string,
	component: Component,
	options?: StandingWindowOptions
) => StandingWindowHandle | undefined;

/** Runs the `permitted` apps' hooks once, at idle after the shell mounts; gives their windows. */
export function useShellHooks(permitted: ShellHook[], shell: Shell) {
	const windows = shallowReactive<StandingWindow[]>([]);
	const files = shellHookFiles.filter((file) => permitted.some((hook) => hook.app === file.app));
	if (files.length) onMounted(() => atIdle(() => runAll(files, permitted, windows, shell)));
	return windows;
}

async function runAll(
	files: typeof shellHookFiles,
	permitted: ShellHook[],
	windows: StandingWindow[],
	shell: Shell
) {
	// The row's attach code loads here, so pages without a shell hook never carry it.
	const [results, { attachWindow }] = await Promise.all([
		Promise.allSettled(files.map((file) => file.load())),
		import("./standingWindows"),
	]);
	const order = permitted.map((hook) => hook.app);
	results.forEach((result, index) => {
		const { app } = files[index];
		if (result.status === "rejected") {
			console.error(`[frappe] ${app}'s shell.js did not load; it is skipped.`, result.reason);
			return;
		}
		const { setup } = result.value;
		if (typeof setup !== "function") {
			console.error(`[frappe] ${app}'s shell.js exports no setup function; it is skipped.`);
			return;
		}
		const title = permitted.find((hook) => hook.app === app)!.title;
		const attach: Attach = (...args) => attachWindow(windows, order, ...args);
		run(app, setup as Setup, shellFor(shell, app, title, attach));
	});
}

function run(app: string, setup: Setup, shell: ShellHookApi) {
	const failed = (error: unknown) =>
		console.error(`[frappe] ${app}'s shell.js setup failed; it is skipped.`, error);
	try {
		Promise.resolve(setup(shell)).catch(failed);
	} catch (error) {
		failed(error);
	}
}

function shellFor(shell: Shell, app: string, title: string, attach: Attach): ShellHookApi {
	return Object.freeze({
		...shell,
		afterSave: (doctype: string, handler: AfterSave) => void registerAfterSave(doctype, handler),
		window: (component: Component, options?: StandingWindowOptions) =>
			attach(app, title, component, options),
	});
}
