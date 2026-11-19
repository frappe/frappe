// The ops an overlay has drawn, and the buffer replays and holds stage into until
// the last of them commits.
import { toRaw } from "vue";

/** Why an `onOpen` view act is dropped on a visit whose view the host puts back. */
export const RESTORED_VIEW = "onOpen ran on a view the page restored";

/** What the page opens, closes and publishes on every overlay a replay or a hold stages. */
export interface Staging {
  /** `token` names this open, so an overlapping close takes its own, not the last opened. */
  beginReplay(token?: StageToken): void;
  /** `keeps`: a replay inside this hold puts back what the hold staged, as a field handler's marks must outlast the re-run. */
  beginHold(keeps?: boolean, token?: StageToken): void;
  commit(token?: StageToken): void;
  publishStaged(except: ReadonlySet<string>): void;
}

export type StageToken = object;

/**
 * The replays and holds open on an overlay, each with its token. A replay inside a keeping
 * hold rebuilds from built-ins, then puts back what that hold itself staged (a field handler's marks).
 */
type OpenKind = "replay" | "hold" | "keeping";

interface Open {
  kind: OpenKind;
  token: StageToken;
}

export class OpenStack {
  private opens: Open[] = [];

  get depth() {
    return this.opens.length;
  }

  /** The keeping hold that owns what a script stages now: the last opened, when it keeps. A replay or a plain hold on top owns nothing. */
  get keeper(): StageToken | null {
    const top = this.opens.at(-1);
    return top?.kind === "keeping" ? top.token : null;
  }

  open(kind: OpenKind, token: StageToken = {}) {
    this.opens.push({ kind, token });
  }

  /**
   * Closes the open with `token` (the last opened, with none). `restoreFrom` is the keeping hold
   * opened before a closing replay, whose ops go back on; `last` when none remain.
   */
  close(token?: StageToken) {
    const at = token ? this.opens.findIndex((one) => one.token === token) : this.opens.length - 1;
    const [closed] = this.opens.splice(at, 1);
    const below = closed.kind === "replay" ? this.opens.slice(0, at).findLast((one) => one.kind === "keeping") : undefined;
    return { last: !this.opens.length, closed: closed.token, restoreFrom: below?.token ?? null };
  }
}

/** What each keeping hold staged, by its token, for a replay in it to put back. */
export class HeldLists<T> {
  private lists = new Map<StageToken, T[]>();

  add(keeper: StageToken | null, item: T) {
    if (keeper) this.lists.set(keeper, [...this.of(keeper), item]);
  }

  of(token: StageToken) {
    return this.lists.get(token) ?? [];
  }

  drop(token: StageToken) {
    this.lists.delete(token);
  }

  removeWhere(drop: (item: T) => boolean) {
    for (const [token, list] of this.lists) this.lists.set(token, list.filter((item) => !drop(item)));
  }

  clear() {
    this.lists.clear();
  }
}

export abstract class StagedOverlay<Op extends { source: string }> implements Staging {
  private pending: Op[] | null = null;
  private opened = new OpenStack();
  private held = new HeldLists<Op>();

  constructor(private readonly drawn: Op[]) {}

  /** A replay rebuilds from built-ins, so it empties the buffer even inside a hold; a keeping hold's ops go back on at its commit. */
  beginReplay(token?: StageToken) {
    this.pending = [];
    this.opened.open("replay", token);
  }

  /** A hold stacks on what is drawn, or joins the buffer already open. */
  beginHold(keeps = false, token?: StageToken) {
    if (!this.opened.depth) this.pending = [...toRaw(this.drawn)];
    this.opened.open(keeps ? "keeping" : "hold", token);
  }

  /** Closes a replay or a hold; true when it was the last open, which publishes. */
  commit(token?: StageToken) {
    if (!this.opened.depth) return false;
    const { last, closed, restoreFrom } = this.opened.close(token);
    if (restoreFrom) this.restoreHeld(restoreFrom);
    this.forgetHeld(closed);
    if (!last) return false;
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
    return this.opened.depth > 0;
  }

  /** The keeping hold that owns what is recorded now, if any. */
  protected get keeper() {
    return this.opened.keeper;
  }

  protected record(op: Op) {
    this.currentOps.push(op);
    this.held.add(this.keeper, op);
  }

  /** Puts a hold's own ops back after a replay inside it rebuilt the buffer. */
  protected restoreHeld(hold: StageToken) {
    this.pending!.push(...this.held.of(hold));
  }

  /** An open closed: its ops are no longer kept. */
  protected forgetHeld(hold: StageToken) {
    this.held.drop(hold);
  }

  private publish(staged: Op[]) {
    if (sameValue(staged, toRaw(this.drawn))) return;
    // One splice, not a clear and a refill: the host must never render the buffer's middle.
    this.drawn.splice(0, this.drawn.length, ...staged);
  }
}

/** Equal by content; a function, a class instance or a raw-marked value only by identity. */
function sameValue(a: unknown, b: unknown, seen = new WeakMap<object, object>()): boolean {
  if (Object.is(a, b)) return true;
  if (!isData(a) || !isData(b)) return false;
  if (seen.has(a)) return seen.get(a) === b;
  seen.set(a, b);
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
