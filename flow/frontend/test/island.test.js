import assert from "node:assert/strict";
import test from "node:test";

import { JSDOM } from "jsdom";

const dom = new JSDOM("<body></body>", { url: "http://localhost/flow/s/S1" });
for (const name of ["window", "document", "location", "history"]) globalThis[name] = dom.window[name];

const { island, loadModule, transport } = await import("./helpers/components.js");
const { mount } = await loadModule("island.js");
const panel = await loadModule("panel.js");

// an element the island mounts into; it records the marks put on it
const target = () => {
	const marks = {};
	return { marks, toggleAttribute: (name, on) => (marks[name] = on) };
};
const last = () => island.mounts.at(-1);

test("in a page's panel the island loads boot before it mounts, opens the saved route on a memory history and reports each route", async () => {
	transport.answers["frappe.flow.api.boot"] = { user: "riya@example.com" };
	transport.calls.length = 0;
	const routes = [];
	const el = target();
	await mount(el, {
		props: { panel: "desk", path: "/s/S2", onNavigate: (path) => routes.push(path) },
	});
	const { options, router } = last();
	assert.equal(panel.inPanel, true);
	assert.equal(panel.panelHost, "desk");
	assert.deepEqual(transport.calls.map(([method]) => method), ["frappe.flow.api.boot"]);
	assert.equal(options.props.boot.user, "riya@example.com");
	assert.equal(options.history, null);
	assert.equal(el.marks["data-panel"], true);
	await router.isReady();
	assert.equal(router.currentRoute.value.fullPath, "/s/S2");
	await router.push("/s/S3");
	assert.deepEqual(routes.slice(-1), ["/s/S3"]);
	// the address bar is the page's
	assert.equal(location.pathname, "/flow/s/S1");
});

test("a panel whose boot fails mounts without it, leaving App to try again and say why", async () => {
	transport.answers["frappe.flow.api.boot"] = () => {
		throw new Error("down");
	};
	await mount(target(), { props: { panel: "app" } });
	assert.equal(last().options.props.boot, null);
	assert.equal(panel.panelHost, "app");
});

test("/flow mounts the island on the address, with the boot it rendered", async () => {
	transport.calls.length = 0;
	const el = target();
	await mount(el, { props: { boot: { user: "sam@example.com" } } });
	const { options, router } = last();
	assert.equal(panel.inPanel, false);
	assert.deepEqual(transport.calls, []);
	assert.equal(options.props.boot.user, "sam@example.com");
	assert.equal(el.marks["data-panel"], false);
	await router.push("/s/S9");
	assert.equal(location.pathname, "/flow/s/S9");
});
