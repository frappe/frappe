import { computed, ref, toValue } from "vue";
import type { ComputedRef, MaybeRefOrGetter, Ref } from "vue";
import { createResource } from "frappe-ui";
import { findView } from "./sections";
import { navigationApi } from "./navigationApi";
import { forwardState, memoizedState } from "../../utils/sharedState";
import { DEFAULT_APP } from "./types";
import type {
  ArrangedRow,
  NavigationItemNaming,
  NavigationItemValues,
  NavigationScope,
  NavigationSection,
  PoolView,
  SidebarResponse,
  ViewCounts,
} from "./types";
import type { SavedView } from "../SavedViews/types";
import type { ViewName } from "../SavedViews/savedViewApi";

export interface UseNavigationOptions {
  app?: MaybeRefOrGetter<string | undefined>;
}

export interface UseNavigation {
  app: ComputedRef<string>;
  sections: ComputedRef<NavigationSection[]>;
  visibleSections: ComputedRef<NavigationSection[]>;
  sharedSections: ComputedRef<NavigationSection[]>;
  loadShared: () => Promise<unknown>;
  loading: ComputedRef<boolean>;
  fetched: ComputedRef<boolean>;
  error: ComputedRef<unknown>;
  canManageShared: ComputedRef<boolean>;
  activeView: ComputedRef<SavedView | undefined>;
  defaultView: ComputedRef<string | number | null>;
  defaultViewIsStored: ComputedRef<boolean>;
  reload: () => Promise<unknown>;
  pool: ComputedRef<PoolView[]>;
  loadPool: () => Promise<PoolView[]>;
  counts: ComputedRef<ViewCounts>;
  loadCounts: (refresh?: boolean) => Promise<ViewCounts>;
  addItem: (
    section: string,
    item: NavigationItemValues,
    forEveryone?: boolean
  ) => Promise<string>;
  getItem: (section: string, item: string) => Promise<NavigationItemValues>;
  updateItem: (
    section: string,
    item: string,
    naming: NavigationItemNaming,
    forEveryone?: boolean,
    values?: NavigationItemValues
  ) => Promise<void>;
  removeItem: (section: string, item: string) => Promise<void>;
  addToSidebar: (view: ViewName) => Promise<ViewName>;
  removeFromSidebar: (view: ViewName) => Promise<ViewName>;
  arrangeItems: (
    section: string,
    items: ArrangedRow[],
    forEveryone?: boolean
  ) => Promise<void>;
  moveItemToSection: (
    source: string,
    item: string,
    section: string,
    index?: number,
    forEveryone?: boolean
  ) => Promise<string>;
  moveViewToSection: (
    view: ViewName,
    section: string,
    index?: number
  ) => Promise<ViewName>;
  createSection: (label: string, shared?: boolean) => Promise<string>;
  renameSection: (section: string, label: string) => Promise<void>;
  hideSection: (section: string, hidden: boolean) => Promise<void>;
  deleteSection: (section: string) => Promise<void>;
  arrangeSections: (sections: string[], forEveryone?: boolean) => Promise<void>;
}

/** The shared half of the API: everything but the caller's own `activeView`. */
type NavigationScopeState = Omit<
  UseNavigation,
  "activeView" | "pool" | "counts"
> & {
  pool: Ref<PoolView[]>;
  counts: Ref<ViewCounts>;
};

const scopes = memoizedState(scopeKey, buildScopeState);

export function useNavigation(
  doctype: MaybeRefOrGetter<string> = "",
  activeId?: MaybeRefOrGetter<string | number | null | undefined>,
  options: UseNavigationOptions = {}
): UseNavigation {
  // Warm the current scope at call time; the handle tracks it from there.
  const current = () => scopes.get(scopeOf(toValue(doctype), options));
  current();

  return {
    ...forwardState(current),
    activeView: computed(() =>
      findView(current().sections.value, toValue(activeId))
    ),
  };
}

/** The shared state itself, for a host that has to reach it outside a setup. */
export function navigationScope(
  doctype: string,
  options: UseNavigationOptions = {}
): NavigationScopeState {
  return scopes.get(scopeOf(doctype, options));
}

/** Drops every scope, so one test's navigation state cannot reach the next. */
export function resetNavigationScopes(): void {
  scopes.reset();
}

function scopeKey(scope: NavigationScope) {
  return `${scope.app}:${scope.doctype}`;
}

function scopeOf(
  doctype: string,
  options: UseNavigationOptions
): NavigationScope {
  return { app: toValue(options.app) ?? DEFAULT_APP, doctype };
}

/** Every consumer of an app and doctype shares one state, so a mutation in one reaches all. */
function buildScopeState(scope: NavigationScope): NavigationScopeState {
  const doctype = scope.doctype;
  const sidebar = createResource({
    url: "frappe.desk.doctype.navigation_section.navigation_section.get_sidebar",
    params: { reference_doctype: doctype, app: scope.app },
    cache: ["navigation-sidebar", scope.app, doctype],
  });

  const shared = createResource({
    url: "frappe.desk.doctype.navigation_section.navigation_section.get_sidebar",
    params: { reference_doctype: doctype, app: scope.app, for_everyone: true },
  });

  const response = computed(() => sidebar.data as SidebarResponse | null);
  const sections = computed<NavigationSection[]>(
    () => response.value?.sections ?? []
  );
  const visibleSections = computed<NavigationSection[]>(() =>
    sections.value
      .filter((section) => !section.hidden)
      .map((section) => ({
        ...section,
        items: section.items.filter((item) => !item.hidden),
      }))
  );

  const sharedSections = computed<NavigationSection[]>(
    () => (shared.data as SidebarResponse | null)?.sections ?? []
  );
  const loadShared = () => shared.fetch();

  const pool = ref<PoolView[]>([]);
  const loadPool = async () => {
    pool.value = await navigationApi.getPool(scope);
    return pool.value;
  };

  const counts = ref<ViewCounts>({});
  const loadCounts = async (refresh = false) => {
    counts.value = await navigationApi.getCounts(scope, refresh);
    return counts.value;
  };

  const reload = () =>
    Promise.all([
      sidebar.fetch(),
      pool.value.length ? loadPool() : null,
      shared.data ? loadShared() : null,
    ]);
  const afterMutation = async <T>(result: T): Promise<T> => {
    await reload();
    return result;
  };

  // A cached resource with `auto` refetches once per consumer; the scope owns the one fetch.
  if (!sidebar.fetched && !sidebar.loading) sidebar.fetch();

  return {
    app: computed(() => scope.app),
    sections,
    visibleSections,
    sharedSections,
    loadShared,
    loading: computed(() => Boolean(sidebar.loading)),
    fetched: computed(() => Boolean(sidebar.fetched)),
    error: computed(() => sidebar.error),
    canManageShared: computed(() => Boolean(response.value?.can_manage_shared)),
    defaultView: computed(() => response.value?.default_view ?? null),
    defaultViewIsStored: computed(() =>
      Boolean(response.value?.default_view_is_stored)
    ),
    reload,
    pool,
    loadPool,
    counts,
    loadCounts,
    addItem: (section, item, forEveryone) =>
      navigationApi.addItem(section, item, forEveryone).then(afterMutation),
    getItem: (section, item) => navigationApi.getItem(section, item),
    updateItem: (section, item, naming, forEveryone, values) =>
      navigationApi
        .updateItem(section, item, naming, forEveryone, values)
        .then(() => afterMutation(undefined)),
    removeItem: (section, item) =>
      navigationApi
        .removeItem(section, item)
        .then(() => afterMutation(undefined)),
    addToSidebar: (view) =>
      navigationApi.addToSidebar(view, scope.app).then(afterMutation),
    removeFromSidebar: (view) =>
      navigationApi.removeFromSidebar(view).then(afterMutation),
    arrangeItems: (section, items, forEveryone) =>
      navigationApi
        .arrangeItems(section, items, forEveryone)
        .then(() => afterMutation(undefined)),
    moveItemToSection: (source, item, section, index, forEveryone) =>
      navigationApi
        .moveItemToSection(source, item, section, index, forEveryone)
        .then(afterMutation),
    moveViewToSection: (view, section, index) =>
      navigationApi.moveToSection(view, section, index).then(afterMutation),
    createSection: (label, shared) =>
      navigationApi.createSection(scope, label, shared).then(afterMutation),
    renameSection: (section, label) =>
      navigationApi
        .renameSection(section, label)
        .then(() => afterMutation(undefined)),
    hideSection: (section, hidden) =>
      navigationApi
        .hideSection(section, hidden)
        .then(() => afterMutation(undefined)),
    deleteSection: (section) =>
      navigationApi.deleteSection(section).then(() => afterMutation(undefined)),
    arrangeSections: (sections, forEveryone) =>
      navigationApi
        .arrangeSections(scope, sections, forEveryone)
        .then(() => afterMutation(undefined)),
  };
}
