// Fails when a desk page's gzip JS moves more than the tolerance away from its baseline.
import { mkdtempSync, readFileSync, realpathSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";

const FRONTEND = import.meta.dirname;
const BUDGETS = join(FRONTEND, "speed-budgets.json");

export const PAGE_CHUNKS = {
  home: "src/pages/Home.vue",
  list: "src/pages/List.vue",
  record: "src/pages/Record.vue",
};

// Not `import.meta.main`: Node 24.0 and 24.1 lack it, and the check would pass unrun.
if (realpathSync(process.argv[1]) === fileURLToPath(import.meta.url))
  await main();

async function main() {
  const budgets = JSON.parse(readFileSync(BUDGETS, "utf8"));
  const outDir = mkdtempSync(join(tmpdir(), "desk-page-js-"));
  try {
    const manifest = await buildManifest(outDir);
    const sizes = pageJsKb(manifest, (file) =>
      readFileSync(join(outDir, file))
    );
    printSizes(sizes, budgets);
    const problems = jsSizeProblems(sizes, budgets);
    if (problems.length) {
      for (const problem of problems) console.error(problem);
      process.exitCode = 1;
    }
  } finally {
    rmSync(outDir, { recursive: true });
  }
}

async function buildManifest(outDir) {
  const { build } = await import("vite");
  await build({
    root: FRONTEND,
    logLevel: "error",
    build: { outDir, emptyOutDir: true, manifest: true },
  });
  return JSON.parse(readFileSync(join(outDir, ".vite/manifest.json"), "utf8"));
}

export function pageJsKb(manifest, read) {
  const entry = chunkFiles(manifest, "index.html");
  return Object.fromEntries(
    Object.entries(PAGE_CHUNKS).map(([page, source]) => {
      const files = new Set([...entry, ...chunkFiles(manifest, source)]);
      const bytes = [...files].reduce(
        (sum, file) => sum + gzipSync(read(file)).length,
        0
      );
      return [page, Math.round((bytes / 1024) * 10) / 10];
    })
  );
}

function chunkFiles(manifest, key, files = new Set()) {
  const chunk = manifest[key];
  if (!chunk) throw new Error(`${key} is not a chunk in the build manifest`);
  if (files.has(chunk.file)) return files;
  files.add(chunk.file);
  for (const imported of chunk.imports ?? [])
    chunkFiles(manifest, imported, files);
  return files;
}

export function jsSizeProblems(sizes, budgets) {
  const tolerance = budgets.jsToleranceKb;
  return Object.entries(sizes)
    .filter(([page, kb]) => kb > budgets[page].baseline.jsKb + tolerance)
    .map(
      ([page, kb]) =>
        `${page}: ${kb} KB of JS is more than ${tolerance} KB above its baseline of ` +
        `${budgets[page].baseline.jsKb} KB. Cut the JS, or raise the baseline in ` +
        `frontend/speed-budgets.json to ${kb}.`
    );
}

function printSizes(sizes, budgets) {
  console.table(
    Object.fromEntries(
      Object.entries(sizes).map(([page, kb]) => [
        page,
        {
          "gzip KB": kb,
          baseline: budgets[page].baseline.jsKb,
          budget: budgets[page].budget.jsKb,
        },
      ])
    )
  );
}
