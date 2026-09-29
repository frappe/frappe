// Runs every structure check on one read of the code: layers, folder loops and concepts.
// It also counts the files each flow reaches, which it prints but never fails on.

import fs from "node:fs";
import path from "node:path";
import { Sources } from "./sources.mjs";
import { buildGraph } from "./graph.mjs";
import { LayerCheck } from "./check.mjs";
import { LoopCheck } from "./loopCheck.mjs";
import { ConceptCheck } from "./conceptCheck.mjs";
import { FlowReach } from "./flowReach.mjs";

export class StructureCheck {
  constructor(root) {
    const read = (file) => fs.readFileSync(path.join(root, file), "utf8");
    this.layerFile = JSON.parse(read("frontend/architecture/layers.json"));
    this.doc = read(this.layerFile.architecture);
    const sources = new Sources(root);
    this.graph = buildGraph(root, sources);
    this.layers = new LayerCheck(this.graph, this.layerFile);
    this.loops = new LoopCheck(
      this.graph.folderCycles,
      this.layerFile.knownLoops
    );
    this.concepts = new ConceptCheck(
      sources.jsFiles(),
      (file) => this.layers.layerOf(file),
      this.doc,
      this.layerFile
    );
    this.flows = new FlowReach(sources.jsFiles(), this.layerFile.flowEntries);
  }

  get passes() {
    return this.layers.passes && this.loops.passes && this.concepts.passes;
  }

  // The failures, one per line; empty when every check passes.
  report() {
    return [
      ...this.layers.report(),
      ...this.loops.report(),
      ...this.concepts.report(),
    ];
  }
}
