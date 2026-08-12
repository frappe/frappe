// Builds the curated `page` and the controller that fires events into it.
// Handlers run serially in run order, each in its own try/catch: a thrower is
// skipped half-applied, never taking the page or another source down with it.
// The one exception is `before_save`, the veto point: its throw aborts the save.
import { ref, type Ref } from "vue";
import type { Router } from "vue-router";
import { call, toast } from "frappe-ui";
import { withRunningSource } from "./context";
import { registrationsFor } from "./registry";
import { Surface } from "./surface";
import type {
  HeaderAction,
  PanelSectionItem,
  QuickAction,
  RecordPageApi,
  TabItem,
  TabsApi,
} from "./types";

/** The closed event vocabulary (wayfinder ticket 14); every other key is a fieldname. */
export const RECORD_PAGE_EVENTS = [
  "refresh",
  "before_save",
  "after_save",
  "on_tab_change",
];

export interface RecordPageHost {
  doctype: string;
  docname: string;
  doc: Ref<Record<string, any>>;
  meta: Ref<any>;
  perms: () => Record<string, any>;
  isDirty: () => boolean;
  /** The name of the tab the reader is on, as the host's strip resolves it. */
  activeTab: () => string;
  save: () => Promise<void>;
  reload: () => Promise<void>;
  router: Router;
  /** Resolves when sources that register after mount (Page Scripts) are in. */
  sourcesReady?: () => Promise<void>;
}

export interface RecordPageController {
  page: RecordPageApi;
  quickActions: Surface<QuickAction>;
  headerActions: Surface<HeaderAction>;
  tabs: Surface<TabItem>;
  panelSections: Surface<PanelSectionItem>;
  /** The replay: clears every surface, then runs every source's `refresh` in run order. */
  refresh: () => Promise<void>;
  fireEvent: (event: string) => Promise<void>;
  /** True once the first replay has run — before it, surfaces are only built-ins. */
  ready: Ref<boolean>;
}

export function createRecordPage(host: RecordPageHost): RecordPageController {
  const quickActions = new Surface<QuickAction>();
  const headerActions = new Surface<HeaderAction>();
  const tabs = new Surface<TabItem>();
  const panelSections = new Surface<PanelSectionItem>();
  const surfaces = [quickActions, headerActions, tabs, panelSections];

  Object.defineProperty(tabs, "active", { get: () => host.activeTab() });

  const page: RecordPageApi = {
    doctype: host.doctype,
    docname: host.docname,
    get doc() {
      return host.doc.value;
    },
    get meta() {
      return host.meta.value;
    },
    get perms() {
      return host.perms();
    },
    get isDirty() {
      return host.isDirty();
    },
    quickActions,
    headerActions,
    tabs: tabs as unknown as TabsApi,
    panelSections,
    save: () => host.save(),
    reload: () => host.reload(),
    refresh: () => refresh(),
    toast: {
      success: (message) => toast.success(message),
      error: (message) => toast.error(message),
    },
    call: (method, params) => call(method, params),
    router: host.router,
  };

  const ready = ref(false);
  let vocabularyChecked = false;

  async function refresh() {
    await host.sourcesReady?.();
    warnUnknownHandlers();
    for (const surface of surfaces) surface.reset();
    await fireEvent("refresh");
    ready.value = true;
  }

  async function fireEvent(event: string) {
    for (const { source, handlers } of registrationsFor(host.doctype)) {
      const handler = handlers[event];
      if (!handler) continue;
      await withRunningSource(source, async () => {
        try {
          await handler(page);
        } catch (error) {
          if (event === "before_save") throw error;
          console.error(
            `[record-page] ${source}.${event} on ${host.doctype} threw`,
            error,
          );
        }
      });
    }
  }

  // Meta can lag the first paint, so the check waits for a replay that has fields.
  function warnUnknownHandlers() {
    if (vocabularyChecked || !import.meta.env.DEV) return;
    const fields = host.meta.value?.fields;
    if (!fields) return;
    vocabularyChecked = true;
    const known = knownHandlerKeys(fields);
    for (const { source, handlers } of registrationsFor(host.doctype))
      for (const key of Object.keys(handlers))
        if (!known.has(key))
          console.warn(
            `[record-page] ${source}.${key} on ${host.doctype} is neither an event nor a fieldname — it will never fire`,
          );
  }

  return {
    page,
    quickActions,
    headerActions,
    tabs,
    panelSections,
    refresh,
    fireEvent,
    ready,
  };
}

function knownHandlerKeys(fields: { fieldname: string; fieldtype: string }[]) {
  const known = new Set(RECORD_PAGE_EVENTS);
  for (const field of fields) {
    known.add(field.fieldname);
    if (field.fieldtype?.startsWith("Table")) {
      known.add(`${field.fieldname}_add`);
      known.add(`${field.fieldname}_remove`);
    }
  }
  return known;
}
