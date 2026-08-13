// The import surface as executable claims (wayfinder tickets 23, 26). The rule
// the editor enforces has to be the rule the blob-module loader enforces, so
// these are written from what the import map actually publishes.
import { describe, expect, it } from "vitest";
import { SHARED_DEPS, unresolvableImports } from "../importLint";

describe("unresolvableImports", () => {
  it("accepts every shared dep, in every import form", () => {
    const source = [
      `import { ref } from "vue"`,
      `import { useRoute } from 'vue-router'`,
      `import { toast, Button } from "frappe-ui"`,
      `import "@framework/ui"`,
      `export { FormLayout } from "@framework/ui"`,
      `const lazy = await import("frappe-ui")`,
    ].join("\n");
    expect(unresolvableImports(source)).toEqual([]);
  });

  it("names the four in one place, shared with the reference panel", () => {
    expect([...SHARED_DEPS]).toEqual([
      "vue",
      "vue-router",
      "frappe-ui",
      "@framework/ui",
    ]);
  });

  it("reports an unlisted package", () => {
    expect(unresolvableImports(`import dayjs from "dayjs"`)).toEqual(["dayjs"]);
  });

  // The map has no trailing-slash entries, so a subpath of a listed dep is as
  // unresolvable as an unlisted one — the trap this lint exists to catch.
  it("reports a subpath of a listed dep", () => {
    const source = [
      `import { CodeEditor } from "frappe-ui/code-editor"`,
      `import { PageScriptEditor } from "@framework/ui/experimental"`,
    ].join("\n");
    expect(unresolvableImports(source)).toEqual([
      "frappe-ui/code-editor",
      "@framework/ui/experimental",
    ]);
  });

  it("reports a relative path, which has nothing to be relative to", () => {
    expect(unresolvableImports(`import x from "./helpers"`)).toEqual([
      "./helpers",
    ]);
  });

  it("reports each bad specifier once, in the order it was typed", () => {
    const source = [
      `import a from "dayjs"`,
      `import b from "lodash"`,
      `import c from "dayjs"`,
    ].join("\n");
    expect(unresolvableImports(source)).toEqual(["dayjs", "lodash"]);
  });

  it("ignores imports inside comments", () => {
    const source = [
      `// import dayjs from "dayjs"`,
      `/* import lodash from "lodash" */`,
      `import { ref } from "vue"`,
    ].join("\n");
    expect(unresolvableImports(source)).toEqual([]);
  });

  it("does not treat a // inside a string as starting a comment", () => {
    const source = [
      `const url = "https://example.com"`,
      `import dayjs from "dayjs"`,
    ].join("\n");
    expect(unresolvableImports(source)).toEqual(["dayjs"]);
  });

  it("says nothing about a script with no imports", () => {
    expect(unresolvableImports(`export default { refresh(page) {} }`)).toEqual(
      [],
    );
  });

  it("does not report the word import inside a string", () => {
    expect(
      unresolvableImports(`const help = 'import from "dayjs" to fail'`),
    ).toEqual([]);
  });
});
