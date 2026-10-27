import type { ComputedRef, Ref } from "vue";
import type { Router } from "vue-router";
import { toast } from "frappe-ui";
import { runMethod } from "@framework/ui/api";
import { BodySurface } from "./body";
import { runningSource, withRunningSource } from "./context";
import { createPageDialogs, type PageDialogEntry } from "./dialog";
import { FrameSurface } from "./frame";
import { HeaderSurface } from "./headerRenderings";
import { createHeldActs } from "./heldActs";
import { createPaintGate, type LateRefresh, type RefreshOptions } from "./paintGate";
import type { Staging } from "./staging";
import type { Handler, PageApi, Registration } from "./types";

/** The events every page fires, whatever its own. */
const ENGINE_EVENTS = ["onRefresh", "onOpen"];

/** What backs `page.cached`: one value per source and key, and the fetches not yet made. */
export interface CachedProvider {
  read(source: string, key: string, fetch: () => unknown): unknown;
  fetchUnfetched(): LateRefresh[];
}

export type PageEngineLists = Record<string, Staging>;

export interface PageEngineSpec<Lists extends PageEngineLists, Extras extends object> {
  doctype: string;
  /** The record's or the page's name, for messages. */
  name: string;
  /** The page's own lists, each on `page` under its name. */
  lists: Lists;
  /** Overlays every replay and hold stages that are not on `page` under a name. */
  overlays?: Staging[];
  /** The page's own events, for the default check of handler keys. */
  events?: string[];
  /** Every source's handlers, in run order. */
  sources: () => Registration[];
  /** The page's own members; a getter stays a getter. */
  extras: (engine: PageEngineParts) => Extras;
  meta: () => Record<string, any> | null;
  perms: () => Record<string, any>;
  roles: () => string[];
  router: Router;
  /** Absent, `page.cached` holds nothing and fetches nothing. */
  cached?: CachedProvider;
  /** Resolves when sources that register after mount are in. */
  sourcesReady?: () => Promise<void>;
  permissionsReady?: () => Promise<unknown>;
  /** True when the sources and the permissions are already in, so a replay needs no wait. */
  loaded?: () => boolean;
  /** The sources a replay's first pass leaves out while their tier loads. */
  skippedBeforeSources?: () => ReadonlySet<string>;
  /** What the first paint names when it went ahead without the sources. */
  lateLabel?: () => string;
  /** The `page` `onOpen` gets, made from the one `onRefresh` gets. */
  openView?: (view: EnginePage<Lists, Extras>) => EnginePage<Lists, Extras>;
  /** Runs once every source is in; absent, a handler key that is no event warns once. */
  warnUnknownHandlers?: () => void;
  /** The events whose throw is rethrown to the caller, not reported. */
  vetoes?: string[];
  /** Files a handler's failure; the console has it already. */
  report?: (error: unknown, source: string, event: string) => void;
}

export type EnginePage<Lists, Extras> = PageApi & Lists & Extras;

export interface PageEngine<Lists extends PageEngineLists, Extras extends object> {
  page: EnginePage<Lists, Extras>;
  frame: FrameSurface;
  header: HeaderSurface;
  body: BodySurface;
  lists: Lists;
  heldActs: ReturnType<typeof createHeldActs>;
  /** Runs every source's handler for `event` in one hold, so its ops paint once. */
  fire: (event: string, detail?: unknown) => Promise<void>;
  /** The replay: rebuilds every list from built-ins, then runs every source's `onRefresh`. */
  refresh: (options?: RefreshOptions) => Promise<void>;
  /** Replays and commits before it returns true; false, having run nothing, while sources or permissions load. */
  paintNow: () => boolean;
  /** Fetches the `page.cached` keys `paintNow` read; answers when they land or at the late limit. */
  fetchCached: () => Promise<void>;
  /** Runs code outside an event, so its ops paint once, when it finishes. */
  hold: <T>(work: () => Promise<T> | T) => Promise<T>;
  /** True once the first replay has painted, or the first paint went ahead without a late source. */
  ready: Ref<boolean>;
  isReplaying: ComputedRef<boolean>;
  /** The `open`/`form` dialogs on screen, for the host's `<PageDialogs>`. */
  dialogs: Ref<PageDialogEntry[]>;
  hasLeft: () => boolean;
  /** The reader left: closes the dialogs and the `page` `onRefresh` and `onOpen` got. */
  leave: () => void;
}

export type PageEngineParts = Pick<
  PageEngine<PageEngineLists, object>,
  "hold" | "hasLeft" | "heldActs" | "fire" | "refresh"
>;

// Gives itself back for any read, call or write, and an await on it never resumes.
const INERT: any = new Proxy(() => {}, {
  get: (_, key) => (key === Symbol.toPrimitive ? () => undefined : INERT),
  apply: () => INERT,
  set: () => true,
});

export function createPageEngine<Lists extends PageEngineLists, Extras extends object>(
  spec: PageEngineSpec<Lists, Extras>,
): PageEngine<Lists, Extras> {
  const frame = new FrameSurface();
  const header = new HeaderSurface();
  const body = new BodySurface();
  const heldActs = createHeldActs({
    isStaging: () => gate.isStaging(),
    inBackground: () => gate.inBackground(),
  });
  let vocabularyChecked = false;

  const gate = createPaintGate({
    doctype: spec.doctype,
    name: spec.name,
    surfaces: [frame, header, body, ...Object.values(spec.lists), ...(spec.overlays ?? [])],
    sourcesReady: spec.sourcesReady,
    permissionsReady: spec.permissionsReady ?? (() => Promise.resolve()),
    loaded: spec.loaded ?? (() => true),
    runRefresh: (ran, beforeSources) =>
      runRefresh(ran, beforeSources ? spec.skippedBeforeSources?.() : undefined),
    fetchCached: () => spec.cached?.fetchUnfetched() ?? [],
    runOpen: (registrations) => runOpen(registrations),
    warnUnknownHandlers: spec.warnUnknownHandlers ?? warnUnknownHandlers,
    deliverHeldActs: heldActs.release,
    closeDialogs: () => dialogs.closeAll(),
    lateLabel: spec.lateLabel ?? (() => "the page's scripts"),
  });
  const { hold } = gate;

  const dialogs = createPageDialogs({ isReplaying: () => gate.isReplaying.value, hold });

  const page = {
    doctype: spec.doctype,
    get meta() {
      return spec.meta();
    },
    get perms() {
      return spec.perms();
    },
    get roles() {
      return spec.roles();
    },
    frame,
    header,
    body,
    refresh: () => gate.refresh(),
    toast: {
      success: (message: string) => toast.success(message),
      error: (message: string) => toast.error(message),
    },
    dialog: dialogs.api,
    call: (method: string, params?: Record<string, any>) =>
      runMethod(method, params).then((envelope) => envelope.data),
    cached: <T>(key: string, fetch: () => Promise<T> | T) =>
      spec.cached?.read(runningSource(), key, fetch) as T | undefined,
    // The one member handed straight through, and the only one; see frontend/CLAUDE.md.
    router: spec.router,
  } as EnginePage<Lists, Extras>;
  addMembers(spec.lists, "list");

  const refreshView = pageView(page);

  const engine: PageEngine<Lists, Extras> = {
    page,
    frame,
    header,
    body,
    lists: spec.lists,
    heldActs,
    fire,
    refresh: gate.refresh,
    paintNow: gate.paintNow,
    fetchCached: gate.fetchCached,
    hold,
    ready: gate.ready,
    isReplaying: gate.isReplaying,
    dialogs: dialogs.entries,
    hasLeft: gate.hasLeft,
    leave: () => {
      refreshView.close();
      gate.leave();
    },
  };
  addMembers(spec.extras(engine), "extra member");
  return engine;

  function addMembers(members: object, kind: string) {
    // Descriptors, not a spread: a spread would read each getter once, here.
    const descriptors = Object.getOwnPropertyDescriptors(members);
    for (const key of Object.keys(descriptors))
      if (Object.hasOwn(page, key))
        throw new Error(`[record-page] the ${kind} "${key}" on ${spec.doctype} would replace the page's own "${key}"`);
    Object.defineProperties(page, descriptors);
  }

  function fire(event: string, detail?: unknown) {
    return hold(() => dispatch(event, detail));
  }

  async function dispatch(event: string, detail?: unknown) {
    for (const { source, handlers } of spec.sources()) {
      const handler = handlers[event];
      if (!handler) continue;
      const run = () =>
        withRunningSource(source, async () => {
          try {
            await handler(page, detail);
          } catch (error) {
            reportHandlerError(source, event, error);
          }
        });
      await gate.asSource(source, run);
    }
  }

  /** A replay's pass, synchronous; `ran` carries its first pass into its second, so no source runs twice. */
  function runRefresh(ran: Set<Registration>, skipping?: ReadonlySet<string>) {
    const late: LateRefresh[] = [];
    for (const registration of spec.sources()) {
      if (ran.has(registration) || skipping?.has(registration.source)) continue;
      ran.add(registration);
      const { source, handlers } = registration;
      const handler = handlers.onRefresh;
      const settled = handler && refreshWith(source, handler);
      if (settled) late.push({ source, settled });
    }
    return late;
  }

  /** Answers when the rest of an `onRefresh` that returned a promise settles. */
  function refreshWith(source: string, handler: Handler) {
    try {
      let result: unknown;
      withRunningSource(source, () => {
        result = handler(refreshView.page);
      });
      if (!(result instanceof Promise)) return;
      warnAsyncRefresh(source);
      return result.then(
        () => {},
        (error) => reportHandlerError(source, "onRefresh", error),
      );
    } catch (error) {
      reportHandlerError(source, "onRefresh", error);
    }
  }

  /** Its part after an await is not held and names no source, as `onRefresh`'s: handlers here overlap. */
  function runOpen(registrations: Registration[]) {
    const view = spec.openView ? spec.openView(refreshView.page) : refreshView.page;
    for (const { source, handlers } of registrations) {
      const handler = handlers.onOpen;
      if (!handler) continue;
      try {
        let result: unknown;
        withRunningSource(source, () => {
          result = handler(view);
        });
        if (result instanceof Promise)
          void result.catch((error) => reportHandlerError(source, "onOpen", error));
      } catch (error) {
        reportHandlerError(source, "onOpen", error);
      }
    }
  }

  // Filed in production too, so an admin sees which scripts to move to a cached read.
  function warnAsyncRefresh(source: string) {
    const message = `[record-page] ${source}.onRefresh on ${spec.doctype} returned a promise; onRefresh should be synchronous, and read server data with page.cached(key, fetcher). The first paint waits up to 500 ms for what it does after its first await; after that it lands as a later paint.`;
    if (import.meta.env.DEV) console.warn(message);
    spec.report?.(new Error(message), source, "onRefresh (async)");
  }

  function reportHandlerError(source: string, event: string, error: unknown) {
    // A veto is not reported: the reader is looking straight at what it refused.
    if (spec.vetoes?.includes(event)) throw error;
    console.error(`[record-page] ${source}.${event} on ${spec.doctype} threw`, error);
    spec.report?.(error, source, event);
  }

  function warnUnknownHandlers() {
    if (!import.meta.env.DEV || vocabularyChecked) return;
    const registrations = spec.sources();
    if (!registrations.length) return;
    vocabularyChecked = true;
    const known = new Set([...ENGINE_EVENTS, ...(spec.events ?? [])]);
    for (const { source, handlers } of registrations)
      for (const key of Object.keys(handlers))
        if (!known.has(key))
          console.warn(`[record-page] ${source}.${key} on ${spec.doctype} is not an event of this page — it will never fire`);
  }
}

/** The `page` `onRefresh` and `onOpen` get; once closed, every member read off it is inert. */
function pageView<Page extends object>(page: Page) {
  let open = true;
  const view = new Proxy(page, { get: (target, key) => (open ? Reflect.get(target, key) : INERT) });
  return { page: view, close: () => void (open = false) };
}
