// The files each flow's entry file reaches through its imports. CI prints them and never fails
// on them: a limit on files would push code into fewer, larger files.

export class FlowReach {
  constructor(jsFiles, flowEntries) {
    this.files = jsFiles;
    this.flows = flowEntries.map((f) => ({
      ...f,
      reached: this.reach(f.entry),
    }));
  }

  report() {
    return this.flows.flatMap(({ flow, entry, reached }) => {
      const inUi = reached.filter((f) => f.startsWith("ui/")).length;
      return [
        `FLOW       ${flow} (${entry}): ${reached.length} files, ${inUi} of them in ui/`,
        ...reached.map((f) => `             ${f}`),
      ];
    });
  }

  // Type imports count, because a reader follows them. A dynamic import is not followed: it
  // loads when another flow needs it, such as a page.
  reach(entry) {
    const seen = new Set();
    const queue = [entry];
    while (queue.length) {
      const file = queue.pop();
      if (seen.has(file) || !this.files.has(file)) continue;
      seen.add(file);
      for (const imp of this.files.get(file).imports)
        if (imp.target && !imp.dynamic) queue.push(imp.target);
    }
    return [...seen].sort();
  }
}
