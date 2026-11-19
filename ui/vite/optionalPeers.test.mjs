// vitest run ui/vite/optionalPeers.test.mjs (from frontend/)

import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import frameworkUI, { OPTIONAL_PEERS, OPTIONAL_PREFIX } from "./index.js";

const plugin = frameworkUI().find(
  (entry) => entry.name === "framework-ui-deps"
);
const importer = path.resolve(
  fileURLToPath(import.meta.url),
  "../../src/components/Fields/templateLanguage.ts"
);
const host = (resolved) => ({ resolve: async () => resolved });

describe("framework-ui-deps optional peers", () => {
  it("gives a host that has lang-vue the real package", async () => {
    const real = { id: "/host/node_modules/@codemirror/lang-vue/index.js" };
    expect(
      await plugin.resolveId.call(host(real), "@codemirror/lang-vue", importer)
    ).toBe(real);
  });

  it("gives a host without lang-vue a stand-in with no language", async () => {
    const id = await plugin.resolveId.call(
      host(null),
      "@codemirror/lang-vue",
      importer
    );
    expect(id).toBe(`${OPTIONAL_PREFIX}@codemirror/lang-vue`);
    expect(plugin.load(id)).toBe(OPTIONAL_PEERS["@codemirror/lang-vue"]);
    expect(plugin.load(id)).toMatch(/vueLanguage = undefined/);
  });

  it("gives a host without lang-javascript a stand-in that throws when evaluated", async () => {
    const id = await plugin.resolveId.call(
      host(null),
      "@codemirror/lang-javascript",
      importer
    );
    expect(id).toBe(`${OPTIONAL_PREFIX}@codemirror/lang-javascript`);
    const source = plugin.load(id);
    expect(source).toMatch(/export const javascriptLanguage/);
    expect(() =>
      new Function(source.replace(/^export const /gm, "var "))()
    ).toThrow(/Cannot find module/);
  });

  it("leaves any other missing package unresolved", async () => {
    expect(
      await plugin.resolveId.call(host(null), "left-pad", importer)
    ).toBeNull();
  });

  it("leaves a file outside the package alone", async () => {
    expect(
      await plugin.resolveId.call(
        host(null),
        "@codemirror/lang-vue",
        "/host/src/main.js"
      )
    ).toBeNull();
  });
});
