// Builds the curated `page` and the controller that fires events into it.
// Handlers run serially in run order, each in its own try/catch: a thrower is
// skipped half-applied, never taking the page or another source down with it.
// The one exception is `beforeSave`, the veto point: its throw aborts the save.
import { computed, ref, type ComputedRef, type Ref } from "vue";
import type { Router } from "vue-router";
import { call, toast } from "frappe-ui";
import { withRunningSource } from "./context";
import { createPageDialogs, type PageDialogEntry } from "./dialog";
import type { Decorator } from "../../components/FormLayout/buildLayoutFromMeta";
import type {
  FormLayoutSchema,
  RawMetaField,
} from "../../components/FormLayout/types";
import { holdsChildRows } from "../../components/Fields/rowIdentity";
import type { RowAddress } from "../../components/Fields/types";
import { FieldsSurface, LAYOUT_BREAKS } from "./fields";
import { FormTabsSurface } from "./formTabs";
import { HeaderActionsSurface } from "./headerRenderings";
import { ROW_EVENTS } from "./flattenHandlers";
import { withRemovals } from "./pageCompatibility";
import { createPagePermissions } from "./pagePermissions";
import { readOnly, type ReadOnlyAdvice } from "./readOnly";
import { registrationsFor } from "./registry";
import { reportCustomizationError } from "./reportError";
import { createRows, warnRowIssue } from "./rows";
import { Surface } from "./surface";
import type {
  PanelSectionItem,
  QuickAction,
  RecordPageApi,
  TabItem,
  TabsApi,
} from "./types";

/** The closed event vocabulary (wayfinder ticket 14); every other key is a fieldname. */
export const RECORD_PAGE_EVENTS = [
  "onRefresh",
  "beforeSave",
  "afterSave",
  "onTabChange",
  "onFormTabChange",
];

// Everything `page` hands back is read-only (ticket 47), and each member names
// the verb that does support what the write was reaching for — a refusal that
// names nothing is a removal wearing a Proxy.
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

// The two differ by one letter and hold structurally identical objects, so
// `page.saved.qty = 5` is a plausible typo for `page.doc.qty = 5` — and it would
// otherwise silently rewrite the baseline `isDirty`, the layout conditions and
// the conflict path all read.
const SAVED_IS_READ_ONLY: ReadOnlyAdvice = {
  path: "page.saved",
  instead: "page.doc, which is the draft this is the saved counterpart of",
};

/** The two tab strips, by the member each is reached through. */
type TabStrip = "tabs" | "formTabs";

const STRIPS: Record<TabStrip, { other: string; sibling: TabStrip }> = {
  tabs: { other: "form's", sibling: "formTabs" },
  formTabs: { other: "record's", sibling: "tabs" },
};

export interface RecordPageHost {
  doctype: string;
  docname: string;
  doc: Ref<Record<string, any>>;
  /** The document as the server last showed it; the draft's baseline. */
  saved: Ref<Record<string, any>>;
  meta: Ref<any>;
  /** `docinfo.permissions` as `getdoc` gave it; the engine curates it. */
  perms: () => Record<string, any>;
  isDirty: () => boolean;
  /** The name of the tab the reader is on, as the host's strip resolves it. */
  activeTab: () => string;
  /**
   * Move the reader to a named tab of the record's strip — `activeTab`'s
   * symmetric partner, and the host's half of `page.tabs.activate`. The engine
   * has already resolved the name against the strip, so this is handed only
   * tabs that are there and on screen; how a strip *records* where the reader is
   * — a URL query here, a ref elsewhere — stays the host's business, which is
   * what keeps activation from having to be spelled as a `page.router` edit.
   */
  activateTab: (name: string) => void;
  /**
   * The record's Details layout, which is the strip `page.formTabs` addresses.
   * Absent for a host that renders no form.
   */
  formLayout?: () => FormLayoutSchema | undefined;
  /**
   * The **identity** of the Form Layout tab the reader is on, as `FormLayout`
   * resolves it and the host's strip reports it, or `''` when the reader is not
   * looking at the form.
   */
  activeFormTab?: () => string;
  /**
   * Move the reader to a tab of the form, by identity. Optional on the same
   * terms as `activeFormTab`: a host that renders no form has no strip to move,
   * and one absent here simply never receives an activation, because the
   * identity will have missed against an empty layout first.
   */
  activateFormTab?: (identity: string) => void;
  save: () => Promise<void>;
  reload: () => Promise<void>;
  router: Router;
  /**
   * The per-field UI overlay hook the host also passes its layout source. Only
   * `page.fields.get` reads it here, and only so its answer cannot disagree
   * with what the host actually renders.
   */
  decorate?: Decorator;
  /**
   * A child doctype's meta fields, by doctype name — what makes the row half of
   * the event vocabulary knowable. Absent while the metas load, and for a host
   * that has none: the tables then speak `.onAdd` / `.onRemove` only, which is
   * what the vocabulary check assumes rather than warns about.
   */
  childFields?: (doctype: string) => RawMetaField[] | undefined;
  /** Resolves when sources that register after mount (Page Scripts) are in. */
  sourcesReady?: () => Promise<void>;
}

export interface RecordPageController {
  page: RecordPageApi;
  quickActions: Surface<QuickAction>;
  headerActions: HeaderActionsSurface;
  tabs: Surface<TabItem>;
  panelSections: Surface<PanelSectionItem>;
  /** Field property overrides; the host feeds `resolve()` to its layout source. */
  fields: FieldsSurface;
  /** Form Layout tab overrides; fed to the same layout source alongside them. */
  formTabs: FormTabsSurface;
  /** The replay: clears every surface, then runs every source's `refresh` in run order. */
  refresh: () => Promise<void>;
  /** `row` addresses the child row a dotted event happened to; see `Handler`. */
  fireEvent: (event: string, row?: RowAddress) => Promise<void>;
  /** True once the first replay has run — before it, surfaces are only built-ins. */
  ready: Ref<boolean>;
  /**
   * True while a replay is staging. Reactive because a host that announces a
   * *settled* strip has to wait for the commit, and the commit is the moment
   * this goes false.
   */
  isReplaying: ComputedRef<boolean>;
  /** The `open`/`form` dialogs on screen, for the host's `<PageDialogs>`. */
  dialogs: Ref<PageDialogEntry[]>;
  /** Closes them newest-first, each promise resolving `null`. */
  closeDialogs: () => void;
}

export function createRecordPage(host: RecordPageHost): RecordPageController {
  const quickActions = new Surface<QuickAction>();
  const headerActions = new HeaderActionsSurface();
  const tabs = new Surface<TabItem>();
  const panelSections = new Surface<PanelSectionItem>();
  const permissions = createPagePermissions(host);
  const fields = new FieldsSurface({
    fields: () => host.meta.value?.fields,
    doc: () => host.doc.value,
    fieldAccess: (fieldname) => permissions.fieldAccess(fieldname),
    decorate: host.decorate,
  });
  const formTabs = new FormTabsSurface({
    tabs: () => host.formLayout?.(),
    doc: () => host.doc.value,
  });
  const rows = createRows({
    doc: () => host.doc.value,
    fields: () => host.meta.value?.fields,
    childFields: host.childFields,
    dispatch: (event, row) => fireEvent(event, row),
  });
  // Every overlay a replay stages. `fields` and `formTabs` are not `Surface`s —
  // they override properties rather than arranging items — but they stage here.
  const surfaces: { beginReplay: () => void; commitReplay: () => void }[] = [
    quickActions,
    headerActions,
    tabs,
    panelSections,
    fields,
    formTabs,
  ];

  Object.defineProperty(tabs, "active", { get: () => host.activeTab() });
  // The same shape as the record strip's: `active` is stored nowhere here
  // either, it is a read into whichever strip the host is drawing.
  Object.defineProperty(formTabs, "active", {
    get: () => host.activeFormTab?.() ?? "",
  });

  const ready = ref(false);
  let vocabularyChecked = false;
  const replaying = ref(0);
  const isReplaying = computed(() => replaying.value > 0);

  // An activation made while a replay is in flight, held until it commits — one
  // name per strip, so a second call replaces the first the way the reader's own
  // last move would. This is not the queueing `activate` refuses: the name is
  // resolved at the moment of the call, against the strip the caller can see
  // (`isVisible` reads the staged ops, as `has` does). Only the *delivery*
  // waits, because until the commit the host is still rendering last replay's
  // strip, and moving the reader to a tab that is not on it yet would show them
  // the fallback for a tick — the replay's middle, leaking through the one
  // channel ticket 71's staging does not cover. That is true of any activation
  // made in the window, not only the ones the replay's own handlers make, which
  // is why the gate is `isReplaying` and not "am I inside `onRefresh`".
  const heldActivations = new Map<TabStrip, string>();

  Object.defineProperty(tabs, "activate", {
    value: (name: string) => activate("tabs", name),
  });
  Object.defineProperty(formTabs, "activate", {
    value: (identity: string) => activate("formTabs", identity),
  });

  const dialogs = createPageDialogs({ isReplaying: () => isReplaying.value });

  const capabilities: RecordPageApi = {
    doctype: host.doctype,
    docname: host.docname,
    // Exempt from the read-only rule below, and deliberately: mutating the
    // document *is* the API. Do not "fix" this.
    get doc() {
      return host.doc.value;
    },
    get saved() {
      return readOnly(host.saved.value, SAVED_IS_READ_ONLY);
    },
    get meta() {
      return readOnly(host.meta.value, META_IS_READ_ONLY);
    },
    // Read-only goes outermost, so a write is refused before the DEV-only
    // unknown-right advisory inside `permissions.perms()` gets to fire.
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
    headerActions,
    tabs: tabs as unknown as TabsApi,
    panelSections,
    fields,
    formTabs,
    rows: rows.rows,
    save: () => host.save(),
    reload: () => host.reload(),
    refresh: () => refresh(),
    toast: {
      success: (message) => toast.success(message),
      error: (message) => toast.error(message),
    },
    dialog: dialogs.api,
    call: (method, params) => call(method, params),
    // The one member handed straight through: it is vue-router's object, not
    // ours, so neither the inbound nor the outbound rule catches it. That is a
    // real cost, not a technicality, and COMPATIBILITY.md's "The one
    // hand-through" section now states it and the two rules that bound it —
    // chiefly that no capability may *require* the router. Do not "fix" this
    // by deleting the member, and do not hand a second one through on its
    // precedent.
    router: host.router,
  };

  // Nothing has been removed yet, so this hands the same object straight back:
  // the guard, and its cost on every member read in every handler, exists only
  // once the removals list has something to say (ticket 20 §4).
  const page = withRemovals(capabilities);

  async function refresh() {
    await Promise.all([host.sourcesReady?.(), permissions.ready()]);
    warnUnknownHandlers();
    // Counted, not a boolean: a script's own `page.refresh()` re-enters this.
    replaying.value += 1;
    // Staged, not cleared: clearing here and re-adding one microtask later is
    // what tore the rendered strip down between the two, taking the reader's
    // place in it with them (ticket 70). The surfaces publish on commit, in one
    // flush, so the host only ever sees a replay's result.
    for (const surface of surfaces) surface.beginReplay();
    try {
      await fireEvent("onRefresh");
    } finally {
      // In `finally` so a throwing handler cannot leave the page staged, which
      // would freeze the overlay on the previous replay for good.
      for (const surface of surfaces) surface.commitReplay();
      replaying.value -= 1;
      // After the commit, so the strip the reader is being moved onto is the one
      // on screen; and inside the same `finally`, so a throwing handler cannot
      // strand a move that had already been decided.
      if (!isReplaying.value) releaseActivations();
    }
    ready.value = true;
  }

  function releaseActivations() {
    const held = [...heldActivations];
    heldActivations.clear();
    for (const [strip, name] of held) {
      // Re-read, not replayed. The strip a held move was decided against is not
      // the one that necessarily settled: a later source can hide the tab an
      // earlier one activated, and delivering that move would land the reader on
      // the strip's fallback — the very outcome a miss exists to prevent. A tab
      // that left before the strip settled is a miss like any other.
      if (!surfaceFor(strip).isVisible(name)) {
        warnActivate(strip, name, "it left the strip before the replay settled");
        continue;
      }
      move(strip, name);
    }
  }

  function surfaceFor(strip: TabStrip) {
    return strip === "tabs" ? tabs : formTabs;
  }

  /**
   * `page.tabs.activate` and `page.formTabs.activate`, both of them, because the
   * interesting miss is the one that names the *other* strip: the two are not
   * interchangeable, an author will mix them up, and only a caller holding both
   * can say which one they wanted. The engine resolves the name and the host
   * moves the reader — activation never reaches for `page.router`.
   */
  function activate(strip: TabStrip, name: string) {
    if (!canReach(strip, name)) return;
    if (isReplaying.value) heldActivations.set(strip, name);
    else move(strip, name);
  }

  function canReach(strip: TabStrip, name: string) {
    // The Details layout can land after the first replay has run, and until it
    // does, "the administrator never authored this" and "it is not here yet"
    // are the same answer — which is why `FormTabsSurface.warnIfAbsent` holds
    // its tongue in the same window. The move is dropped either way: an
    // activation is resolved at the moment of the call and is not queued.
    if (strip === "formTabs" && !host.formLayout?.()?.length) return false;
    const here = surfaceFor(strip);
    const there = surfaceFor(strip === "tabs" ? "formTabs" : "tabs");
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
    // Hidden is a miss and not an invitation: `show()` is the verb that reveals
    // a tab, and one call should not quietly perform two.
    if (!here.isVisible(name)) {
      warnActivate(strip, name, "it is hidden — show() reveals a tab");
      return false;
    }
    return true;
  }

  /** The host's half, and the only place the engine hands a strip a name. */
  function move(strip: TabStrip, name: string) {
    // A host that draws the form's strip but cannot move it would otherwise
    // swallow an activation that passed every check — the one silent failure
    // this verb exists to abolish.
    if (strip === "formTabs" && !host.activateFormTab) {
      warnActivate(strip, name, "this host cannot move the reader on that strip");
      return;
    }
    try {
      if (strip === "tabs") host.activateTab(name);
      else host.activateFormTab?.(name);
    } catch (error) {
      // Reported, never rethrown: a released move runs inside `refresh`'s
      // `finally`, so a throwing host hook would take the rest of the release
      // with it and leave `ready` false — a page stuck on its skeleton because
      // a router guard said no.
      console.error(
        `[record-page] page.${strip}.activate("${name}") — the host threw`,
        error,
      );
    }
  }

  /**
   * Said every time, not once: a miss here is an act the script just performed —
   * the reader was not moved — rather than a standing fault in its text, and the
   * second failed move is not the first one repeated.
   */
  function warnActivate(strip: TabStrip, name: string, because: string) {
    if (!import.meta.env.DEV) return;
    console.warn(
      `[record-page] page.${strip}.activate("${name}") — ${because}; the reader was not moved.`,
    );
  }

  async function fireEvent(event: string, row?: RowAddress) {
    // One handle for the whole dispatch, and the same object `page.rows()` hands
    // back: it is an address, so every source is looking at the same live row.
    const handle = row ? rows.handle(row) : undefined;
    for (const { source, handlers } of registrationsFor(host.doctype)) {
      const handler = handlers[event];
      if (!handler) continue;
      await withRunningSource(source, async () => {
        try {
          await handler(page, handle);
        } catch (error) {
          // `beforeSave` rethrows to abort the save, and is the one catch site
          // that does not report: the user is looking straight at a failed save,
          // so logging it would file a working veto as an error.
          if (event === "beforeSave") throw error;
          console.error(
            `[record-page] ${source}.${event} on ${host.doctype} threw`,
            error,
          );
          // No `route`: the reporter reads `location`, which is the URL an admin
          // can paste. `router.fullPath` drops the app's base and would make this
          // one site disagree with the other three.
          reportCustomizationError(error, {
            source,
            event,
            doctype: host.doctype,
            record: host.docname,
          });
        }
      });
    }
  }

  // Meta can lag the first paint, so the check waits for a replay that has fields.
  function warnUnknownHandlers() {
    if (!import.meta.env.DEV) return;
    const fields = host.meta.value?.fields;
    if (!fields) return;
    const registrations = registrationsFor(host.doctype);
    // Nothing to shadow and no keys to check when no source is registered — and
    // saying so anyway would fire the warning on every record a plain app opens.
    if (!registrations.length) return;
    // Deliberately *not* behind the latch below: this one reads the **child**
    // meta, which can land after the parent's — `handlerVocabulary`'s
    // `unresolved` list exists for exactly that window — so latching on the
    // parent alone would drop the collision warning for the whole session.
    // Re-attempting it costs a loop over the tables, and `warnRowIssue`
    // remembers what it has already said.
    warnShadowedChildFields(fields);
    if (vocabularyChecked) return;
    vocabularyChecked = true;
    const known = handlerVocabulary(fields, host.childFields);
    const said = new Set<string>();
    for (const { source, handlers } of registrations)
      for (const key of Object.keys(handlers)) {
        if (known.has(key)) continue;
        // A whole block written under a fieldname that holds no rows is one
        // mistake, not one per handler in it — so it is named by its table.
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
   * The three child fieldnames the table vocabulary occupies, named at load
   * because the engine knows the child's fields where v1 could only warn on
   * every access. Frappe reserves none of them (`RESERVED_KEYWORDS` is five
   * names plus the cached properties), so a child doctype may legitimately
   * carry any — and ticket 54 traded a guarantee for this warning knowingly.
   *
   * 54 called the result "an announced capability hole, never a misfire", and
   * for `trigger` that is exact. For the two lifecycle names it is not: a child
   * field named `onAdd` commits as `<table>.onAdd`, which is the *same string*
   * the row-added event dispatches, so the author's `onAdd` handler runs — with
   * a live row — on that field being edited. The hole is announced, but it is a
   * misfire, and the warning says so rather than the comfortable thing.
   */
  function warnShadowedChildFields(fields: RawMetaField[]) {
    for (const field of fields) {
      if (!holdsChildRows(field.fieldtype) || !field.options) continue;
      const child = host.childFields?.(field.options);
      if (!child) continue;
      const has = (fieldname: string) =>
        child.some((one) => one.fieldname === fieldname);
      // The verb wins and the field stays reachable through `page.doc`.
      if (has("trigger"))
        // Warned per child doctype for the session, not per controller: the same
        // shadow is the same fact on every record of the doctype, and navigating
        // between them must not restate it.
        warnRowIssue(
          `${field.options}.trigger is shadowed by the row handle's own trigger() — read it from page.doc.${field.fieldname} instead`,
        );
      // One string cannot be two events, and the field's commit is the one that
      // arrives unannounced — so the warning names the direction that bites.
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
    headerActions,
    tabs,
    panelSections,
    fields,
    formTabs,
    refresh,
    fireEvent,
    ready,
    isReplaying,
    dialogs: dialogs.entries,
    closeDialogs: dialogs.closeAll,
  };
}

/**
 * The whole vocabulary a handler key may be drawn from (tickets 44, 45): the
 * four events, every parent fieldname, and — for a child table — the dotted
 * family and nothing else.
 *
 * A Table fieldtype's **bare** fieldname is deliberately not here. It was only
 * ever firable because the deleted deep watch could not tell one row's edit from
 * another's, so a table has no control that commits under its own name; leaving
 * it in would accept `products() {}` silently and never fire it.
 */
function handlerVocabulary(
  fields: RawMetaField[],
  childFields?: (doctype: string) => RawMetaField[] | undefined,
) {
  const known = new Set(RECORD_PAGE_EVENTS);
  // Every child table on the doctype, so a nested block written under something
  // that is not one can be named as that rather than as a generic typo.
  const tables = new Set<string>();
  // Tables whose child doctype we cannot see. A host with no `childFields`, or
  // one whose child meta has not landed, must not accuse a correct key of being
  // a typo — so those tables are answered by prefix instead.
  const unresolved: string[] = [];
  for (const field of fields) {
    if (!holdsChildRows(field.fieldtype)) {
      known.add(field.fieldname);
      continue;
    }
    tables.add(field.fieldname);
    known.add(`${field.fieldname}.${ROW_EVENTS.add}`);
    known.add(`${field.fieldname}.${ROW_EVENTS.remove}`);
    // A Table MultiSelect has no per-cell editing, so its vocabulary is add and
    // remove alone — an honest gap rather than keys that would never fire.
    if (field.fieldtype !== "Table") continue;
    const child = field.options && childFields?.(field.options);
    if (!child) unresolved.push(field.fieldname);
    // A layout break has no value and so no commit; `page.fields` excludes them
    // for the same reason, and accepting one here would be a key that never fires.
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
