// node --test ui/vite/island/inputs.test.mjs

import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";

import { benchPaths } from "./assets.js";
import { islandsUnchanged, writeInputsStamp } from "./inputs.js";

const URL = "/assets/frappe/dist/page-island/notifications.island.abc.js";

/** A bench with one page island, built once and stamped. */
function builtBench() {
  const bench = fs.realpathSync(
    fs.mkdtempSync(path.join(os.tmpdir(), "island-inputs-"))
  );
  const write = (rel, text) => {
    fs.mkdirSync(path.dirname(path.join(bench, rel)), { recursive: true });
    fs.writeFileSync(path.join(bench, rel), text);
  };

  write("apps/frappe/island-toolchain/package.json", "{}");
  write("apps/frappe/island-toolchain/yarn.lock", "frappe-ui@1");
  write(
    "apps/frappe/island-toolchain/node_modules/frappe-ui/index.js",
    "export {}"
  );
  write(
    "apps/frappe/frappe/desk/page/notifications/notifications.island.js",
    "import './n.vue'"
  );
  write(
    "apps/frappe/frappe/desk/page/notifications/notifications.vue",
    "<template/>"
  );
  write("apps/erpnext/node_modules/chart-lib/index.js", "export {}");

  const root = path.join(bench, "apps/frappe/island-toolchain");
  const options = {
    app: "frappe",
    subdir: "page-island",
    root,
    entries: {
      "frappe.page.notifications": path.join(
        bench,
        "apps/frappe/frappe/desk/page/notifications/notifications.island.js"
      ),
    },
    production: true,
  };
  const paths = benchPaths(bench, "frappe", "page-island");

  write(`sites${URL}`, "built");
  const assets = { "frappe.page.notifications.island.js": URL };
  write("sites/assets/assets.json", JSON.stringify(assets));

  const moduleIds = [
    options.entries["frappe.page.notifications"],
    path.join(
      bench,
      "apps/frappe/frappe/desk/page/notifications/notifications.vue"
    ) + "?vue&type=script",
    path.join(root, "node_modules/frappe-ui/index.js"),
    path.join(bench, "apps/erpnext/node_modules/chart-lib/index.js"),
    "\0virtual:island.css",
  ];
  writeInputsStamp(
    { ...options, paths, mode: "production" },
    moduleIds,
    assets
  );

  return { bench, options, write };
}

test("unchanged inputs reuse the output", () => {
  const { options } = builtBench();
  assert.equal(islandsUnchanged(options), true);
});

test("an edited source file builds again", () => {
  const { options, write } = builtBench();
  write(
    "apps/frappe/frappe/desk/page/notifications/notifications.vue",
    "<template>x</template>"
  );
  assert.equal(islandsUnchanged(options), false);
});

test("a new page builds again", () => {
  const { bench, options, write } = builtBench();
  write("apps/erpnext/erpnext/manufacturing/page/bom/bom.island.js", "");
  options.entries["erpnext.page.bom"] = path.join(
    bench,
    "apps/erpnext/erpnext/manufacturing/page/bom/bom.island.js"
  );
  assert.equal(islandsUnchanged(options), false);
});

test("another mode builds again", () => {
  const { options } = builtBench();
  assert.equal(islandsUnchanged({ ...options, production: false }), false);
});

test("a new lockfile builds again", () => {
  const { options, write } = builtBench();
  write("apps/frappe/island-toolchain/yarn.lock", "frappe-ui@2");
  assert.equal(islandsUnchanged(options), false);
});

test("a missing assets.json entry builds again", () => {
  const { options, write } = builtBench();
  write("sites/assets/assets.json", "{}");
  assert.equal(islandsUnchanged(options), false);
});

test("no toolchain node_modules still reuses prebuilt output", () => {
  const { bench, options } = builtBench();
  fs.rmSync(path.join(bench, "apps/frappe/island-toolchain/node_modules"), {
    recursive: true,
  });
  assert.equal(islandsUnchanged(options), true);
});

test("output built on another bench path is reused", () => {
  const { bench, options } = builtBench();
  const moved = `${bench}-moved`;
  fs.cpSync(bench, moved, { recursive: true });
  const relocate = (file) => path.join(moved, path.relative(bench, file));

  assert.equal(
    islandsUnchanged({
      ...options,
      root: relocate(options.root),
      entries: Object.fromEntries(
        Object.entries(options.entries).map(([name, file]) => [
          name,
          relocate(file),
        ])
      ),
    }),
    true
  );
});

test("a missing toolchain folder builds instead of throwing", () => {
  const { bench, options } = builtBench();
  fs.rmSync(path.join(bench, "apps/frappe/island-toolchain"), {
    recursive: true,
  });
  assert.equal(islandsUnchanged(options), false);
});

test("new tailwind plugins build again", () => {
  const { options } = builtBench();
  assert.equal(
    islandsUnchanged({ ...options, tailwindPlugins: ["@tailwindcss/forms"] }),
    false
  );
});

test("an edited package outside the toolchain builds again", () => {
  const { options, write } = builtBench();
  write("apps/erpnext/node_modules/chart-lib/index.js", "export const v = 2");
  assert.equal(islandsUnchanged(options), false);
});
