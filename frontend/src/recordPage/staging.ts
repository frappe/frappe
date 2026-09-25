// The ops an overlay has drawn, and the buffer replays and holds stage into until
// the last of them commits.
import { toRaw } from "vue";

/** Why a held act is dropped when the first paint goes ahead without its target. */
export const NOT_DRAWN = "the first paint went ahead without it";

/** Why a held act is dropped when the replay after a background read commits. */
export const IN_BACKGROUND = "it ran in the replay after a background read";

/** Which held acts a commit delivers: every one, those whose target is drawn, or none. */
export type Release = "all" | "drawn" | "none";

/** The reason a held act is dropped under `release`, or null when it lands. */
export function dropReason(release: Release, isDrawn: () => boolean): string | null {
  if (release === "none") return IN_BACKGROUND;
  if (release === "drawn" && !isDrawn()) return NOT_DRAWN;
  return null;
}

/** What the page opens, closes and publishes on every overlay a replay or a hold stages. */
export interface Staging {
  beginReplay(): void;
  beginHold(): void;
  commit(): void;
  publishStaged(except: ReadonlySet<string>): void;
}

export abstract class StagedOverlay<Op extends { source: string }> implements Staging {
  private pending: Op[] | null = null;
  private depth = 0;

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

  /** Draws the buffer as it stands, less the ops of the sources in `except`, and keeps staging. */
  publishStaged(except: ReadonlySet<string>) {
    if (this.pending) this.publish(this.pending.filter((op) => !except.has(op.source)));
  }

  protected get drawnOps(): Op[] {
    return this.drawn;
  }

  /** What a script reads back: the buffer while one is open. */
  protected get currentOps(): Op[] {
    return this.pending ?? this.drawn;
  }

  /** True while a replay or a hold is open. */
  protected get staging() {
    return this.depth > 0;
  }

  protected record(op: Op) {
    this.currentOps.push(op);
  }

  private publish(staged: Op[]) {
    if (sameValue(staged, toRaw(this.drawn))) return;
    // One splice, not a clear and a refill: the host must never render the buffer's middle.
    this.drawn.splice(0, this.drawn.length, ...staged);
  }
}

/** Equal by content; a function, a class instance or a raw-marked value only by identity. */
function sameValue(a: unknown, b: unknown, seen = new WeakSet<object>()): boolean {
  if (Object.is(a, b)) return true;
  if (!isData(a) || !isData(b) || seen.has(a)) return false;
  seen.add(a);
  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
    return a.every((one, index) => sameValue(one, b[index], seen));
  }
  const keys = Object.keys(a);
  if (keys.length !== Object.keys(b).length) return false;
  return keys.every((key) => Object.hasOwn(b, key) && sameValue(a[key], b[key], seen));
}

function isData(value: unknown): value is Record<string, unknown> {
  if (!value || typeof value !== "object") return false;
  if ((value as { __v_skip?: boolean }).__v_skip) return false;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === Array.prototype || proto === null;
}
