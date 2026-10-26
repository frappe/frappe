// Checks that each name exported across a folder boundary is in the concept table of the layer
// that defines it. knownUnlisted in layers.json holds today's gaps; the list may only shrink.
// A ui/ name is public when a public entry exports it and code outside ui/ imports it. Any
// other ui/ name is internal: it never gets a concept row, so it is counted apart from gaps.

import path from "node:path";
import { conceptsOf } from "./architectureDoc.mjs";

export class ConceptCheck {
  constructor(jsFiles, layerOf, doc, layerFile, uiEntries) {
    this.files = jsFiles;
    this.layerOf = layerOf;
    this.listed = listedNames(doc, layerFile.layers);
    this.known = layerFile.knownUnlisted;
    this.unlisted = this.findUnlisted();
    this.publicUi = this.findPublicUi(uiEntries);
  }

  isInternal(file, name) {
    return file.startsWith("ui/") && !this.publicUi.has(`${file}#${name}`);
  }

  summary() {
    const known = Object.entries(this.known).flatMap(([file, names]) =>
      names.map((n) => [file, n])
    );
    const internal = known.filter(([file, n]) => this.isInternal(file, n));
    const gaps = known.filter(([file, n]) => !this.isInternal(file, n));
    const uiNames = count(internal, "ui/ names");
    return [
      `GAPS       ${count(gaps)}: no concept row yet`,
      `INTERNAL   ${uiNames}: not public, so no concept row`,
    ];
  }

  get newUnlisted() {
    return this.pairs(this.unlisted).filter(
      ([file, name]) => !this.known[file]?.includes(name)
    );
  }

  // A known gap that is listed now, or no longer crosses a folder, must leave knownUnlisted.
  get fixedUnlisted() {
    const now = Object.fromEntries(this.unlisted);
    return Object.entries(this.known).flatMap(([file, names]) =>
      names.filter((n) => !now[file]?.has(n)).map((n) => [file, n])
    );
  }

  get passes() {
    return !this.newUnlisted.length && !this.fixedUnlisted.length;
  }

  report() {
    return [
      ...this.newUnlisted.map(([file, name]) =>
        this.isInternal(file, name)
          ? `NOT PUBLIC ${name} (${file}): gets no concept row; keep it in its folder or add it to knownUnlisted`
          : `NO CONCEPT ${name} (${file}): add it to layer ${this.layerOf(
              file
            )}'s concept table`
      ),
      ...this.fixedUnlisted.map(
        ([file, name]) =>
          `LISTED     ${name} (${file}): remove it from knownUnlisted`
      ),
    ];
  }

  // Each imported or re-exported name, traced to the file that defines it.
  findUnlisted() {
    const unlisted = new Map();
    for (const [file, info] of this.files) {
      for (const imp of info.imports) {
        if (!imp.target || path.dirname(imp.target) === path.dirname(file))
          continue;
        for (const [home, concept] of this.namesTaken(imp)) {
          const layer = this.layerOf(home);
          if (!layer || this.listed.get(layer)?.has(concept)) continue;
          if (!unlisted.has(home)) unlisted.set(home, new Set());
          unlisted.get(home).add(concept);
        }
      }
    }
    return new Map([...unlisted].sort(([a], [b]) => a.localeCompare(b)));
  }

  findPublicUi(uiEntries) {
    const exported = new Set();
    for (const entry of uiEntries.filter((e) => this.files.has(e))) {
      const names = this.exportsOf(entry);
      if (
        entry.endsWith(".vue") ||
        this.files.get(entry).exports.has("default")
      )
        names.add("default");
      for (const name of names)
        exported.add(this.conceptOf(entry, name).join("#"));
    }
    const imported = [...this.files]
      .filter(([file]) => !file.startsWith("ui/"))
      .flatMap(([, info]) => info.imports)
      .filter((imp) => imp.target?.startsWith("ui/"))
      .flatMap((imp) => this.namesTaken(imp).map((pair) => pair.join("#")));
    return new Set(imported.filter((key) => exported.has(key)));
  }

  namesTaken(imp) {
    // `* from` and `* as x` hand over every name the target exports.
    const names =
      imp.star || imp.namespace
        ? [...this.exportsOf(imp.target)]
        : imp.names.map((n) => n.from);
    return names.map((name) => this.conceptOf(imp.target, name));
  }

  conceptOf(file, name) {
    const [home, homeName] = this.homeOf(file, name);
    return [home, homeName === "default" ? baseName(home) : homeName];
  }

  // Follows `export { x } from` and `export * from` to the file that defines the name.
  homeOf(file, name, seen = new Set()) {
    const info = this.files.get(file);
    if (!info || seen.has(file) || info.exports.has(name)) return [file, name];
    seen.add(file);
    for (const imp of info.imports.filter((i) => i.reexport && i.target)) {
      const pair = imp.names.find((n) => n.as === name);
      if (pair) return this.homeOf(imp.target, pair.from, seen);
      if (imp.star && this.exportsOf(imp.target).has(name))
        return this.homeOf(imp.target, name, seen);
    }
    return [file, name];
  }

  exportsOf(file, seen = new Set()) {
    const info = this.files.get(file);
    if (!info || seen.has(file)) return new Set();
    seen.add(file);
    const names = new Set([...info.exports].filter((n) => n !== "default"));
    for (const imp of info.imports.filter((i) => i.reexport && i.target)) {
      for (const { as } of imp.names) names.add(as);
      if (imp.star)
        for (const n of this.exportsOf(imp.target, seen)) names.add(n);
    }
    return names;
  }

  pairs(map) {
    return [...map].flatMap(([file, names]) =>
      [...names].map((n) => [file, n])
    );
  }
}

// The names in backticks in each layer's Concept column: `FormLayout`, `useDoc`, and so on.
function listedNames(doc, layers) {
  const listed = new Map();
  for (const layer of layers) {
    const names = new Set();
    for (const row of conceptsOf(doc, layer)) {
      for (const span of row.name.match(/`[^`]+`/g) || [])
        for (const word of span.match(/[\w$]+/g) || []) names.add(word);
    }
    listed.set(layer.id, names);
  }
  return listed;
}

function count(pairs, what = "names") {
  const files = new Set(pairs.map(([file]) => file));
  return `${pairs.length} ${what} in ${files.size} files`;
}

function baseName(file) {
  return path.basename(file).replace(/\.[^.]+$/, "");
}
