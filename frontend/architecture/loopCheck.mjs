// Checks the groups of folders that import each other against knownLoops in layers.json.
// A group may only shrink, and a group that shrinks or goes must be updated in the same PR.

export class LoopCheck {
  constructor(loops, knownLoops) {
    this.loops = loops;
    this.known = knownLoops;
  }

  get newLoops() {
    return this.loops.filter(
      (group) => !this.known.some((k) => overlaps(k, group))
    );
  }

  get grownLoops() {
    return this.loops
      .filter((group) => this.known.some((k) => overlaps(k, group)))
      .filter(
        (group) => !this.known.some((k) => group.every((f) => k.includes(f)))
      )
      .map((group) => ({
        group,
        added: group.filter((f) => !this.known.some((k) => k.includes(f))),
      }));
  }

  // A known group that shrank, split or went. A known group inside a grown one is
  // reported as grown instead.
  get shrunkLoops() {
    return this.known.filter(
      (k) => !this.loops.some((group) => k.every((f) => group.includes(f)))
    );
  }

  get passes() {
    return (
      !this.newLoops.length &&
      !this.grownLoops.length &&
      !this.shrunkLoops.length
    );
  }

  report() {
    return [
      ...this.newLoops.map((group) => `NEW LOOP   ${group.join(" <-> ")}`),
      ...this.grownLoops.map(
        ({ group, added }) =>
          `LOOP GREW  ${group.join(" <-> ")}: added ${
            added.join(", ") || "a link between two known groups"
          }`
      ),
      ...this.shrunkLoops.map(
        (k) => `LOOP SHRANK ${k.join(" <-> ")}: update it in knownLoops`
      ),
    ];
  }
}

function overlaps(a, b) {
  return a.some((f) => b.includes(f));
}
