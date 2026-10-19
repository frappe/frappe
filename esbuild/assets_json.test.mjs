// node --test esbuild/assets_json.test.mjs

import assert from "node:assert/strict";
import fs from "node:fs";
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";

const { update_assets_json } = createRequire(import.meta.url)(
  "./assets_json.js"
);

function assets_json(contents) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "assets-json-"));
  const file = path.join(dir, "assets.json");
  fs.writeFileSync(file, JSON.stringify(contents));
  return file;
}

test("a write waits for the one holding the lock, and keeps its keys", async () => {
  const file = assets_json({ "desk.bundle.js": "/old.js" });
  fs.mkdirSync(file + ".lock");

  const island = update_assets_json(file, (current) => ({
    ...current,
    "x.island.js": "/x.js",
  }));
  await new Promise((resolve) => setTimeout(resolve, 100));
  assert.deepEqual(JSON.parse(fs.readFileSync(file, "utf-8")), {
    "desk.bundle.js": "/old.js",
  });

  fs.writeFileSync(file, JSON.stringify({ "desk.bundle.js": "/new.js" }));
  fs.rmSync(file + ".lock", { recursive: true });
  await island;

  assert.deepEqual(JSON.parse(fs.readFileSync(file, "utf-8")), {
    "desk.bundle.js": "/new.js",
    "x.island.js": "/x.js",
  });
  assert.equal(fs.existsSync(file + ".lock"), false);
});

test("a failed update frees the lock", async () => {
  const file = assets_json({});
  await assert.rejects(
    update_assets_json(file, () => {
      throw new Error("taken");
    }),
    /taken/
  );
  assert.equal(fs.existsSync(file + ".lock"), false);
});

test("a missing file starts empty, and an unreadable one is left as it is", async () => {
  const file = path.join(
    fs.mkdtempSync(path.join(os.tmpdir(), "assets-json-")),
    "assets.json"
  );
  const { previous } = await update_assets_json(file, () => ({
    "a.js": "a.1.js",
  }));
  assert.deepEqual(previous, {});

  fs.writeFileSync(file, "{");
  await assert.rejects(
    update_assets_json(file, () => ({})),
    SyntaxError
  );
  assert.equal(fs.readFileSync(file, "utf-8"), "{");
  assert.equal(fs.existsSync(file + ".lock"), false);
});
