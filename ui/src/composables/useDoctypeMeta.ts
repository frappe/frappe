import { computed, ref, toValue } from "vue";
import type { ComputedRef, MaybeRefOrGetter, Ref } from "vue";
import { getMeta } from "../api";
import type { RawMetaField } from "../components/FormLayout/types";
import { memoizedState } from "../utils/sharedState";

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
  loading: ComputedRef<boolean>;
  error: ComputedRef<unknown>;
  /** Re-fetch the meta. */
  reload: () => void;
}

interface DoctypeMetaEntry {
  metas: Ref<Record<string, DoctypeMeta>>;
  error: Ref<unknown>;
  loading: ComputedRef<boolean>;
  reload: () => void;
}

/** Memoised per doctype: fetched once per session, shared by every caller. */
const entries = memoizedState((doctype: string) => doctype, buildEntry);

/** Fetch a doctype's meta with its child tables; building the layout is `buildLayoutFromMeta`'s job. */
export function useDoctypeMeta(
  doctype: MaybeRefOrGetter<string>
): UseDoctypeMeta {
  // Warm the current entry at call time; the computed tracks it from there.
  const current = () => entries.get(toValue(doctype));
  current();
  const entry = computed(current);

  return {
    meta: computed(() => entry.value.metas.value[toValue(doctype)] ?? null),
    metas: computed(() => entry.value.metas.value),
    loading: computed(() => entry.value.loading.value),
    error: computed(() => entry.value.error.value),
    reload: () => entry.value.reload(),
  };
}

/** Drops every memoised meta, so one test's fetch cannot reach the next. */
export function resetDoctypeMeta(): void {
  entries.reset();
}

function buildEntry(doctype: string): DoctypeMetaEntry {
  const metas = ref<Record<string, DoctypeMeta>>({});
  const error = ref<unknown>(null);
  const loading = ref(false);
  // The slower of two reloads must not overwrite the newer answer.
  let turn = 0;

  async function reload() {
    const mine = ++turn;
    loading.value = true;
    try {
      const envelope = await getMeta<DoctypeMeta | null>(doctype, { include: ["children"] });
      if (mine !== turn) return;
      metas.value = keyByName(doctype, envelope.data, envelope.children as DoctypeMeta[] | undefined);
      error.value = envelope.data ? null : new Error(`Doctype meta not found for "${doctype}".`);
    } catch (caught) {
      if (mine !== turn) return;
      metas.value = {};
      error.value = caught;
    } finally {
      if (mine === turn) loading.value = false;
    }
  }

  reload();

  return { metas, error, loading: computed(() => loading.value), reload };
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
