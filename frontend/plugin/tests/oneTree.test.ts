// @vitest-environment node
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { build, createServer, type ViteDevServer } from "vite";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import oneTree, {
  LINKED_UI,
  REAL_UI,
  frameworkPublishedFiles,
  outOfLinkedPackage,
} from "../oneTree.js";

const importer = `${LINKED_UI}/src/components/Phone/utils.ts`;

describe("a relative import that climbs out of the linked ui package", () => {
  it("resolves against the package's real place in the framework's tree", () => {
    expect(
      outOfLinkedPackage("../../../../frappe/geo/country_info.json", importer),
    ).toBe(`${REAL_UI}/../frappe/geo/country_info.json`.replace("ui/../", ""));
  });

  it("leaves a relative import inside the package to vite", () => {
    expect(outOfLinkedPackage("../Link/Link.vue", importer)).toBeUndefined();
  });

  it("leaves other importers alone", () => {
    expect(
      outOfLinkedPackage(
        "../../../../frappe/geo/country_info.json",
        `${REAL_UI}/src/x.ts`,
      ),
    ).toBeUndefined();
  });

  it("returns nothing for a file the tree does not have, so vite reports the miss", () => {
    expect(
      outOfLinkedPackage("../../../../frappe/geo/missing.json", importer),
    ).toBeUndefined();
  });
});

describe("a framework name published from a file", () => {
  const manifest = [
    {
      app: "frappe",
      source_dir: "/bench/apps/frappe/frappe",
      import_map: { vue: "vue", "frappe/i18n": "./frontend/i18n.js" },
    },
    { app: "crm", source_dir: "/bench/apps/crm/crm", runtime_deps: {} },
  ];
  const plugin = oneTree(manifest) as any;

  it("lists only the scoped file values", () => {
    expect(frameworkPublishedFiles(manifest)).toEqual({
      "frappe/i18n": "/bench/apps/frappe/frappe/frontend/i18n.js",
    });
  });

  it("resolves from an app's source without a declaration", async () => {
    expect(
      await plugin.resolveId(
        "frappe/i18n",
        "/bench/apps/crm/crm/frontend/lib/index.js",
      ),
    ).toBe("/bench/apps/frappe/frappe/frontend/i18n.js");
  });

  it("resolves from the framework's own contributed source", async () => {
    expect(
      await plugin.resolveId(
        "frappe/i18n",
        "/bench/apps/frappe/frappe/core/doctype/user/frontend/record.js",
      ),
    ).toBe("/bench/apps/frappe/frappe/frontend/i18n.js");
  });

  it("does not reach an importer outside every app's source, such as ui/", async () => {
    expect(
      await plugin.resolveId("frappe/i18n", `${REAL_UI}/src/components/x.ts`),
    ).toBeUndefined();
  });

  it("still leaves an undeclared bare name to vite", async () => {
    expect(
      await plugin.resolveId("vue", "/bench/apps/crm/crm/frontend/lib/index.js"),
    ).toBeUndefined();
  });
});

describe("a package an app declares", () => {
  const frontend = fileURLToPath(new URL("../..", import.meta.url));
  const shellFile = `${frontend}src/main.ts`;
  // Vite resolves from its root when the importer is not on disk, so the app file must exist.
  const appSource = mkdtempSync(join(tmpdir(), "one-tree-crm-"));
  const appFile = join(appSource, "record.js");
  writeFileSync(appFile, "");
  const manifest = [
    { app: "frappe", source_dir: frontend, runtime_deps: {} },
    {
      app: "crm",
      source_dir: appSource,
      runtime_deps: { vue: "*", "frappe-ui": "*" },
    },
  ];
  let server: ViteDevServer;

  const resolveFrom = async (source: string, importer: string) =>
    (await server.environments.client.pluginContainer.resolveId(source, importer))?.id;

  beforeAll(async () => {
    server = await createServer({
      configFile: false,
      root: frontend,
      logLevel: "silent",
      plugins: [oneTree(manifest)],
      resolve: { preserveSymlinks: true },
      server: { middlewareMode: true, hmr: false, watch: null },
      optimizeDeps: { noDiscovery: true, include: [] },
    });
  });

  afterAll(async () => {
    await server?.close();
    rmSync(appSource, { recursive: true });
  });

  it("resolves a package that exports only an import entry, such as frappe-ui", async () => {
    const shell = await resolveFrom("frappe-ui", shellFile);
    expect(shell).toBeTruthy();
    expect(await resolveFrom("frappe-ui", appFile)).toBe(shell);
  });

  it("gives the app the vue the shell gets, not the CommonJS entry", async () => {
    const shell = await resolveFrom("vue", shellFile);
    expect(shell).toMatch(/vue\.runtime\.esm-bundler\.js/);
    expect(await resolveFrom("vue", appFile)).toBe(shell);
  });

  it("does not resolve a package the app did not declare", async () => {
    expect(await resolveFrom("dompurify", appFile)).toBeUndefined();
  });

  it("resolves the same way in a build", async () => {
    const found: Record<string, string | undefined> = {};
    const probe = {
      name: "probe",
      resolveId: (id: string) => (id === "probe" ? "\0probe" : undefined),
      load: (id: string) => (id === "\0probe" ? "export {}" : undefined),
      async buildStart(this: any) {
        for (const source of ["frappe-ui", "vue"]) {
          found[`shell ${source}`] = (await this.resolve(source, shellFile))?.id;
          found[`app ${source}`] = (await this.resolve(source, appFile))?.id;
        }
        found["app dompurify"] = (await this.resolve("dompurify", appFile))?.id;
      },
    };
    await build({
      configFile: false,
      root: frontend,
      logLevel: "silent",
      plugins: [oneTree(manifest), probe],
      resolve: { preserveSymlinks: true },
      build: { write: false, rolldownOptions: { input: "probe" } },
    });

    expect(found["shell frappe-ui"]).toBeTruthy();
    expect(found["app frappe-ui"]).toBe(found["shell frappe-ui"]);
    expect(found["shell vue"]).toMatch(/vue\.runtime\.esm-bundler\.js/);
    expect(found["app vue"]).toBe(found["shell vue"]);
    expect(found["app dompurify"]).toBeUndefined();
  });
});
