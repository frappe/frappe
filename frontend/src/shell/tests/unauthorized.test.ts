// The refusal the shell mounts when boot answers 401 or 403: its one link never leads back to the index's own refusal.
import { afterEach, describe, expect, it } from "vitest";
import { createApp, type App } from "vue";

import Unauthorized from "../Unauthorized.vue";

let app: App | undefined;

function mountAt(path: string): HTMLAnchorElement {
	window.history.replaceState(null, "", path);
	const host = document.createElement("div");
	document.body.appendChild(host);
	app = createApp(Unauthorized);
	app.mount(host);
	return host.querySelector("a")!;
}

afterEach(() => {
	app?.unmount();
	document.body.innerHTML = "";
	window.history.replaceState(null, "", "/");
});

describe("Unauthorized", () => {
	it("links an app's refusal back to the index", () => {
		expect(mountAt("/apps/crm").getAttribute("href")).toBe("/apps");
	});

	it("links the index's own refusal to /me, never to /apps", () => {
		expect(mountAt("/apps").getAttribute("href")).toBe("/me");
		app?.unmount();
		expect(mountAt("/apps/").getAttribute("href")).toBe("/me");
	});
});
