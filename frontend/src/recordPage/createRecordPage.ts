// Builds the curated `page` and the controller that fires events into it. Handlers
// run serially, each in its own try/catch; only a `beforeSave` throw aborts anything.
import { computed, shallowRef, type ComputedRef, type Ref } from "vue";
import type { Router } from "vue-router";
import { toast } from "frappe-ui";
import { runMethod } from "@framework/ui/api";
import { CachedReads } from "./cachedReads";
import { createCommitChannel, type RecordCommitChannel } from "./commitChannel";
import { ComposerSurface, composerTab, type ComposerHost } from "./composer";
import { runningSource, withRunningSource } from "./context";
import { createPageDialogs, type PageDialogEntry } from "./dialog";
import { createHeldActs, type HeldAct } from "./heldActs";
import type { Decorator } from "@framework/ui/components/FormLayout/buildLayoutFromMeta";
import type {
  FormLayoutSchema,
  RawMetaField,
} from "@framework/ui/components/FormLayout/types";
import { holdsChildRows } from "@framework/ui/components/Fields/rowIdentity";
import type { RowAddress } from "@framework/ui/components/Fields/types";
import { ActivitySurface, FilesSurface } from "./feed";
import { FieldsSurface, LAYOUT_BREAKS } from "./fields";
import { FormSurface } from "./form";
import { FormTabsSurface } from "./formTabs";
import { FrameSurface } from "./frame";
import { BodySurface } from "./body";
import { HeaderSurface } from "./headerRenderings";
import { ROW_EVENTS } from "./flattenHandlers";
import { createPagePermissions } from "./pagePermissions";
import { readOnly, type ReadOnlyAdvice } from "./readOnly";
import { registrationsFor, type Registration } from "./registry";
import { reportCustomizationError } from "./reportError";
import { createRows, warnRowIssue } from "./rows";
import { clientScriptsLoaded, replacedClientScripts } from "./clientScripts";
import { createPaintGate, type LateRefresh, type RefreshOptions } from "./paintGate";
import { RESTORED_VIEW, type Staging } from "./staging";
import { Surface } from "./surface";
import { PANEL_SECTION_KEYS, QUICK_ACTION_KEYS, TAB_ITEM_KEYS } from "./types";
import type {
  ActivityRow,
  ComposerOpenOptions,
  FileRow,
  Handler,
  PageRow,
  PanelSectionItem,
  PanelSectionsApi,
  PostedRow,
  QuickAction,
  RecordPageApi,
  TabItem,
  TabsApi,
} from "./types";

/** The name a `beforeSave` veto rejects under, so a host keeps the draft instead of reloading. */
export const SAVE_VETO = "SaveVeto";

/** A veto keeps the script's message; a non-Error throw is wrapped so it can carry the name. */
function asVeto(error: unknown): Error {
  const veto = error instanceof Error ? error : new Error(String(error));
  veto.name = SAVE_VETO;
  return veto;
}

// Gives itself back for any read, call or write, and an await on it never resumes.
const INERT: any = new Proxy(() => {}, {
  get: (_, key) => (key === Symbol.toPrimitive ? () => undefined : INERT),
  apply: () => INERT,
  set: () => true,
});

/** The `page` `onRefresh` and `onOpen` get; once closed, every member read off it is inert. */
function pageView(page: RecordPageApi) {
  let open = true;
  const view = new Proxy(page, { get: (target, key) => (open ? Reflect.get(target, key) : INERT) });
  return { page: view, close: () => void (open = false) };
}

/** `target` with the named members answered from `members`; every other read and write goes through. */
function overriding<T extends object>(target: T, members: Record<string, unknown>): T {
  // Over a child of `target`: a Proxy may not answer a frozen own member of its target differently.
  return new Proxy(Object.create(target), {
    get: (_, key) => (Object.hasOwn(members, key) ? members[key as string] : Reflect.get(target, key)),
    set: (_, key, value) => Reflect.set(target, key, value),
  });
}

/** The closed event vocabulary; every other key is a fieldname. */
export const RECORD_PAGE_EVENTS = [
  "onRefresh",
  "onOpen",
  "beforeSave",
  "afterSave",
  "onTabChange",
  "onFormTabChange",
  "onPost",
];

// Each refusal names the verb that does support what the write was reaching for.
const META_IS_READ_ONLY: ReadOnlyAdvice = {
  path: "page.meta",
  instead: "page.fields.update('qty', { hidden: 1 })",
};

const PERMS_ARE_READ_ONLY: ReadOnlyAdvice = {
  path: "page.perms",
  instead: "a copy: { ...page.perms }, since rights come from the server",
};

const ROLES_ARE_READ_ONLY: ReadOnlyAdvice = {
  path: "page.roles",
  instead:
    "a copy: [...page.roles], since roles belong to the session, not the page",
};

// `page.saved.qty = 5` is a plausible typo for `page.doc.qty = 5`, and would
// otherwise silently rewrite the baseline `isDirty` reads.
const SAVED_IS_READ_ONLY: ReadOnlyAdvice = {
  path: "page.saved",
  instead: "page.doc, which is the draft this is the saved counterpart of",
};

/** The two tab strips, by the member each is reached through. */
type TabStrip = "tabs" | "form.tabs";

const STRIPS: Record<TabStrip, { other: string; sibling: TabStrip }> = {
  tabs: { other: "form's", sibling: "form.tabs" },
  "form.tabs": { other: "record's", sibling: "tabs" },
};

export interface RecordPageHost {
  doctype: string;
  docname: string;
  doc: Ref<Record<string, any>>;
  /** The document as the server last showed it; the draft's baseline. */
  saved: Ref<Record<string, any>>;
  meta: Ref<any>;
  /** The record read's `permissions` part; the engine curates it. */
  perms: () => Record<string, any>;
  isDirty: () => boolean;
  /** The name of the tab the reader is on, as the host's strip resolves it. */
  activeTab: () => string;
  /** Moves the reader to a tab of the record's strip; the engine has already resolved the name. */
  activateTab: (name: string) => void;
  /** The record's Details layout, which `page.form` addresses; absent for a host with no form. */
  formLayout?: () => FormLayoutSchema | undefined;
  /** The identity of the Form Layout tab the reader is on, or `''` outside the form. */
  activeFormTab?: () => string;
  /** Moves the reader to a tab of the form, by identity; absent for a host with no form. */
  activateFormTab?: (identity: string) => void;
  /** Opens or shuts a panel section for the reader; the engine has already resolved the name. */
  discloseSection?: (name: string, open: boolean) => void;
  /** Lands the reader on a field of the form; `cursor` is false for a read-only one. */
  focusField?: (fieldname: string, cursor: boolean) => void;
  /** Writes the draft; the engine flushes and fires `beforeSave` before it, `afterSave` after. */
  save: () => Promise<void>;
  reload: () => Promise<void>;
  router: Router;
  /** The host's per-field overlay hook; `page.fields.get` reads it to match what renders. */
  decorate?: Decorator;
  /** A child doctype's meta fields, by doctype name; absent while the metas load. */
  childFields?: (doctype: string) => RawMetaField[] | undefined;
  /** Resolves when sources that register after mount (Client Scripts) are in. */
  sourcesReady?: () => Promise<void>;
  /** The rows the Activity tab has loaded, oldest first, pending ones included. */
  activityRows: () => ActivityRow[];
  /** Opens the Activity tab and scrolls to the row, paging older until drawn; false if the list ended first, null if the host warned why not. */
  scrollToActivity: (key: string) => Promise<boolean | null>;
  reloadActivity: () => Promise<void>;
  /** The record read's `attachments` part, oldest first. */
  fileRows: () => FileRow[];
  reloadFiles: () => Promise<void>;
  /** Opens a writer in the band; the engine has already moved the reader to a tab that draws it. */
  openWriter?: ComposerHost["openWriter"];
  closeWriter?: ComposerHost["closeWriter"];
  /** The open writer's name, or `''`. */
  activeWriter?: ComposerHost["activeWriter"];
  windowState?: ComposerHost["windowState"];
  setWindow?: ComposerHost["setWindow"];
  /** True when the host puts back the reader's view on this visit; `onOpen`'s view acts then do nothing. */
  restoresView?: () => boolean;
}

export interface RecordPageController {
  page: RecordPageApi;
  quickActions: Surface<QuickAction>;
  frame: FrameSurface;
  body: BodySurface;
  header: HeaderSurface;
  tabs: Surface<TabItem>;
  panelSections: Surface<PanelSectionItem>;
  /** Field property overrides; the host feeds `resolve()` to its layout source. */
  fields: FieldsSurface;
  /** The Details form's list; its `tabs` overlay is fed to the same layout source. */
  form: FormSurface;
  /** A script's rows for the Activity tab, and the types it shows. */
  activity: ActivitySurface;
  /** A script's rows for the Files tab. */
  files: FilesSurface;
  /** The composer's writers; the host provides the built-in `comment`. */
  composer: ComposerSurface;
  /** What the host provides as `CommitKey`: a field's commit fires its handler through it. */
  commits: RecordCommitChannel;
  /** The replay: clears every surface, then runs every source's `refresh` in run order. */
  refresh: (options?: RefreshOptions) => Promise<void>;
  /** Replays and commits before it returns true; false, having run nothing, while scripts or permissions load. */
  paintNow: () => boolean;
  /** `row` addresses the child row a dotted event happened to; see `Handler`. */
  fireEvent: (event: string, row?: RowAddress) => Promise<void>;
  /** Fires `onPost` with the posted row's key, once the server has answered the built-in writer. */
  firePost: (key: string) => Promise<void>;
  /** Fetches the `page.cached` keys `paintNow` read, for the host's background reads; answers when they land or at the late limit. */
  fetchCached: () => Promise<void>;
  /** Runs script code the host calls outside an event, so its ops paint once, when it finishes. */
  hold: <T>(work: () => Promise<T> | T) => Promise<T>;
  /** True from a `page.save()` until its `afterSave` settles. */
  isSaving: ComputedRef<boolean>;
  /** True once the first replay has painted, or the first paint went ahead without a late script. */
  ready: Ref<boolean>;
  /** True while a replay is staging; a host announcing a settled strip waits for it to go false. */
  isReplaying: ComputedRef<boolean>;
  /** The `open`/`form` dialogs on screen, for the host's `<PageDialogs>`. */
  dialogs: Ref<PageDialogEntry[]>;
  /** The reader left the page: closes its dialogs newest-first, each resolving `null`, and closes the `page` `onRefresh` and `onOpen` got. */
  leave: () => void;
}

export function createRecordPage(host: RecordPageHost): RecordPageController {
  const quickActions = new Surface<QuickAction>({ surface: "quickActions", keys: QUICK_ACTION_KEYS });
  const frame = new FrameSurface();
  const body = new BodySurface();
  const header = new HeaderSurface();
  const tabs = new Surface<TabItem>({ surface: "tabs", keys: TAB_ITEM_KEYS });
  const panelSections = new Surface<PanelSectionItem>({
    surface: "panelSections",
    keys: PANEL_SECTION_KEYS,
  });
  const permissions = createPagePermissions(host);
  const fields = new FieldsSurface({
    fields: () => host.meta.value?.fields,
    doc: () => host.doc.value,
    fieldAccess: (fieldname) => permissions.fieldAccess(fieldname),
    decorate: host.decorate,
    isSection: (name) => panelSections.has(name),
  });
  const formTabs = new FormTabsSurface({
    tabs: () => host.formLayout?.(),
    doc: () => host.doc.value,
  });
  const form = new FormSurface({ fields: () => host.meta.value?.fields }, formTabs);
  const heldActs = createHeldActs({
    isStaging: () => gate.isStaging(),
    inBackground: () => gate.inBackground(),
  });
  const activity = new ActivitySurface({
    rows: () => host.activityRows(),
    scrollTo: (key) => host.scrollToActivity(key),
    reload: () => host.reloadActivity(),
    take: heldActs.take,
  });
  const files = new FilesSurface({
    rows: () => host.fileRows(),
    reload: () => host.reloadFiles(),
  });
  const composer = new ComposerSurface(
    {
      openWriter: (name, options) => openWriter(name, options),
      closeWriter: () => host.closeWriter?.(),
      activeWriter: () => host.activeWriter?.() ?? "",
      windowState: () => host.windowState?.() ?? "docked",
      setWindow: (window) => host.setWindow?.(window),
    },
    heldActs.take,
    heldActs.drop,
  );
  const rows = createRows({
    doc: () => host.doc.value,
    fields: () => host.meta.value?.fields,
    childFields: host.childFields,
    dispatch: (event, row) => fireEvent(event, row),
  });
  const surfaces: Staging[] = [
    quickActions,
    frame,
    body,
    header,
    tabs,
    panelSections,
    fields,
    form,
    formTabs,
    activity,
    files,
    composer,
  ];

  Object.defineProperty(tabs, "active", { get: () => host.activeTab() });
  Object.defineProperty(formTabs, "active", {
    get: () => host.activeFormTab?.() ?? "",
  });

  let vocabularyChecked = false;

  Object.defineProperty(tabs, "activate", {
    value: (name: string) => activate("tabs", name),
  });
  Object.defineProperty(formTabs, "activate", {
    value: (identity: string) => activate("form.tabs", identity),
  });

  Object.defineProperty(panelSections, "open", {
    value: (name: string) => disclose(name, true),
  });
  Object.defineProperty(panelSections, "close", {
    value: (name: string) => disclose(name, false),
  });

  Object.defineProperty(fields, "focus", {
    value: (fieldname: string) => focusField(fieldname),
  });

  const cachedReads = new CachedReads(host.doctype, host.docname);

  const commits = createCommitChannel({
    dispatch: (event, row) => fireEvent(event, row),
  });

  const gate = createPaintGate({
    doctype: host.doctype,
    docname: host.docname,
    surfaces,
    sourcesReady: host.sourcesReady,
    permissionsReady: () => permissions.ready(),
    loaded: () =>
      permissions.loaded() && (!host.sourcesReady || clientScriptsLoaded(host.doctype)),
    runRefresh: (ran, beforeSources) =>
      runRefresh(ran, beforeSources ? replacedClientScripts(host.doctype) : undefined),
    fetchCached: () => cachedReads.fetchUnfetched(),
    runOpen: (registrations) => runOpen(registrations),
    warnUnknownHandlers: () => warnUnknownHandlers(),
    deliverHeldActs: heldActs.release,
    closeDialogs: () => dialogs.closeAll(),
  });
  const { hold } = gate;

  const dialogs = createPageDialogs({ isReplaying: () => gate.isReplaying.value, hold });

  const page: RecordPageApi = {
    doctype: host.doctype,
    docname: host.docname,
    // Exempt from the read-only rule: mutating the document *is* the API.
    get doc() {
      return host.doc.value;
    },
    get saved() {
      return readOnly(host.saved.value, SAVED_IS_READ_ONLY);
    },
    get meta() {
      return readOnly(host.meta.value, META_IS_READ_ONLY);
    },
    // Read-only goes outermost, so a write is refused before the unknown-right
    // advisory inside `permissions.perms()` gets to fire.
    get perms() {
      return readOnly(permissions.perms(), PERMS_ARE_READ_ONLY);
    },
    get roles() {
      return readOnly(permissions.roles(), ROLES_ARE_READ_ONLY);
    },
    fieldAccess: (fieldname) => permissions.fieldAccess(fieldname),
    get isDirty() {
      return host.isDirty();
    },
    quickActions,
    frame,
    body,
    header,
    tabs: tabs as unknown as TabsApi,
    panelSections: panelSections as unknown as PanelSectionsApi,
    fields,
    form,
    activity,
    files,
    composer,
    rows: rows.rows,
    save: () => save(),
    reload: () => (gate.hasLeft() ? Promise.resolve() : host.reload()),
    refresh: () => gate.refresh(),
    toast: {
      success: (message) => toast.success(message),
      error: (message) => toast.error(message),
    },
    dialog: dialogs.api,
    call: (method, params) => runMethod(method, params).then((envelope) => envelope.data),
    cached: <T>(key: string, fetch: () => Promise<T> | T) =>
      cachedReads.read(runningSource(), key, fetch) as T | undefined,
    // The one member handed straight through, and the only one; see frontend/CLAUDE.md.
    router: host.router,
  };

  const refreshView = pageView(page);

  // One sequence at a time: a second `page.save()` mid-flight joins it, so no handler fires twice.
  const saving = shallowRef<Promise<void> | null>(null);

  /** The one save path: a clean doc resolves at once, a `beforeSave` throw sends nothing, and it paints once. */
  function save() {
    if (gate.hasLeft() || !host.isDirty()) return Promise.resolve();
    saving.value ??= hold(runSave).finally(() => (saving.value = null));
    return saving.value;
  }

  async function runSave() {
    await commits.flush();
    try {
      await fireEvent("beforeSave");
    } catch (error) {
      throw asVeto(error);
    }
    if (gate.hasLeft()) return;
    await host.save();
    await fireEvent("afterSave");
  }

  function focusField(fieldname: string) {
    if (!canFocus(fieldname)) return;
    const act: HeldAct = {
      kind: "focus",
      target: "",
      isDrawn: () => fields.isDrawn(fieldname),
      land: () => {
        if (canFocus(fieldname, "it left the form before the replay settled"))
          deliverFocus(fieldname);
      },
      refuse: (because) => warnFocus(fieldname, because),
    };
    if (!heldActs.take(act)) deliverFocus(fieldname);
  }

  function canFocus(fieldname: string, gone = "no such field") {
    if (!fields.has(fieldname)) {
      warnFocus(fieldname, gone);
      return false;
    }
    if (fields.get(fieldname)?.hidden) {
      warnFocus(fieldname, "it is hidden — show() reveals a field");
      return false;
    }
    return true;
  }

  function deliverFocus(fieldname: string) {
    if (!host.focusField) {
      warnFocus(fieldname, "this host draws no form");
      return;
    }
    try {
      host.focusField(fieldname, !fields.get(fieldname)?.read_only);
    } catch (error) {
      console.error(
        `[record-page] page.fields.focus("${fieldname}") — the host threw`,
        error,
      );
    }
  }

  function warnFocus(fieldname: string, because: string) {
    if (!import.meta.env.DEV) return;
    console.warn(
      `[record-page] page.fields.focus("${fieldname}") — ${because}; the reader was not moved.`,
    );
  }

  /** Both acts: a miss is said the way `activate` says one, and a hidden section is a miss. */
  function disclose(name: string, open: boolean) {
    if (!canDisclose(name, open)) return;
    const act: HeldAct = {
      kind: "disclose",
      target: name,
      isDrawn: () => panelSections.isDrawn(name),
      // Re-read, as a held activation is: a later source can hide or relabel the section.
      land: () => {
        if (canDisclose(name, open, "it left the panel before the replay settled"))
          deliverDisclosure(name, open);
      },
      refuse: (because) => warnDisclose(name, open, because),
    };
    if (!heldActs.take(act)) deliverDisclosure(name, open);
  }

  function canDisclose(name: string, open: boolean, gone = "no such section") {
    const item = panelSections.find(name);
    if (!item) {
      warnDisclose(name, open, gone);
      return false;
    }
    if (!panelSections.isVisible(name)) {
      warnDisclose(name, open, "it is hidden — show() reveals a section");
      return false;
    }
    // No label, no header, so there is nothing for the reader to open or shut.
    if (!item.label) {
      warnDisclose(name, open, "it has no header");
      return false;
    }
    return true;
  }

  function deliverDisclosure(name: string, open: boolean) {
    if (!host.discloseSection) {
      warnDisclose(name, open, "this host cannot open or shut a section");
      return;
    }
    try {
      host.discloseSection(name, open);
    } catch (error) {
      // Reported, never rethrown, for the reason `move` gives.
      console.error(
        `[record-page] page.panelSections.${open ? "open" : "close"}("${name}") — the host threw`,
        error,
      );
    }
  }

  function warnDisclose(name: string, open: boolean, because: string) {
    if (!import.meta.env.DEV) return;
    const verb = open ? "open" : "close";
    console.warn(
      `[record-page] page.panelSections.${verb}("${name}") — ${because}; nothing was ${open ? "opened" : "shut"}.`,
    );
  }

  function surfaceFor(strip: TabStrip) {
    return strip === "tabs" ? tabs : formTabs;
  }

  /** Both strips' `activate`: the interesting miss names the other strip, and only a caller holding both can say so. */
  function activate(strip: TabStrip, name: string) {
    if (!canReach(strip, name)) return;
    const act: HeldAct = {
      kind: "activate",
      target: strip,
      isDrawn: () => surfaceFor(strip).isDrawn(name),
      land: () => landActivation(strip, name),
      refuse: (because) => warnActivate(strip, name, because),
    };
    // Held until commit: until then the host still renders the last replay's strip, and a
    // move onto a tab not yet on it shows the fallback for a tick.
    if (!heldActs.take(act)) move(strip, name);
  }

  // Re-read, not replayed: a later source can hide the tab an earlier one
  // activated, and delivering that move would land the reader on the fallback.
  function landActivation(strip: TabStrip, name: string) {
    if (surfaceFor(strip).isVisible(name)) move(strip, name);
    else warnActivate(strip, name, "it left the strip before the replay settled");
  }

  function canReach(strip: TabStrip, name: string) {
    // Until the Details layout lands, "never authored" and "not here yet" are the
    // same answer; an activation is never queued, so the move is dropped either way.
    if (strip === "form.tabs" && !host.formLayout?.()?.length) return false;
    const here = surfaceFor(strip);
    const there = surfaceFor(STRIPS[strip].sibling);
    if (!here.has(name)) {
      warnActivate(
        strip,
        name,
        there.has(name)
          ? `it is on the ${STRIPS[strip].other} strip — page.${STRIPS[strip].sibling}.activate("${name}")`
          : "no such tab",
      );
      return false;
    }
    // Hidden is a miss: `show()` is the verb that reveals a tab.
    if (!here.isVisible(name)) {
      warnActivate(strip, name, "it is hidden — show() reveals a tab");
      return false;
    }
    return true;
  }

  /** The host's half, and the only place the engine hands a strip a name. */
  function move(strip: TabStrip, name: string) {
    // A host that draws the form's strip but cannot move it must not swallow the move silently.
    if (strip === "form.tabs" && !host.activateFormTab) {
      warnActivate(strip, name, "this host cannot move the reader on that strip");
      return;
    }
    try {
      if (strip === "tabs") host.activateTab(name);
      else host.activateFormTab?.(name);
    } catch (error) {
      // Reported, never rethrown: a released move runs inside `refresh`'s `finally`,
      // and a throw here would leave `ready` false and the page stuck on its skeleton.
      console.error(
        `[record-page] page.${strip}.activate("${name}") — the host threw`,
        error,
      );
    }
  }

  /** Said every time, not once: a miss is an act just performed, not a standing fault in the script. */
  function warnActivate(strip: TabStrip, name: string, because: string) {
    if (!import.meta.env.DEV) return;
    console.warn(
      `[record-page] page.${strip}.activate("${name}") — ${because}; the reader was not moved.`,
    );
  }

  /** `page.composer.open`'s host half: the reader first moves to a tab that draws the band. */
  function openWriter(name: string, options: ComposerOpenOptions) {
    const tab = composerTab(tabs.visible(), host.activeTab());
    if (!tab) return warnOpen(name, "no tab on the strip draws the composer");
    if (!host.openWriter) return warnOpen(name, "this host draws no composer");
    if (tab !== host.activeTab()) activate("tabs", tab);
    host.openWriter(name, options);
  }

  function warnOpen(name: string, because: string) {
    if (!import.meta.env.DEV) return;
    console.warn(
      `[record-page] page.composer.open("${name}") — ${because}; nothing was opened.`,
    );
  }

  async function fireEvent(event: string, row?: RowAddress) {
    // One handle for the whole dispatch, and the same object `page.rows()` hands back.
    const detail = row ? rows.handle(row) : undefined;
    await hold(() => dispatch(event, detail));
  }

  function firePost(key: string) {
    return hold(() => dispatch("onPost", { name: key }));
  }

  async function dispatch(event: string, detail?: PageRow | PostedRow) {
    for (const { source, handlers } of registrationsFor(host.doctype)) {
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
    for (const registration of registrationsFor(host.doctype)) {
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
    const view = host.restoresView?.() ? restoredView() : refreshView.page;
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

  /** The `page` `onOpen` gets when the host puts back the reader's view: its view acts warn and do nothing. */
  function restoredView(): RecordPageApi {
    const skipped: Record<string, unknown> = {
      tabs: overriding(page.tabs, {
        activate: (name: string) => {
          if (canReach("tabs", name)) warnActivate("tabs", name, RESTORED_VIEW);
        },
      }),
      form: overriding(page.form, {
        tabs: overriding(page.form.tabs, {
          activate: (identity: string) => {
            if (canReach("form.tabs", identity)) warnActivate("form.tabs", identity, RESTORED_VIEW);
          },
        }),
      }),
      panelSections: overriding(page.panelSections, {
        open: (name: string) => {
          if (canDisclose(name, true)) warnDisclose(name, true, RESTORED_VIEW);
        },
        close: (name: string) => {
          if (canDisclose(name, false)) warnDisclose(name, false, RESTORED_VIEW);
        },
      }),
      fields: overriding(page.fields, {
        focus: (fieldname: string) => {
          if (canFocus(fieldname)) warnFocus(fieldname, RESTORED_VIEW);
        },
      }),
      activity: overriding(page.activity, {
        scrollTo: (key: string) => activity.refuseScroll(key, RESTORED_VIEW),
      }),
      composer: overriding(page.composer, {
        // A writer the reader cannot open goes to the real act, which says why and opens nothing.
        open: (name: string, options?: ComposerOpenOptions) =>
          composer.isVisible(name) ? warnOpen(name, RESTORED_VIEW) : composer.open(name, options),
      }),
    };
    return new Proxy(refreshView.page, {
      get: (view, key) => {
        const member = Reflect.get(view, key);
        return member !== INERT && Object.hasOwn(skipped, key) ? skipped[key as string] : member;
      },
    });
  }

  // Filed in production too, so an admin sees which scripts to move to a cached read.
  function warnAsyncRefresh(source: string) {
    const message = `[record-page] ${source}.onRefresh on ${host.doctype} returned a promise; onRefresh should be synchronous, and read server data with page.cached(key, fetcher). The first paint waits up to 500 ms for what it does after its first await; after that it lands as a later paint.`;
    if (import.meta.env.DEV) console.warn(message);
    reportCustomizationError(new Error(message), {
      source,
      event: "onRefresh (async)",
      doctype: host.doctype,
      record: host.docname,
    });
  }

  function reportHandlerError(source: string, event: string, error: unknown) {
    // `beforeSave` rethrows to abort the save and is not reported: the user
    // is looking straight at a failed save, and a working veto is not an error.
    if (event === "beforeSave") throw error;
    console.error(`[record-page] ${source}.${event} on ${host.doctype} threw`, error);
    // No `route`: the reporter reads `location`, the URL an admin can paste;
    // `router.fullPath` drops the app's base.
    reportCustomizationError(error, {
      source,
      event,
      doctype: host.doctype,
      record: host.docname,
    });
  }

  // Meta can lag the first paint, so the check waits for a replay that has fields.
  function warnUnknownHandlers() {
    if (!import.meta.env.DEV) return;
    const fields = host.meta.value?.fields;
    if (!fields) return;
    const registrations = registrationsFor(host.doctype);
    // With no source registered, warning would fire on every record a plain app opens.
    if (!registrations.length) return;
    // Not behind the latch below: this reads the child meta, which can land after
    // the parent's, and `warnRowIssue` remembers what it has already said.
    warnShadowedChildFields(fields);
    if (vocabularyChecked) return;
    vocabularyChecked = true;
    const known = handlerVocabulary(fields, host.childFields);
    const said = new Set<string>();
    for (const { source, handlers } of registrations)
      for (const key of Object.keys(handlers)) {
        if (known.has(key)) continue;
        // A block under a fieldname that holds no rows is one mistake, named by its table.
        const [table] = key.split(".");
        const nested = key.includes(".") && !known.isTable(table);
        const message = nested
          ? `${source}.${table} on ${host.doctype} is not a child table — nothing nested under it will fire`
          : `${source}.${key} on ${host.doctype} is neither an event nor a fieldname — it will never fire`;
        if (said.has(message)) continue;
        said.add(message);
        console.warn(`[record-page] ${message}`);
      }
  }

  /**
   * Frappe reserves none of the three names the row vocabulary occupies. A child
   * field named `onAdd` commits as the string the row-added event dispatches, so it misfires.
   */
  function warnShadowedChildFields(fields: RawMetaField[]) {
    for (const field of fields) {
      if (!holdsChildRows(field.fieldtype) || !field.options) continue;
      const child = host.childFields?.(field.options);
      if (!child) continue;
      const has = (fieldname: string) =>
        child.some((one) => one.fieldname === fieldname);
      if (has("trigger"))
        // Once per child doctype for the session; navigating between records must not restate it.
        warnRowIssue(
          `${field.options}.trigger is shadowed by the row handle's own trigger() — read it from page.doc.${field.fieldname} instead`,
        );
      for (const lifecycle of Object.values(ROW_EVENTS))
        if (has(lifecycle))
          warnRowIssue(
            `${field.options}.${lifecycle} collides with the table's ${lifecycle} handler — editing that field on a row fires ${field.fieldname}.${lifecycle} as though a row had been ${lifecycle === ROW_EVENTS.add ? "added" : "removed"}. Rename the field, or handle it from page.doc.${field.fieldname}`,
          );
    }
  }

  return {
    page,
    quickActions,
    frame,
    body,
    header,
    tabs,
    panelSections,
    fields,
    form,
    activity,
    files,
    composer,
    commits,
    refresh: gate.refresh,
    paintNow: gate.paintNow,
    fireEvent,
    firePost,
    fetchCached: gate.fetchCached,
    hold,
    isSaving: computed(() => saving.value !== null),
    ready: gate.ready,
    isReplaying: gate.isReplaying,
    dialogs: dialogs.entries,
    leave: () => {
      refreshView.close();
      gate.leave();
    },
  };
}

/**
 * The whole vocabulary a handler key may be drawn from. A Table's bare fieldname is
 * not in it: nothing commits under a table's own name, so `products() {}` would never fire.
 */
function handlerVocabulary(
  fields: RawMetaField[],
  childFields?: (doctype: string) => RawMetaField[] | undefined,
) {
  const known = new Set(RECORD_PAGE_EVENTS);
  const tables = new Set<string>();
  // Tables whose child meta has not landed must not make a correct key look like
  // a typo, so they are answered by prefix.
  const unresolved: string[] = [];
  for (const field of fields) {
    if (!holdsChildRows(field.fieldtype)) {
      known.add(field.fieldname);
      continue;
    }
    tables.add(field.fieldname);
    known.add(`${field.fieldname}.${ROW_EVENTS.add}`);
    known.add(`${field.fieldname}.${ROW_EVENTS.remove}`);
    // A Table MultiSelect has no per-cell editing, so its vocabulary is add and remove alone.
    if (field.fieldtype !== "Table") continue;
    const child = field.options && childFields?.(field.options);
    if (!child) unresolved.push(field.fieldname);
    // A layout break has no value and so no commit; `page.fields` excludes them too.
    else
      for (const one of child)
        if (!LAYOUT_BREAKS.has(one.fieldtype))
          known.add(`${field.fieldname}.${one.fieldname}`);
  }
  return {
    has: (key: string) =>
      known.has(key) || unresolved.some((table) => key.startsWith(`${table}.`)),
    isTable: (fieldname: string) => tables.has(fieldname),
  };
}
