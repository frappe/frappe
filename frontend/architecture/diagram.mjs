// Builds the desk architecture page from the code, layers.json and ARCHITECTURE.md.
// Usage: node frontend/architecture/diagram.mjs [--stdout | --out <file>]. Exits 1 when the check fails.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { buildGraph } from "./graph.mjs";
import { LayerCheck } from "./check.mjs";
import { conceptsOf, extensionsOf, flowsOf } from "./architectureDoc.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(here, "..", "..");

if (process.argv[1] === fileURLToPath(import.meta.url)) main();

export function buildDiagram(root = ROOT) {
  const read = (file) => fs.readFileSync(path.join(root, file), "utf8");
  const layerFile = JSON.parse(read("frontend/architecture/layers.json"));
  const doc = read(layerFile.architecture);
  const check = new LayerCheck(buildGraph(root), layerFile);
  const data = {
    commit: git(root, "rev-parse --short HEAD"),
    branch: git(root, "rev-parse --abbrev-ref HEAD"),
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
  return { html, check };
}

function main() {
  const { html, check } = buildDiagram();
  const outAt = process.argv.indexOf("--out");
  if (process.argv.includes("--stdout")) {
    process.stdout.write(html);
  } else {
    const out =
      outAt > 0
        ? path.resolve(process.argv[outAt + 1])
        : path.join(os.tmpdir(), "desk-architecture.html");
    fs.writeFileSync(out, html);
    console.error(
      `${check.boxes.length} folders, ${check.edges.length} edges -> ${out}`
    );
  }
  for (const line of check.report()) console.error(line);
  if (!check.passes) process.exitCode = 1;
}

function git(root, args) {
  try {
    return execFileSync("git", args.split(" "), {
      cwd: root,
      encoding: "utf8",
    }).trim();
  } catch {
    return "";
  }
}
