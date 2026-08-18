// Loads third-party frontend extensions: static ESM files listed in boot,
// imported sequentially in install order so registration order stays lawful.
// The unit of failure is the whole module — a 404, a throw or a hang logs a
// named error and the page renders with that source absent.
import { reactive } from "vue";
import { withRegisteringSource } from "./context";
import { reportCustomizationError } from "./reportError";

const IMPORT_TIMEOUT = 5000;

// The tripwire is a site-wide misconfiguration rather than any one app's bug, so
// it reports under its own name on the tier it breaks.
const IMPORT_MAP_SOURCE = "import-map";

export async function loadFrontendExtensions(entries: string[]) {
	if (!entries.length) return;
	await assertSharedSingletons();
	for (const [app, urls] of byApp(entries)) {
		for (const url of urls.filter(isStylesheet)) injectStylesheet(url);
		for (const url of urls.filter((entry) => !isStylesheet(entry))) {
			await withRegisteringSource(app, () => importExtension(app, url));
		}
	}
}

async function importExtension(app: string, url: string) {
	try {
		await withTimeout(import(/* @vite-ignore */ url), `${app} extension timed out`);
	} catch (error) {
		console.error(`[record-page] extension from '${app}' failed to load, skipped`, error);
		reportCustomizationError(error, { source: app, tier: "extension", event: "load" });
	}
}

// The tripwire ticket 05 §7 asks for: if the import map hands extensions a vue
// that is not the host's, every provide/inject seam is already broken. Nobody
// would ever see the console line, which is why it reports.
async function assertSharedSingletons() {
	try {
		const mapped = await import(/* @vite-ignore */ "vue");
		if (mapped.reactive !== reactive) {
			const message = "import map resolves a second vue; extensions will misbehave";
			console.error(`[record-page] ${message}`);
			reportTripwire(new Error(message));
		}
	} catch (error) {
		console.error("[record-page] shared deps missing from the import map", error);
		reportTripwire(error);
	}
}

function reportTripwire(error: unknown) {
	reportCustomizationError(error, {
		source: IMPORT_MAP_SOURCE,
		tier: "extension",
		event: "load",
	});
}

/** Boot order is install order; grouping keeps an app's css ahead of its js. */
function byApp(entries: string[]) {
	const groups = new Map<string, string[]>();
	for (const entry of entries) {
		const app = entry.split("/").filter(Boolean)[1] ?? "unknown";
		groups.set(app, [...(groups.get(app) ?? []), entry]);
	}
	return groups;
}

function isStylesheet(url: string) {
	return url.split("?")[0].endsWith(".css");
}

function injectStylesheet(url: string) {
	const link = document.createElement("link");
	link.rel = "stylesheet";
	link.href = url;
	document.head.appendChild(link);
}

function withTimeout(work: Promise<any>, message: string) {
	return Promise.race([
		work,
		new Promise((_, reject) => setTimeout(() => reject(new Error(message)), IMPORT_TIMEOUT)),
	]);
}
