// Fails when a test file under frontend/ or ui/ matches no vitest `include` pattern.
import { execFileSync } from "node:child_process";
import { globSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative, resolve } from "node:path";

const FRONTEND = import.meta.dirname;
const ROOT = resolve(FRONTEND, "..");

main();

function main() {
  const run = new Set(testFilesVitestRuns());
  const onDisk = testFilesOnDisk();
  const missing = onDisk.filter((file) => !run.has(file));
  if (missing.length) {
    console.error(
      "These test files match no `include` pattern in frontend/vitest.config.js:"
    );
    for (const file of missing) console.error(`  ${relative(ROOT, file)}`);
    process.exit(1);
  }
  console.log(`All ${onDisk.length} test files run.`);
}

// Read from a file: the config logs a line to stdout before vitest prints its JSON.
function testFilesVitestRuns() {
  const dir = mkdtempSync(join(tmpdir(), "vitest-list-"));
  const output = join(dir, "files.json");
  execFileSync(
    join(FRONTEND, "node_modules/.bin/vitest"),
    ["list", "--filesOnly", `--json=${output}`],
    {
      cwd: FRONTEND,
      stdio: ["ignore", "ignore", "inherit"],
    }
  );
  const files = JSON.parse(readFileSync(output, "utf8")).map(
    (entry) => entry.file
  );
  rmSync(dir, { recursive: true });
  return files;
}

function testFilesOnDisk() {
  return globSync(
    "{frontend,ui}/**/*.{test,spec}.{js,jsx,ts,tsx,mjs,cjs,mts,cts}",
    {
      cwd: ROOT,
      exclude: (path) => path.includes("node_modules"),
    }
  ).map((file) => join(ROOT, file));
}
