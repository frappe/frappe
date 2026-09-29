// Builds the desk architecture page from the code, layers.json and ARCHITECTURE.md.
// Usage: node frontend/architecture/diagram.mjs [--stdout | --out <file>] [--flows].
// Exits 1 when a structure check fails. --flows also prints the files each flow reaches.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { StructureCheck } from "./structure.mjs";
import { conceptsOf, extensionsOf, flowsOf } from "./architectureDoc.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(here, "..", "..");

if (process.argv[1] === fileURLToPath(import.meta.url)) main();

export function buildDiagram(root = ROOT) {
  const read = (file) => fs.readFileSync(path.join(root, file), "utf8");
  const structure = new StructureCheck(root);
  const { layerFile, doc, layers: check } = structure;
  const data = {
    commit: git(root, "rev-parse --short HEAD"),
    branch: git(root, "rev-parse --abbrev-ref HEAD"),
    sourceBase: sourceBase(root),
    builtAt: new Date().toISOString().slice(0, 16).replace("T", " "),
    architecture: layerFile.architecture,
    layers: layerFile.layers.map((l) => ({
      ...l,
      concepts: conceptsOf(doc, l),
    })),
    boxes: check.boxes,
    edges: check.edges,
    knownBreaks: check.knownBreaks,
    loops: check.loops,
    flows: flowsOf(doc),
    extensions: extensionsOf(doc),
    unplaced: check.unplaced,
  };
  // A "</script>" or "<!--" inside the JSON would end or break the page's script.
  const json = JSON.stringify(data).replaceAll("<", "\\u003c");
  const scripts = ["shared.js", "panel.js", "layersView.js", "views.js"]
    .map((f) => read(`frontend/architecture/${f}`))
    .join("\n");
  const html = read("frontend/architecture/diagram.html")
    .replace("/*DATA*/null", () => json)
    .replace("/*SCRIPTS*/", () => scripts);
  return { html, structure };
}

function main() {
  const { html, structure } = buildDiagram();
  const { boxes, edges } = structure.layers;
  const outAt = process.argv.indexOf("--out");
  if (process.argv.includes("--stdout")) {
    process.stdout.write(html);
  } else {
    const out =
      outAt > 0
        ? path.resolve(process.argv[outAt + 1])
        : path.join(os.tmpdir(), "desk-architecture.html");
    fs.writeFileSync(out, html);
    console.error(`${boxes.length} folders, ${edges.length} edges -> ${out}`);
  }
  if (process.argv.includes("--flows"))
    for (const line of structure.flows.report()) console.error(line);
  for (const line of structure.report()) console.error(line);
  if (!structure.passes) process.exitCode = 1;
}

// Links go to the commit the page was built from, on the remote the branch tracks, else origin.
// Only GitHub's link format is known; any other forge gets plain paths.
export function sourceBase(root) {
  const branch = git(root, "rev-parse --abbrev-ref HEAD");
  const tracked = git(
    root,
    `for-each-ref --format=%(upstream:remotename) refs/heads/${branch}`
  );
  const remote =
    tracked ||
    (git(root, "remote").split("\n").includes("origin") ? "origin" : "");
  if (!remote) return null;
  const address = git(root, `remote get-url ${remote}`).replace(
    /^git@([^:]+):/,
    "https://$1/"
  );
  if (!address.startsWith("https://")) return null;
  const url = new URL(address);
  if (url.hostname !== "github.com") return null;
  const repo = url.pathname.replace(/\.git$/, "").replace(/\/$/, "");
  // Built from the host and path only, so a token in the remote address never reaches the page.
  return `https://${url.hostname}${repo}/blob/${git(root, "rev-parse HEAD")}/`;
}

function git(root, args) {
  return execFileSync("git", args.split(" "), {
    cwd: root,
    encoding: "utf8",
  }).trim();
}
