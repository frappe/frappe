// Builds the curated `page` and the controller that fires events into it. Handlers
// run serially, each in its own try/catch; only a `beforeSave` throw aborts anything.
import { computed, ref, type ComputedRef, type Ref } from "vue";
import type { Router } from "vue-router";
import { call, toast } from "frappe-ui";
import { withRunningSource } from "./context";
import { createPageDialogs, type PageDialogEntry } from "./dialog";
import type { Decorator } from "@framework/ui/components/FormLayout/buildLayoutFromMeta";
import type {
  FormLayoutSchema,
  RawMetaField,
} from "@framework/ui/components/FormLayout/types";
import { holdsChildRows } from "@framework/ui/components/Fields/rowIdentity";
import type { RowAddress } from "@framework/ui/components/Fields/types";
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

/** The closed event vocabulary; every other key is a fieldname. */
export const RECORD_PAGE_EVENTS = [
  "onRefresh",
  "beforeSave",
  "afterSave",
  "onTabChange",
  "onFormTabChange",
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
  /** Moves the reader to a tab of the record's strip; the engine has already resolved the name. */
  activateTab: (name: string) => void;
  /** The record's Details layout, which `page.formTabs` addresses; absent for a host with no form. */
  formLayout?: () => FormLayoutSchema | undefined;
  /** The identity of the Form Layout tab the reader is on, or `''` outside the form. */
  activeFormTab?: () => string;
  /** Moves the reader to a tab of the form, by identity; absent for a host with no form. */
  activateFormTab?: (identity: string) => void;
  save: () => Promise<void>;
  reload: () => Promise<void>;
  router: Router;
  /** The host's per-field overlay hook; `page.fields.get` reads it to match what renders. */
  decorate?: Decorator;
  /** A child doctype's meta fields, by doctype name; absent while the metas load. */
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
  /** True while a replay is staging; a host announcing a settled strip waits for it to go false. */
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
  // Every overlay a replay stages; `fields` and `formTabs` are not `Surface`s but stage here.
  const surfaces: { beginReplay: () => void; commitReplay: () => void }[] = [
    quickActions,
    headerActions,
    tabs,
    panelSections,
    fields,
    formTabs,
  ];

  Object.defineProperty(tabs, "active", { get: () => host.activeTab() });
  Object.defineProperty(formTabs, "active", {
    get: () => host.activeFormTab?.() ?? "",
  });

  const ready = ref(false);
  let vocabularyChecked = false;
  const replaying = ref(0);
  const isReplaying = computed(() => replaying.value > 0);

  // Resolved at the call, delivered on commit: until then the host still renders the
  // last replay's strip, and a move onto a tab not yet on it shows the fallback for a tick.
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
    // The one member handed straight through, and the only one; see frontend/CLAUDE.md.
    router: host.router,
  };

  // With an empty removals list this hands the same object straight back.
  const page = withRemovals(capabilities);

  async function refresh() {
    await Promise.all([host.sourcesReady?.(), permissions.ready()]);
    warnUnknownHandlers();
    // Counted, not a boolean: a script's own `page.refresh()` re-enters this.
    replaying.value += 1;
    // Staged, not cleared: clearing here and re-adding a microtask later tears the
    // rendered strip down between the two, and the reader's place in it with them.
    for (const surface of surfaces) surface.beginReplay();
    try {
      await fireEvent("onRefresh");
    } finally {
      // In `finally` so a throwing handler cannot leave the page staged for good.
      for (const surface of surfaces) surface.commitReplay();
      replaying.value -= 1;
      // After the commit, so the strip the reader lands on is the one on screen;
      // inside the `finally`, so a throwing handler cannot strand a decided move.
      if (!isReplaying.value) releaseActivations();
    }
    ready.value = true;
  }

  function releaseActivations() {
    const held = [...heldActivations];
    heldActivations.clear();
    for (const [strip, name] of held) {
      // Re-read, not replayed: a later source can hide the tab an earlier one
      // activated, and delivering that move would land the reader on the fallback.
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

  /** Both strips' `activate`: the interesting miss names the other strip, and only a caller holding both can say so. */
  function activate(strip: TabStrip, name: string) {
    if (!canReach(strip, name)) return;
    if (isReplaying.value) heldActivations.set(strip, name);
    else move(strip, name);
  }

  function canReach(strip: TabStrip, name: string) {
    // Until the Details layout lands, "never authored" and "not here yet" are the
    // same answer; an activation is never queued, so the move is dropped either way.
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
    if (strip === "formTabs" && !host.activateFormTab) {
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

  async function fireEvent(event: string, row?: RowAddress) {
    // One handle for the whole dispatch, and the same object `page.rows()` hands back.
    const handle = row ? rows.handle(row) : undefined;
    for (const { source, handlers } of registrationsFor(host.doctype)) {
      const handler = handlers[event];
      if (!handler) continue;
      await withRunningSource(source, async () => {
        try {
          await handler(page, handle);
        } catch (error) {
          // `beforeSave` rethrows to abort the save and is not reported: the user
          // is looking straight at a failed save, and a working veto is not an error.
          if (event === "beforeSave") throw error;
          console.error(
            `[record-page] ${source}.${event} on ${host.doctype} threw`,
            error,
          );
          // No `route`: the reporter reads `location`, the URL an admin can paste;
          // `router.fullPath` drops the app's base.
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
