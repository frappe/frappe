// Fails when a test file under `frontend/` or `ui/` is not one vitest runs. Each `ui/`
// folder was once listed by hand in `vitest.config.js`, and 50 test files went unrun.
import { execFileSync } from "node:child_process";
import { mkdtempSync, readdirSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative, resolve } from "node:path";

const FRONTEND = import.meta.dirname;
const ROOT = resolve(FRONTEND, "..");
const TEST_FILE = /\.(test|spec)\.[cm]?[jt]sx?$/;

main();

function main() {
  const run = new Set(testFilesVitestRuns());
  const onDisk = ["frontend", "ui"].flatMap((dir) =>
    testFilesIn(join(ROOT, dir))
  );
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

function testFilesVitestRuns() {
  const output = join(
    mkdtempSync(join(tmpdir(), "vitest-list-")),
    "files.json"
  );
  execFileSync(
    join(FRONTEND, "node_modules/.bin/vitest"),
    ["list", "--filesOnly", `--json=${output}`],
    {
      cwd: FRONTEND,
      stdio: "ignore",
    }
  );
  return JSON.parse(readFileSync(output, "utf8")).map((entry) => entry.file);
}

function testFilesIn(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      return entry.name === "node_modules" || entry.name.startsWith(".")
        ? []
        : testFilesIn(path);
    }
    return TEST_FILE.test(entry.name) ? [path] : [];
  });
}
