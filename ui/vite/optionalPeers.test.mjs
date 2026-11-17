// node --test ui/vite/optionalPeers.test.mjs

import assert from "node:assert/strict";
import { test } from "node:test";

import frameworkUI, { OPTIONAL_PEERS, OPTIONAL_PREFIX } from "./index.js";

const plugin = frameworkUI().find((entry) => entry.name === "framework-ui-deps");
const importer = new URL("../src/components/Fields/templateLanguage.ts", import.meta.url).pathname;
const host = (resolved) => ({ resolve: async () => resolved });

test("a host that has lang-vue gets the real package", async () => {
	const real = { id: "/host/node_modules/@codemirror/lang-vue/index.js" };
	assert.equal(await plugin.resolveId.call(host(real), "@codemirror/lang-vue", importer), real);
});

test("a host that never installed lang-vue gets a stand-in with no language", async () => {
	const id = await plugin.resolveId.call(host(null), "@codemirror/lang-vue", importer);
	assert.equal(id, `${OPTIONAL_PREFIX}@codemirror/lang-vue`);
	assert.equal(plugin.load(id), OPTIONAL_PEERS["@codemirror/lang-vue"]);
	assert.match(plugin.load(id), /vueLanguage = undefined/);
});

test("any other missing package stays unresolved", async () => {
	assert.equal(await plugin.resolveId.call(host(null), "left-pad", importer), null);
});

test("a file outside the package is left alone", async () => {
	assert.equal(await plugin.resolveId.call(host(null), "@codemirror/lang-vue", "/host/src/main.js"), null);
});

test("a host without lang-javascript gets a stand-in that throws when evaluated", async () => {
	const id = await plugin.resolveId.call(host(null), "@codemirror/lang-javascript", importer);
	assert.equal(id, `${OPTIONAL_PREFIX}@codemirror/lang-javascript`);
	const source = plugin.load(id);
	assert.match(source, /export const javascriptLanguage/);
	assert.throws(() => new Function(source.replace(/^export const /gm, "var "))(), /Cannot find module/);
});
