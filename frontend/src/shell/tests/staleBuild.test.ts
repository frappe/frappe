// A lazy chunk that 404s after a build shows one Reload toast while the shell is mounted.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent } from "vue";

const fake = vi.hoisted(() => ({ toast: vi.fn() }));
vi.mock("frappe-ui", () => ({ toast: fake.toast }));

import { useStaleBuildNotice } from "../staleBuild";

const releases: Array<() => void> = [];

function mountShell() {
	const Shell = defineComponent({
		setup() {
			useStaleBuildNotice();
			return () => null;
		},
	});
	const app = createApp(Shell);
	app.mount(document.body.appendChild(document.createElement("div")));
	releases.push(() => app.unmount());
	return app;
}

// What Vite's preload helper dispatches when a dynamic import fails.
function failChunk() {
	const event = new Event("vite:preloadError");
	Object.assign(event, { payload: new TypeError("Failed to fetch dynamically imported module") });
	window.dispatchEvent(event);
}

describe("useStaleBuildNotice", () => {
	beforeEach(() => fake.toast.mockReset());
	afterEach(() => releases.splice(0).forEach((release) => release()));

	it("shows a persistent toast with a Reload action when a chunk fails", () => {
		mountShell();
		failChunk();

		expect(fake.toast).toHaveBeenCalledTimes(1);
		const [message, options] = fake.toast.mock.calls[0];
		expect(message).toBe("A new version is available");
		expect(options.duration).toBe(Infinity);
		expect(options.action.label).toBe("Reload");
	});

	it("gives every failure the same toast id, so a second chunk replaces the first", () => {
		mountShell();
		failChunk();
		failChunk();

		const ids = fake.toast.mock.calls.map(([, options]) => options.id);
		expect(new Set(ids).size).toBe(1);
	});

	it("reloads the page from the action and not before", () => {
		const reload = vi.fn();
		vi.stubGlobal("location", { reload });
		mountShell();
		failChunk();
		expect(reload).not.toHaveBeenCalled();

		fake.toast.mock.calls[0][1].action.onClick();

		expect(reload).toHaveBeenCalledTimes(1);
		vi.unstubAllGlobals();
	});

	it("listens only while the shell is mounted", () => {
		const app = mountShell();
		app.unmount();
		failChunk();

		expect(fake.toast).not.toHaveBeenCalled();
	});
});
