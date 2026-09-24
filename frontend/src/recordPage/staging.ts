// The ops an overlay has drawn, and the buffer replays and holds stage into until
// the last of them commits.
import { toRaw } from "vue";

/** Why a held act is dropped when the first paint goes ahead without its target. */
export const NOT_DRAWN = "the first paint went ahead without it";

/** What the page opens, closes and publishes on every overlay a replay or a hold stages. */
export interface Staging {
  beginReplay(): void;
  beginHold(): void;
  commit(): void;
  publishStaged(except?: string): void;
}

export abstract class StagedOverlay<Op extends { source: string }> implements Staging {
  private pending: Op[] | null = null;
  private depth = 0;

  /** `drawn` is the reactive list the host renders from. */
  constructor(private readonly drawn: Op[]) {}

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

  /** What the host renders: committed ops only. */
  protected get drawnOps(): Op[] {
    return this.drawn;
  }

  /** What a script reads back: the buffer while one is open. */
  protected get currentOps(): Op[] {
    return this.pending ?? this.drawn;
  }

  /** True while a replay or a hold is open; acts wait for the commit. */
  protected get staging() {
    return this.depth > 0;
  }

  protected record(op: Op) {
    this.currentOps.push(op);
  }

  private publish(staged: Op[]) {
    const drawn = toRaw(this.drawn);
    if (staged.length === drawn.length && staged.every((op, index) => op === drawn[index])) return;
    // One splice, not a clear and a refill: the host must never render the buffer's middle.
    this.drawn.splice(0, this.drawn.length, ...staged);
  }
}
