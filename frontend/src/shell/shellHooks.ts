// Each permitted app's shell hook, `<module>/frontend/shell.js`: its `setup(shell)` runs once per
// tab at idle after the shell's first paint, in the site's app order.
import { onMounted } from "vue";
import { registerAfterSave, type AfterSave } from "@/afterSave";
import { shellHookFiles } from "@/contributions/registry";
import { atIdle } from "./atIdle";

/** All a shell hook attaches through. */
export interface ShellHookApi {
	/** Runs `handler` after each save of a settings binding of `doctype`. */
	afterSave(doctype: string, handler: AfterSave): void;
}

type Setup = (shell: ShellHookApi) => unknown;

/** Runs the hooks of the `permitted` apps once, at idle after the shell mounts. */
export function useShellHooks(permitted: string[]) {
	const files = shellHookFiles.filter((file) => permitted.includes(file.app));
	if (!files.length) return;
	onMounted(() => atIdle(() => runAll(files)));
}

async function runAll(files: typeof shellHookFiles) {
	const results = await Promise.allSettled(files.map((file) => file.load()));
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
		run(app, setup as Setup);
	});
}

function run(app: string, setup: Setup) {
	const failed = (error: unknown) =>
		console.error(`[frappe] ${app}'s shell.js setup failed; it is skipped.`, error);
	try {
		Promise.resolve(setup(shellFor())).catch(failed);
	} catch (error) {
		failed(error);
	}
}

function shellFor(): ShellHookApi {
	return Object.freeze({
		afterSave: (doctype: string, handler: AfterSave) => void registerAfterSave(doctype, handler),
	});
}
