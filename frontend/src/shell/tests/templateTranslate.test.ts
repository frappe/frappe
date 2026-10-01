// @vitest-environment node
// A `template:` string calls `__` and `__n` with no import, as every component template does.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { afterAll, describe, expect, it, vi } from "vitest";
import { createSSRApp } from "vue";
import { renderToString } from "vue/server-renderer";
import { compileScript } from "../../../templateCompiler/compileScript.mjs";

vi.mock("@framework/ui/api", () => ({
  getTranslations: async () => ({ data: { "Save {0}": "Enregistrer {0}" } }),
}));

import { installTranslate, loadTranslations } from "@/i18n";

const folder = path.dirname(fileURLToPath(import.meta.url));
const scratch = path.join(folder, "../../../node_modules/.template-translate-test");

afterAll(() => fs.rmSync(scratch, { recursive: true, force: true }));

async function render(body: string) {
  const { code, errors } = compileScript(`export default {\n${body}\n}\n`);
  expect(errors).toEqual([]);
  fs.mkdirSync(scratch, { recursive: true });
  const file = path.join(scratch, `${Math.random().toString(36).slice(2)}.mjs`);
  fs.writeFileSync(file, code as string);
  const module = await import(/* @vite-ignore */ pathToFileURL(file).href);
  const app = createSSRApp(module.default);
  installTranslate(app);
  return renderToString(app);
}

describe("installTranslate", () => {
  it("gives a template: string __ with no import", async () => {
    await loadTranslations("v1", "fr");

    expect(await render(`template: "<p>{{ __('Save {0}', ['Deal']) }}</p>",`)).toBe(
      "<p>Enregistrer Deal</p>",
    );
  });

  it("gives a template: string __n with no import", async () => {
    const html = await render(`template: "<p>{{ __n('{0} task', '{0} tasks', 2, [2]) }}</p>",`);

    expect(html).toBe("<p>2 tasks</p>");
  });

  it("lets a setup() return named __ win over the global", async () => {
    const html = await render(
      `setup() { return { __: (text) => text.toUpperCase() } },\ntemplate: "<p>{{ __('save') }}</p>",`,
    );

    expect(html).toBe("<p>SAVE</p>");
  });
});
