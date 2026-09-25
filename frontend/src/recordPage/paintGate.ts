// When the record page paints: replays and holds stage every overlay, and the first
// paint lifts the skeletons once, or goes ahead without a late script.
import { computed, ref, type ComputedRef, type Ref } from "vue";
import { clientScriptWait } from "./clientScripts";
import type { Registration } from "./registry";
import type { Staging } from "./staging";

/** How long the first paint waits for the page's scripts before it goes ahead without a late one. */
export const FIRST_PAINT_LIMIT_MS = 500;

/** How long an `onRefresh`'s part after an await holds the page's paints before the page stops waiting. */
export const LATE_LIMIT_MS = 5000;

export interface PaintGateHost {
  doctype: string;
  docname: string;
  /** Every overlay a replay or a hold stages. */
  surfaces: Staging[];
  /** Resolves when sources that register after mount (Client Scripts) are in. */
  sourcesReady?: () => Promise<void>;
  permissionsReady: () => Promise<unknown>;
  /** True when the sources and the permissions are already in, so a replay needs no wait. */
  loaded: () => boolean;
  /** Runs `onRefresh` for each source `ran` does not hold yet, adding it; answers the ones still running. */
  runRefresh: (ran: Set<Registration>) => LateRefresh[];
  /** Called once every source is in, before the replay's second pass. */
  warnUnknownHandlers: () => void;
  /** Delivers the acts held so far; `drawnOnly` drops one whose target is not drawn. */
  deliverHeldActs: (drawnOnly: boolean) => void;
  closeDialogs: () => void;
}

export interface PaintGate {
  /** True once the first replay has painted, or the first paint went ahead without a late script. */
  ready: Ref<boolean>;
  isReplaying: ComputedRef<boolean>;
  /** The replay: rebuilds every overlay from built-ins, then runs every source's `onRefresh`. */
  refresh: (options?: RefreshOptions) => Promise<void>;
  /** Replays and commits before it returns true; false, having run nothing, while scripts or permissions load. */
  paintNow: () => boolean;
  /** One paint for the work's ops, and its acts delivered after it. */
  hold: <T>(work: () => Promise<T> | T) => Promise<T>;
  /** Runs a handler under its source's name; the early paint leaves out every running source. */
  asSource: (source: string, work: () => Promise<void>) => Promise<void>;
  /** True while a replay or a hold is open, so an act waits for the commit. */
  isStaging: () => boolean;
  /** True while the replay after a background read runs, so an act in it is dropped. */
  inBackground: () => boolean;
  /** The reader left the page: closes its dialogs and late holds, and delivers no more acts. */
  leave: () => void;
  /** True once the reader has left, so a kept `page.save` or `page.reload` does nothing. */
  hasLeft: () => boolean;
}

/** An `onRefresh` that returned a promise: the rest of it runs in a hold for its source. */
export interface LateRefresh {
  source: string;
  settled: Promise<void>;
}

export interface RefreshOptions {
  /** The replay after a background read: it runs in one step once the sources are in, and drops its acts. */
  background?: boolean;
}

export function createPaintGate(host: PaintGateHost): PaintGate {
  const ready = ref(false);
  const replaying = ref(0);
  const isReplaying = computed(() => replaying.value > 0);
  const state = {
    holding: 0,
    replayed: false,
    // The sources running a handler on this page, oldest first, and what a replay waits on, for the early paint.
    running: [] as string[],
    awaiting: null as "permissions" | "sources" | null,
    firstPaintLimit: undefined as ReturnType<typeof setTimeout> | undefined,
    left: false,
    // True while the first paint's acts land: the page then reads as drawn, not staging.
    early: false,
    background: false,
  };
  let markLeft!: () => void;
  const left = new Promise<void>((resolve) => (markLeft = resolve));

  async function refresh(options: RefreshOptions = {}) {
    if (state.left) return;
    if (!ready.value && !state.firstPaintLimit)
      state.firstPaintLimit = setTimeout(paintWithoutLate, FIRST_PAINT_LIMIT_MS);
    try {
      await replay(options.background ?? false);
    } finally {
      state.awaiting = null;
      replayed();
    }
  }

  async function replay(background: boolean) {
    const everything = Promise.all([host.sourcesReady?.(), host.permissionsReady()]);
    // Raced, so a late rejection of `everything` is already handled when the second pass awaits it.
    await waitFor("permissions", Promise.race([host.permissionsReady(), everything]));
    if (background) await everything;
    if (state.left) return;
    if (background) return replayNow(true);
    openReplay();
    // Filled by `runSources`, so the first pass's late parts are still held when the second pass throws.
    const late: LateRefresh[] = [];
    try {
      await runSources(everything, late);
    } finally {
      // In `finally` so a throwing handler cannot leave the page staged for good.
      closeReplay();
      holdLate(late);
    }
  }

  /** The sources already registered run while the Client Script tier loads; it runs last anyway. */
  async function runSources(everything: Promise<unknown>, late: LateRefresh[]) {
    const ran = new Set<Registration>();
    late.push(...host.runRefresh(ran));
    await waitFor("sources", everything);
    host.warnUnknownHandlers();
    late.push(...host.runRefresh(ran));
  }

  function paintNow() {
    if (state.left || !host.loaded()) return false;
    replayNow(false);
    state.replayed = true;
    ready.value = true;
    return true;
  }

  /** The whole replay in one step, once nothing is left to wait for. */
  function replayNow(background: boolean) {
    openReplay();
    state.background = background;
    let late: LateRefresh[] = [];
    try {
      host.warnUnknownHandlers();
      late = host.runRefresh(new Set());
    } finally {
      state.background = false;
      closeReplay();
    }
    holdLate(late);
  }

  /** Opened once the replay has committed, so its synchronous part draws without waiting for these. */
  function holdLate(late: LateRefresh[]) {
    for (const { source, settled } of late)
      void asSource(source, () => hold(() => bounded(source, settled)));
  }

  /** Answers when the part settles or the reader leaves, or after the limit with a warning. */
  function bounded(source: string, settled: Promise<void>) {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const limit = new Promise<void>((resolve) => {
      timer = setTimeout(() => {
        if (import.meta.env.DEV)
          console.warn(
            `[record-page] ${source}.onRefresh on ${host.doctype} did not settle within ${LATE_LIMIT_MS / 1000} s; the page stopped waiting for it.`,
          );
        resolve();
      }, LATE_LIMIT_MS);
    });
    const done = Promise.race([settled, left, limit]);
    void done.then(() => clearTimeout(timer));
    return done;
  }

  async function waitFor(what: typeof state.awaiting, promise: Promise<unknown>) {
    state.awaiting = what;
    await promise;
    state.awaiting = null;
  }

  function openReplay() {
    // Counted, not a boolean: a script's own `page.refresh()` re-enters this.
    replaying.value += 1;
    // Staged, not cleared: clearing here and re-adding a microtask later tears the
    // rendered strip down between the two, and the reader's place in it with them.
    for (const surface of host.surfaces) surface.beginReplay();
  }

  function closeReplay() {
    for (const surface of host.surfaces) surface.commit();
    replaying.value -= 1;
    // After the commit, so the strip the reader lands on is the one on screen.
    releaseActs();
  }

  function replayed() {
    state.replayed = true;
    settleReady();
  }

  /** The skeletons lift once a replay has ended and nothing stages; a hold may close last. */
  function settleReady() {
    if (!state.replayed || isStaging()) return;
    clearTimeout(state.firstPaintLimit);
    ready.value = true;
  }

  /** The first replay ran out of time: draw every source not running, lift the skeletons, name the late one. */
  function paintWithoutLate() {
    if (ready.value || state.left) return;
    const late = state.awaiting ? lateWait() : (state.running.at(-1) ?? lateWait());
    const running = new Set(state.running);
    for (const surface of host.surfaces) surface.publishStaged(running);
    releaseEarlyActs();
    ready.value = true;
    console.warn(
      `[record-page] ${host.doctype} ${host.docname} painted after ${FIRST_PAINT_LIMIT_MS} ms without waiting for ${late}; its changes land when it finishes.`,
    );
  }

  /** Each act held so far lands if the early paint drew its target, and is dropped if not. */
  function releaseEarlyActs() {
    state.early = true;
    try {
      host.deliverHeldActs(true);
    } finally {
      state.early = false;
    }
  }

  function lateWait() {
    if (state.awaiting === "permissions") return "the page's permissions";
    return clientScriptWait(host.doctype) ?? "the page's scripts";
  }

  async function hold<T>(work: () => Promise<T> | T): Promise<T> {
    state.holding += 1;
    for (const surface of host.surfaces) surface.beginHold();
    try {
      return await work();
    } finally {
      for (const surface of host.surfaces) surface.commit();
      state.holding -= 1;
      releaseActs();
      settleReady();
    }
  }

  async function asSource(source: string, work: () => Promise<void>) {
    state.running.push(source);
    try {
      await work();
    } finally {
      state.running.splice(state.running.lastIndexOf(source), 1);
    }
  }

  function leave() {
    state.left = true;
    markLeft();
    clearTimeout(state.firstPaintLimit);
    host.closeDialogs();
  }

  function isStaging() {
    return !state.early && (isReplaying.value || state.holding > 0);
  }

  /** Delivers the acts a replay or a hold kept back, once the last of them has committed. */
  function releaseActs() {
    if (!state.left && !isStaging()) host.deliverHeldActs(false);
  }

  function inBackground() {
    return state.background;
  }

  return {
    ready,
    isReplaying,
    refresh,
    paintNow,
    hold,
    asSource,
    isStaging,
    inBackground,
    leave,
    hasLeft: () => state.left,
  };
}
