/**
 * Verify the island preset against a fixture app.
 *
 * The preset's output is a build, so this script runs one. It stages
 * `tests/fixture/` as a frontend inside a throwaway bench, runs the preset over
 * it, and reads the output back. It checks what the desk loader and the mount
 * contract depend on:
 *
 * - a self-contained ES module per entry
 * - chunks two entries share
 * - one stylesheet with preflight and every class the bundle applies
 * - assets.json keys in the `.island.js` and `.island.css` form
 * - an island that registers even when it is over budget
 *
 * This is a plain Node script, not a unit test, because the build pipeline is
 * under test.
 *
 * The preset builds on the app's own tooling, so the fixture borrows an
 * installed frontend's `node_modules`: Vite, Tailwind, frappe-ui and the rest.
 * Name any app frontend where `yarn install` ran.
 *
 * Usage:
 *   node ui/vite/island/tests/verify.mjs ../insights/frontend
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import zlib from "node:zlib";
import { fileURLToPath } from "node:url";

import { buildIslands } from "../index.js";
import { unscannedSources } from "../tailwind-scan.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.join(HERE, "fixture");
// ui/vite/island/tests → apps/frappe, which holds the `ui` package the fixture
// imports the mount contract from.
const FRAMEWORK_ROOT = path.resolve(HERE, "../../../..");

const ENTRIES = {
  island_fixture_panel: "src/islands/panel.js",
  island_fixture_badge: "src/islands/badge.js",
};

const failures = [];

const kb = (bytes) => `${(bytes / 1024).toFixed(1)} kB`;

const check = (ok, what, detail = "") => {
  console.log(
    `  ${ok ? "ok  " : "FAIL"} ${what}${detail ? `: ${detail}` : ""}`
  );
  if (!ok) failures.push(what);
};

const bench = stageBench(donorTree());
try {
  await run();
} finally {
  fs.rmSync(bench.root, { recursive: true, force: true });
}

if (failures.length) {
  console.error(`\n[island] ${failures.length} check(s) failed`);
  process.exit(1);
}
console.log("\n[island] preset verified");

async function run() {
  const island = {
    app: "fixtureapp",
    root: bench.frontend,
    entries: ENTRIES,
    production: true,
    tailwindPlugins: ["@tailwindcss/container-queries"],
  };

  await buildIslands(island);

  const assets = JSON.parse(fs.readFileSync(bench.assetsJson, "utf-8"));
  const panel = read(assets, "island_fixture_panel.island.js");
  const badge = read(assets, "island_fixture_badge.island.js");
  const css = read(assets, "island_fixture_panel.island.css");

  console.log("\nassets.json registration");
  check(
    !!panel,
    "each entry registers an .island.js key",
    assets["island_fixture_panel.island.js"]
  );
  check(
    !!badge,
    "including the second entry",
    assets["island_fixture_badge.island.js"]
  );
  check(
    !!css,
    "an .island.css key is registered",
    assets["island_fixture_panel.island.css"]
  );
  check(
    assets["island_fixture_badge.island.css"] ===
      assets["island_fixture_panel.island.css"],
    "both entries point at the app's one stylesheet"
  );
  check(
    assets["desk.bundle.js"] === "/assets/frappe/dist/js/desk.bundle.ABC.js",
    "a legacy .bundle.js key survives the merge"
  );

  console.log("\nJS output");
  check(/^\s*(import|export)\b/m.test(panel.text), "output is ESM");
  check(
    /export\s*\{[^}]*\bmount\b/.test(panel.text),
    "the mount export survives"
  );
  check(
    bareImports(panel.text).length === 0,
    "the island resolves nothing off the page",
    bareImports(panel.text).join(", ") || "no bare imports"
  );
  check(
    panel.text.includes("<path d="),
    "the lucide icon's SVG is in the bundle"
  );

  console.log("\nshared chunks");
  const shared = sharedChunks(panel, badge);
  check(
    shared.length > 0,
    "the two entries import chunks in common",
    shared.join(", ")
  );
  // Both entries render frappe-ui's Button on Vue, which is six figures of
  // bytes. If each carried its own copy, the two closures would add up to the
  // JS on disk instead of overlapping it.
  const closures = closureSize(panel) + closureSize(badge);
  const onDisk = weighJs(bench.outDir);
  check(
    closures > onDisk * 1.5,
    "each entry loads far more than it alone contributes",
    `${kb(closures)} loaded from ${kb(onDisk)} on disk`
  );

  console.log("\nCSS output");
  check(!/(^|[,}])\s*:root\b/.test(css.text), "no :root selector");
  check(!/(^|[,}])\s*html\b/.test(css.text), "no html selector");
  check(!/(^|[,}])\s*body\b/.test(css.text), "no body selector");
  check(css.text.includes(":host"), "document-level rules became :host");
  check(
    /box-sizing:\s*border-box/.test(css.text),
    "the sheet carries preflight"
  );
  check(/--ink-gray-\d:/.test(css.text), "the sheet carries the theme tokens");
  // The host registers the face, and it names it InterVariable. An island
  // asking for frappe-ui's `InterVar` matches nothing and draws system-ui.
  check(
    css.text.includes("InterVariable") && !/InterVar(?![\w-])/.test(css.text),
    "the sheet asks for the font the host registers"
  );
  check(css.text.includes(".panel-accent"), "app CSS is kept");
  check(
    css.text.includes(".bg-surface-gray-2"),
    "the app's utilities are there"
  );
  // The scan reaches every module the bundle is built from, frappe-ui's own
  // components among them. Their classes have no other sheet to come from.
  // Both are Button's, and neither is written anywhere in the fixture.
  check(
    css.text.includes(".text-ink-base") &&
      css.text.includes(".bg-surface-blue-4"),
    "frappe-ui's own classes are there"
  );
  check(
    /container-type:\s*inline-size/.test(css.text),
    "the app's Tailwind plugins run"
  );
  check(
    /@container[^{]*\{[^}]*grid-template-columns:\s*repeat\(3/.test(css.text),
    "a container-query variant compiles"
  );
  // The scan follows the bundle's imports. It therefore finds a class literal
  // in a helper module wherever that module sits, and it leaves the classes of
  // a module nothing imports out of the sheet.
  check(
    css.text.includes(".text-ink-red-7") &&
      css.text.includes(".text-ink-green-7"),
    "a class from an imported helper is scanned"
  );
  check(
    !css.text.includes(".text-ink-amber-7"),
    "a class from an unimported module is not"
  );

  // The backstop for `watch`, where the scan list is fixed at start-up.
  console.log("\nunscanned source");
  const frontend = fs.realpathSync(bench.frontend);
  const scanned = path.join(frontend, "src/islands/tone.js");
  const added = path.join(frontend, "src/islands/unused.js");
  const style = path.join(frontend, "src/islands/panel.css");
  const reported = unscannedSources({
    modules: [scanned, added, style],
    scanned: new Set([scanned]),
  });
  check(!reported.includes(scanned), "a scanned module is not reported");
  check(reported.includes(added), "a module added since the scan is");
  check(!reported.includes(style), "a stylesheet is not reported as unscanned");

  console.log("\nmeasured");
  console.log(`  panel  ${kb(panel.raw)} raw / ${kb(panel.gzip)} gzip`);
  console.log(`  badge  ${kb(badge.raw)} raw / ${kb(badge.gzip)} gzip`);
  console.log(`  CSS    ${kb(css.raw)} raw / ${kb(css.gzip)} gzip`);
  console.log(`  build  ${kb(weighJs(bench.outDir))} of JS on disk`);

  console.log("\nsize budget");
  // The budget warns, so the build must still finish and still register the
  // island. A build that stopped here would leave the assets on disk with no
  // assets.json entry, which is an island the desk loader cannot resolve.
  await buildIslands({ ...island, budget: 32 * 1024 });
  const overBudget = JSON.parse(fs.readFileSync(bench.assetsJson, "utf-8"));
  check(
    !!read(overBudget, "island_fixture_panel.island.js"),
    "a budget below what an island loads still registers the island"
  );
}

/* ------------------------------------------------------------------ staging */

/** The installed frontend the fixture borrows its tooling from. */
function donorTree() {
  const given = process.argv[2];
  if (!given)
    throw new Error(
      "island: name an installed app frontend to build against, e.g. " +
        "`node ui/vite/island/tests/verify.mjs ../insights/frontend`. The " +
        "preset runs on the app's own Vite, Tailwind and frappe-ui."
    );

  const donor = path.resolve(given);
  if (!fs.existsSync(path.join(donor, "node_modules")))
    throw new Error(
      `island: ${donor} has no node_modules. Run \`yarn install\` there first.`
    );

  return donor;
}

/**
 * A throwaway bench holding the fixture as an app frontend, so the preset
 * discovers its paths as it will in a real bench.
 */
function stageBench(donor) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "island-verify-"));
  const frontend = path.join(root, "apps/fixtureapp/frontend");
  const assetsJson = path.join(root, "sites/assets/assets.json");

  fs.mkdirSync(path.dirname(assetsJson), { recursive: true });
  fs.cpSync(FIXTURE, frontend, { recursive: true });
  mirrorModules(
    path.join(donor, "node_modules"),
    path.join(frontend, "node_modules")
  );

  // A legacy key, to prove the island build rewrites only its own.
  fs.writeFileSync(
    assetsJson,
    JSON.stringify(
      { "desk.bundle.js": "/assets/frappe/dist/js/desk.bundle.ABC.js" },
      null,
      4
    )
  );
  // Pin the preset to the throwaway bench. Nothing here may touch a real
  // sites/assets.
  process.env.FRAPPE_BENCH_ROOT = root;

  return {
    root,
    frontend,
    assetsJson,
    outDir: path.join(root, "sites/assets/fixtureapp/dist/island"),
  };
}

/**
 * The donor's `node_modules`, entry by entry, as a directory the fixture owns.
 *
 * A symlink to the whole tree would make the generated Tailwind config and
 * `.island` cache land in the donor app. Entry-level links also leave room for
 * `@framework/ui` to point at this checkout rather than whichever one the donor
 * links.
 */
function mirrorModules(from, to) {
  fs.mkdirSync(to, { recursive: true });

  for (const entry of fs.readdirSync(from)) {
    if (entry === "@framework") continue;
    fs.symlinkSync(path.join(from, entry), path.join(to, entry));
  }

  fs.mkdirSync(path.join(to, "@framework"), { recursive: true });
  fs.symlinkSync(
    path.join(FRAMEWORK_ROOT, "ui"),
    path.join(to, "@framework/ui")
  );
}

/* ------------------------------------------------------------------ reading */

function read(assets, key) {
  const url = assets[key];
  if (!url)
    throw new Error(
      `island: ${key} is not registered, so nothing can be read back`
    );

  const file = path.join(bench.root, "sites", url.replace(/^\//, ""));
  const buffer = fs.readFileSync(file);
  return {
    file,
    text: buffer.toString("utf-8"),
    raw: buffer.length,
    gzip: zlib.gzipSync(buffer, { level: 9 }).length,
  };
}

/** Every JS byte the build wrote. */
function weighJs(dir) {
  let raw = 0;
  for (const entry of fs.readdirSync(dir, {
    recursive: true,
    withFileTypes: true,
  }))
    if (entry.isFile() && entry.name.endsWith(".js"))
      raw += fs.statSync(path.join(entry.parentPath, entry.name)).size;
  return raw;
}

/** The bytes the browser loads to run one entry: the entry and its chunks. */
function closureSize(entry) {
  let raw = 0;
  const seen = new Set();
  const queue = [entry.file];

  while (queue.length) {
    const file = queue.pop();
    if (seen.has(file)) continue;
    seen.add(file);

    const source = fs.readFileSync(file, "utf-8");
    raw += Buffer.byteLength(source);
    queue.push(
      ...relativeImports(source).map((s) => path.resolve(path.dirname(file), s))
    );
  }

  return raw;
}

/** Chunks both entries import, by specifier. */
function sharedChunks(...entries) {
  const [first, ...rest] = entries.map(
    (entry) => new Set(relativeImports(entry.text))
  );
  return [...first].filter((name) => rest.every((other) => other.has(name)));
}

function relativeImports(source) {
  return specifiers(source).filter((s) => s.startsWith("."));
}

function bareImports(source) {
  return specifiers(source).filter((s) => !/^[./]/.test(s));
}

/** Every specifier the module imports, in source order. */
function specifiers(source) {
  return [
    ...source.matchAll(
      /\bfrom\s*['"]([^'"]+)['"]|\bimport\s*['"]([^'"]+)['"]/g
    ),
  ].map((match) => match[1] ?? match[2]);
}
