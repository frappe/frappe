import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { unrunTestFiles } from "../check-test-files.mjs";

let root: string;

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), "check-test-files-"));
});

afterEach(() => {
  rmSync(root, { recursive: true });
});

function touch(...paths: string[]) {
  return paths.map((path) => {
    const file = join(root, path);
    mkdirSync(dirname(file), { recursive: true });
    writeFileSync(file, "");
    return file;
  });
}

describe("unrunTestFiles", () => {
  it("names each test file under frontend/ and ui/ that vitest does not run", () => {
    const [run, unrunFrontend, unrunUi] = touch(
      "frontend/src/a/tests/a.test.ts",
      "frontend/walks/b.test.ts",
      "ui/src/c/c.spec.js"
    );

    expect(unrunTestFiles(root, [run])).toEqual([unrunFrontend, unrunUi]);
  });

  it("passes when vitest runs every test file", () => {
    const files = touch("frontend/src/tests/a.test.ts", "ui/src/tests/b.test.ts");

    expect(unrunTestFiles(root, files)).toEqual([]);
  });

  it("ignores node_modules, other folders and files that are not tests", () => {
    touch(
      "frontend/node_modules/pkg/x.test.ts",
      "ui/node_modules/pkg/y.test.js",
      "frappe/public/z.test.js",
      "frontend/src/testing.ts",
      "ui/src/tests/fixtures.ts"
    );

    expect(unrunTestFiles(root, [])).toEqual([]);
  });
});
