// Fails when a test file under frontend/ or ui/ matches no vitest `include` pattern.
import { execFileSync } from "node:child_process";
import {
  globSync,
  mkdtempSync,
  readFileSync,
  realpathSync,
  rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const FRONTEND = import.meta.dirname;

// Not `import.meta.main`: Node 24.0 and 24.1 lack it, and the check would pass unrun.
if (realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) main();

function main() {
  const root = resolve(FRONTEND, "..");
  const missing = unrunTestFiles(root, testFilesVitestRuns());
  if (missing.length) {
    console.error(
      "These test files match no `include` pattern in frontend/vitest.config.js:"
    );
    for (const file of missing) console.error(`  ${relative(root, file)}`);
    process.exit(1);
  }
  console.log("Every test file runs.");
}

export function unrunTestFiles(root, run) {
  const runs = new Set(run);
  return testFilesOnDisk(root).filter((file) => !runs.has(file));
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

function testFilesOnDisk(root) {
  return globSync(
    "{frontend,ui}/**/*.{test,spec}.{js,jsx,ts,tsx,mjs,cjs,mts,cts}",
    {
      cwd: root,
      exclude: (path) => path.includes("node_modules"),
    }
  )
    .map((file) => join(root, file))
    .sort();
}
