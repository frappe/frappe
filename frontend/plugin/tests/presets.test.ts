import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import resolveConfig from "tailwindcss/resolveConfig.js";
import { afterAll, describe, expect, it } from "vitest";
import { checkPresets, frameworkPreset, frameworkTheme, loadPresets } from "../presets.js";

const theme = frameworkTheme();

function refusal(loaded: { app: string; preset: object }[]) {
  try {
    checkPresets(loaded, theme);
  } catch (error) {
    return (error as Error).message;
  }
  throw new Error("passed");
}

const header =
  "The desk shell builds one stylesheet, which admits one value for each theme key. These presets conflict:";

describe("an app's Tailwind preset", () => {
  it("refuses a key outside theme and plugins, naming the app and the key", () => {
    const message = refusal([
      { app: "erpnext", preset: { safelist: ["prose"], theme: { extend: {} } } },
    ]);
    expect(message).toBe(
      `${header}\n  erpnext sets \`safelist\`; a preset carries \`theme\` and \`plugins\` only\n\nChange the presets and build again.`,
    );
  });

  it("refuses a plain theme key, which would replace the whole scale", () => {
    expect(
      refusal([{ app: "erpnext", preset: { theme: { spacing: { "1": "4px" } } } }]),
    ).toContain("erpnext sets `theme.spacing`; a preset writes under `theme.extend` only");
  });

  it("refuses a leaf the framework theme defines, showing the framework's value", () => {
    expect(
      refusal([
        {
          app: "erpnext",
          preset: { theme: { extend: { colors: { gray: { "100": "#eee" } } } } },
        },
      ]),
    ).toContain(
      `erpnext sets \`colors.gray.100\`, which the framework defines as ${JSON.stringify(theme.colors.gray[100])}`,
    );
  });

  it("refuses a framework leaf whose key holds a dot, such as spacing 0.5", () => {
    expect(
      refusal([{ app: "erpnext", preset: { theme: { extend: { spacing: { "0.5": "3px" } } } } }]),
    ).toContain(
      `erpnext sets \`spacing.0.5\`, which the framework defines as ${JSON.stringify(theme.spacing["0.5"])}`,
    );
  });

  it("names a whole scale the framework holds as an object, not by dumping it", () => {
    expect(
      refusal([{ app: "crm", preset: { theme: { extend: { colors: () => ({}) } } } }]),
    ).toContain("crm sets `colors`, which the framework defines as an object");
  });

  it("refuses a preset that is not an object", () => {
    expect(refusal([{ app: "crm", preset: (() => ({})) as any }])).toContain(
      "crm exports function; a preset is an object",
    );
  });

  it("refuses one leaf two apps write with different values, naming each", () => {
    expect(
      refusal([
        { app: "crm", preset: { theme: { extend: { colors: { brand: "#a00000" } } } } },
        { app: "erpnext", preset: { theme: { extend: { colors: { brand: "#0000b0" } } } } },
      ]),
    ).toContain('colors.brand: crm wants "#a00000", erpnext wants "#0000b0"');
  });

  it("prints a function value as a function", () => {
    expect(
      refusal([
        { app: "crm", preset: { theme: { extend: { colors: { brand: () => "#a00000" } } } } },
        { app: "erpnext", preset: { theme: { extend: { colors: { brand: "#0000b0" } } } } },
      ]),
    ).toContain('colors.brand: crm wants a function, erpnext wants "#0000b0"');
  });

  it("passes two apps writing one leaf with an equal value, and different leaves under one parent", () => {
    const loaded = checkPresets(
      [
        { app: "crm", preset: { theme: { extend: { colors: { brand: "#a00000", "crm-ink": "#111" } } } } },
        { app: "erpnext", preset: { theme: { extend: { colors: { brand: "#a00000", "erp-ink": "#222" } } } } },
      ],
      theme,
    );
    const resolved = resolveConfig({ presets: loaded.map(({ preset }) => preset) }).theme as any;
    expect(resolved.colors["crm-ink"]).toBe("#111");
    expect(resolved.colors["erp-ink"]).toBe("#222");
  });

  it("wraps every preset with presets: [], so the framework's scale survives", () => {
    const preset = { theme: { extend: { colors: { x: "#000" } } } };
    const bare = resolveConfig({ presets: [frameworkPreset(), preset] }).theme as any;
    expect(bare.borderRadius["4"]).toBeUndefined();
    const [{ preset: wrapped }] = checkPresets([{ app: "crm", preset }], theme);
    const kept = resolveConfig({ presets: [frameworkPreset(), wrapped] }).theme as any;
    expect(kept.borderRadius["4"]).toBe(theme.borderRadius["4"]);
    expect(kept.colors.x).toBe("#000");
  });
});

describe("loading a preset from an app", () => {
  const bench = mkdtempSync(join(tmpdir(), "presets-"));
  afterAll(() => rmSync(bench, { recursive: true, force: true }));

  function app(name: string, type: string | undefined, source: string) {
    const root = join(bench, name);
    mkdirSync(join(root, name, "frontend"), { recursive: true });
    writeFileSync(join(root, "package.json"), JSON.stringify(type ? { type } : {}));
    writeFileSync(join(root, name, "frontend", "tailwind.preset.js"), source);
    return join(root, name);
  }

  it("loads an export default preset under a \"type\": \"module\" repo, from any app on the bench, and skips one with none", () => {
    const sourceDirs = [
      app("crm", "module", 'export default { theme: { extend: { colors: { "crm-ink": "#111" } } } };'),
      app("hrms", undefined, 'export default { theme: { extend: { colors: { "hrms-ink": "#222" } } } };'),
      join(bench, "erpnext", "erpnext"),
    ];
    const loaded = loadPresets(sourceDirs, theme);
    expect(loaded.map(({ app }) => app)).toEqual(["crm", "hrms"]);
    expect(loaded[0].preset).toEqual({
      theme: { extend: { colors: { "crm-ink": "#111" } } },
      presets: [],
    });
  });
});
