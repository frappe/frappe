import { computed, ref, toValue } from "vue";
import type { ComputedRef, MaybeRefOrGetter, Ref } from "vue";
import { getMeta } from "../api";
import type { RawMetaField } from "../components/FormLayout/types";
import { landFresh, memoizedState } from "../utils/sharedState";

/** A DocPerm row as the meta read returns it; booleans arrive as `0 | 1`. */
export interface DocPermRow {
  role: string;
  permlevel?: number;
  read?: 0 | 1;
  write?: 0 | 1;
  [right: string]: unknown;
}

export interface DoctypeMeta {
  name: string;
  title_field?: string;
  fields?: RawMetaField[];
  permissions?: DocPermRow[];
}

export interface UseDoctypeMeta {
  /** The requested doctype's meta; `null` until it loads (or if absent). */
  meta: ComputedRef<DoctypeMeta | null>;
  /** The doctype's meta and its child tables' (`include=children`), keyed by name. */
  metas: ComputedRef<Record<string, DoctypeMeta>>;
  /** True while nothing is there to show; a stale meta shows while its fresh one is read. */
  loading: ComputedRef<boolean>;
  /** True while a stale meta shows and its fresh one is read. */
  refreshing: ComputedRef<boolean>;
  error: ComputedRef<unknown>;
  /** Re-fetch the meta. */
  reload: () => void;
  /** Resolves once a stale meta's fresh read has arrived, shown or held; at once when none is out. */
  refreshed: () => Promise<void>;
}

interface DoctypeMetaEntry {
  metas: Ref<Record<string, DoctypeMeta>>;
  error: Ref<unknown>;
  loading: ComputedRef<boolean>;
  refreshing: ComputedRef<boolean>;
  reload: () => void;
  refreshed: Promise<void>;
}

/** Memoised per doctype: fetched once, and again after the DocType changes; shared by every caller. */
const entries = memoizedState((doctype: string) => doctype, buildEntry);

/** Fetch a doctype's meta with its child tables; building the layout is `buildLayoutFromMeta`'s job. */
export function useDoctypeMeta(
  doctype: MaybeRefOrGetter<string>
): UseDoctypeMeta {
  // Built at call time and held until the doctype moves, so a later stale mark cannot swap it.
  let held = { doctype: toValue(doctype), entry: entries.get(toValue(doctype)) };
  const entry = computed(() => {
    const name = toValue(doctype);
    if (name !== held.doctype) held = { doctype: name, entry: entries.get(name) };
    return held.entry;
  });

  return {
    meta: computed(() => entry.value.metas.value[toValue(doctype)] ?? null),
    metas: computed(() => entry.value.metas.value),
    loading: computed(() => entry.value.loading.value),
    refreshing: computed(() => entry.value.refreshing.value),
    error: computed(() => entry.value.error.value),
    reload: () => entry.value.reload(),
    refreshed: () => entry.value.refreshed,
  };
}

/** Marks the doctype's meta, every meta holding it as a child table, and every fetch in flight stale. */
export function markDoctypeMetaStale(doctype: string): void {
  // A fetch in flight may answer from before the change, and its child tables are not known yet.
  entries.stale(
    (key, entry) =>
      key === doctype ||
      doctype in entry.metas.value ||
      entry.loading.value ||
      entry.refreshing.value
  );
}

/** Drops every memoised meta, so one test's fetch cannot reach the next. */
export function resetDoctypeMeta(): void {
  entries.reset();
}

function buildEntry(doctype: string, stale?: DoctypeMetaEntry): DoctypeMetaEntry {
  const metas = ref<Record<string, DoctypeMeta>>(stale?.metas.value ?? {});
  const error = ref<unknown>(null);
  const loading = ref(false);
  const refreshing = ref(Object.keys(metas.value).length > 0);
  let arrive = () => {};
  const refreshed = refreshing.value
    ? new Promise<void>((resolve) => (arrive = resolve))
    : Promise.resolve();
  // The slower of two reloads must not overwrite the newer answer.
  let turn = 0;

  async function reload() {
    const mine = ++turn;
    loading.value = !refreshing.value;
    try {
      const envelope = await getMeta<DoctypeMeta | null>(doctype, { include: ["children"] });
      if (mine !== turn) return;
      show(() => {
        metas.value = keyByName(doctype, envelope.data, envelope.children as DoctypeMeta[] | undefined);
        error.value = envelope.data ? null : new Error(`Doctype meta not found for "${doctype}".`);
      });
    } catch (caught) {
      if (mine !== turn) return;
      // A failed refresh keeps the stale meta on show, and the next caller reads again.
      if (refreshing.value) {
        refreshing.value = false;
        entries.stale((_key, one) => one === entry);
      } else {
        metas.value = {};
        error.value = caught;
      }
    } finally {
      if (mine === turn) {
        loading.value = false;
        arrive();
      }
    }
  }

  function show(commit: () => void) {
    if (!refreshing.value) return commit();
    landFresh(() => {
      commit();
      refreshing.value = false;
    });
  }

  const entry: DoctypeMetaEntry = {
    metas,
    error,
    loading: computed(() => loading.value),
    refreshing: computed(() => refreshing.value),
    reload,
    refreshed,
  };
  reload();
  return entry;
}

function keyByName(
  doctype: string,
  meta: DoctypeMeta | null,
  children: DoctypeMeta[] | undefined
): Record<string, DoctypeMeta> {
  const map: Record<string, DoctypeMeta> = {};
  if (meta) map[doctype] = meta;
  for (const child of children ?? []) map[child.name] = child;
  return map;
}
