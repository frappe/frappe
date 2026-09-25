// When the record page paints: replays and holds stage every overlay, and the first
// paint lifts the skeletons once, or goes ahead without a late script.
import { computed, ref, type ComputedRef, type Ref } from "vue";
import { clientScriptWait } from "./clientScripts";
import type { Registration } from "./registry";
import type { Release, Staging } from "./staging";
import { andThen, settle, type MaybePromise } from "./steps";

/** How long the first paint waits for the page's scripts before it goes ahead without a late one. */
export const FIRST_PAINT_LIMIT_MS = 500;

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
  /** Runs `onRefresh` for each source `ran` does not hold yet, adding it. */
  runRefresh: (ran: Set<Registration>) => MaybePromise;
  /** Called once every source is in, before the replay's second pass. */
  warnUnknownHandlers: () => void;
  /** Delivers or drops the acts held so far, as `release` says. */
  deliverHeldActs: (release: Release) => void;
  closeDialogs: () => void;
}

export interface PaintGate {
  /** True once the first replay has painted, or the first paint went ahead without a late script. */
  ready: Ref<boolean>;
  isReplaying: ComputedRef<boolean>;
  /** The replay: rebuilds every overlay from built-ins, then runs every source's `onRefresh`. */
  refresh: (options?: RefreshOptions) => Promise<void>;
  /** Replays and commits before it returns; false, having run nothing, when anything must be waited for. */
  paintNow: () => boolean;
  /** One paint for the work's ops, and its acts delivered after it. */
  hold: <T>(work: () => Promise<T> | T) => Promise<T>;
  /** Runs a handler under its source's name; the early paint leaves out every running source. */
  asSource: (source: string, replay: boolean, work: () => MaybePromise) => MaybePromise;
  /** True while a replay or a hold is open, so an act waits for the commit. */
  isStaging: () => boolean;
  /** The reader left the page: closes its dialogs and stops the first-paint clock. */
  leave: () => void;
}

export interface RefreshOptions {
  /** The replay after a background read: its acts are dropped with a warning. */
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
    running: [] as { source: string; replay: boolean }[],
    awaiting: null as "permissions" | "sources" | null,
    firstPaintLimit: undefined as ReturnType<typeof setTimeout> | undefined,
    left: false,
    // True while the first paint's acts land: the page then reads as drawn, not staging.
    early: false,
    // Set when a background replay commits; the next release drops what is held.
    dropActs: false,
  };

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
    openReplay();
    try {
      await runSources(everything);
    } finally {
      // In `finally` so a throwing handler cannot leave the page staged for good.
      closeReplay(background);
    }
  }

  function paintNow() {
    if (state.left || !host.loaded()) return false;
    openReplay();
    const ran = new Set<Registration>();
    let pass: MaybePromise = undefined;
    try {
      pass = andThen(host.runRefresh(ran), () => secondPass(ran));
    } finally {
      if (!pass) endPaintNow();
    }
    if (pass) {
      paintEarly();
      void pass.finally(endPaintNow);
    }
    return true;
  }

  function endPaintNow() {
    closeReplay(false);
    replayed();
  }

  function secondPass(ran: Set<Registration>) {
    host.warnUnknownHandlers();
    return host.runRefresh(ran);
  }

  /** The sources already registered run while the Client Script tier loads; it runs last anyway. */
  async function runSources(everything: Promise<unknown>) {
    const ran = new Set<Registration>();
    await host.runRefresh(ran);
    await waitFor("sources", everything);
    host.warnUnknownHandlers();
    await host.runRefresh(ran);
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

  function closeReplay(background: boolean) {
    for (const surface of host.surfaces) surface.commit();
    replaying.value -= 1;
    if (background) state.dropActs = true;
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
    const inReplay = state.running.filter((entry) => entry.replay);
    const late = (inReplay.at(-1) ?? state.running.at(-1))?.source ?? lateWait();
    paintEarly();
    console.warn(
      `[record-page] ${host.doctype} ${host.docname} painted after ${FIRST_PAINT_LIMIT_MS} ms without waiting for ${late}; its changes land when it finishes.`,
    );
  }

  /** Draws every source not running a handler, lifts the skeletons, lands acts whose target is drawn. */
  function paintEarly() {
    const running = new Set(state.running.map((entry) => entry.source));
    for (const surface of host.surfaces) surface.publishStaged(running);
    state.early = true;
    try {
      host.deliverHeldActs("drawn");
    } finally {
      state.early = false;
    }
    ready.value = true;
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

  function asSource(source: string, replay: boolean, work: () => MaybePromise) {
    const entry = { source, replay };
    state.running.push(entry);
    return settle(work, () => void state.running.splice(state.running.indexOf(entry), 1));
  }

  function leave() {
    state.left = true;
    clearTimeout(state.firstPaintLimit);
    host.closeDialogs();
  }

  function isStaging() {
    return !state.early && (isReplaying.value || state.holding > 0);
  }

  /** Delivers the acts a replay or a hold kept back, once the last of them has committed. */
  function releaseActs() {
    if (isStaging()) return;
    const release = state.dropActs ? "none" : "all";
    state.dropActs = false;
    host.deliverHeldActs(release);
  }

  return { ready, isReplaying, refresh, paintNow, hold, asSource, isStaging, leave };
}
