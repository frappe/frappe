// node --test ui/vite/island/toolchain.test.mjs

import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";

import { installToolchain } from "./toolchain.js";

test("a node_modules from an older lockfile installs again", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "island-toolchain-"));
  fs.writeFileSync(
    path.join(root, "package.json"),
    JSON.stringify({ name: "toolchain", version: "0.0.0", private: true })
  );
  fs.writeFileSync(path.join(root, "yarn.lock"), "");
  fs.mkdirSync(path.join(root, "node_modules"));

  installToolchain(root);

  assert.ok(fs.existsSync(path.join(root, "node_modules", ".yarn-integrity")));
  fs.rmSync(root, { recursive: true });
});
