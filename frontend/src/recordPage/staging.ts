// The ops an overlay has drawn, and the buffer replays and holds stage into until
// the last of them commits.
import { toRaw } from "vue";

export class StagedOps<Op extends { source: string }> {
  private pending: Op[] | null = null;
  private depth = 0;

  /** `drawn` is the reactive list the host renders from. */
  constructor(private readonly drawn: Op[]) {}

  /** What the host renders: committed ops only. */
  get committed(): Op[] {
    return this.drawn;
  }

  /** What a script reads back: the buffer while one is open. */
  get current(): Op[] {
    return this.pending ?? this.drawn;
  }

  get isStaging() {
    return this.depth > 0;
  }

  record(op: Op) {
    this.current.push(op);
  }

  /** A replay rebuilds from built-ins, so it empties the buffer even inside a hold. */
  beginReplay() {
    this.pending = [];
    this.depth += 1;
  }

  /** A hold stacks on what is drawn, or joins the buffer already open. */
  beginHold() {
    if (!this.depth) this.pending = [...toRaw(this.drawn)];
    this.depth += 1;
  }

  /** Closes a replay or a hold; true when it was the last open, which publishes. */
  commit() {
    if (!this.depth) return false;
    this.depth -= 1;
    if (this.depth) return false;
    const staged = this.pending ?? [];
    this.pending = null;
    this.publish(staged);
    return true;
  }

  /** Draws the buffer as it stands, less one source's ops, and keeps staging. */
  publishStaged(except?: string) {
    if (this.pending) this.publish(this.pending.filter((op) => op.source !== except));
  }

  private publish(staged: Op[]) {
    const drawn = toRaw(this.drawn);
    if (staged.length === drawn.length && staged.every((op, index) => op === drawn[index])) return;
    // One splice, not a clear and a refill: the host must never render the buffer's middle.
    this.drawn.splice(0, this.drawn.length, ...staged);
  }
}
