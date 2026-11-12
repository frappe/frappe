// Stand-ins for the list page's state and the List renderer's, for tests of the page's controls:
// `vi.mock("@/list/useListPage", ...)` and `vi.mock("@/list/useListView", ...)` hand these out, and
// `fake.state` holds the refs a test moves.
import { computed, ref, type Ref } from "vue";
import { vi } from "vitest";
import type { SavedView } from "@/list/savedView";
import type { ListPage } from "@/list/useListPage";
import type { ListView } from "@/list/useListView";
import type { View } from "@/list/view";

const PLAIN: SavedView = {
  key: "list",
  label: "",
  type: "List",
  layer: null,
  applies: true,
};

export const fake = {
  reload: vi.fn(),
  reloadMeta: vi.fn(),
  createValues: {} as Record<string, unknown>,
  /** Whether the page has read meta, the stored settings and the URL. */
  seeded: true,
  selectedAtMount: [] as string[],
  state: {} as Record<string, Ref<unknown>>,
};

export function resetFake() {
  fake.reload.mockReset();
  fake.reloadMeta.mockReset();
  fake.createValues = {};
  fake.seeded = true;
  fake.selectedAtMount = [];
}

export function useListPage(
  doctype: string,
  opened: SavedView = PLAIN,
): ListPage {
  const metaError = ref<unknown>(null);
  const view: View = {
    doctype,
    key: opened.key,
    type: opened.type,
    layer: opened.layer,
    settings: computed(() => ({})),
    filters: ref([]),
    sort: ref([]),
    seeded: computed(() => seeded.value),
    modified: computed(() => false),
    update: vi.fn(),
    customized: () => false,
    reset: async () => {},
  };
  const seeded = ref(fake.seeded);
  const customizing = ref(false);
  fake.state = {
    filters: view.filters,
    sort: view.sort,
    seeded,
    customizing,
    metaError,
  };
  return {
    view,
    quickFilterFields: ref(undefined),
    customizing,
    metaError: computed(() => metaError.value),
    reloadMeta: fake.reloadMeta,
    saveForSite: async () => {},
    resetForSite: async () => {},
    createValues: computed(() => fake.createValues),
  };
}

export function useListView(): ListView {
  const state = fake.state;
  state.rows = ref([]);
  state.error = ref(null);
  state.selection = ref([...fake.selectedAtMount]);
  return {
    columns: ref([]),
    shownColumns: computed(() => []),
    selection: state.selection,
    pageSize: ref(20),
    rowsKey: () => "",
    rows: state.rows,
    loading: ref(false),
    error: state.error,
    rowCount: ref(0),
    totalCount: ref(0),
    totalCapped: ref(false),
    totalUnknown: ref(false),
    hasCounts: ref(true),
    hasNextPage: ref(false),
    rowActions: computed(() => []),
    fieldOf: () => undefined,
    statusThemeOf: () => null,
    columnsCustomized: computed(() => false),
    resetColumns: async () => {},
    resizeColumn: () => {},
    resetColumnWidth: () => {},
    rowLink: () => ({}),
    reload: fake.reload,
    deleteSelection: async () => ({ deleted: [], failed: [] }),
  } as unknown as ListView;
}

/** Loads the List renderer's code, so the page draws it at once. */
export async function installListRenderer() {
  await import("../ListView.vue");
}
