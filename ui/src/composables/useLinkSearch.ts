// The options behind a link picker: the server's matches for the typed text; the last answer wins.
import { computed, ref, shallowRef, toValue } from "vue";
import type { ComputedRef, MaybeRefOrGetter } from "vue";
import { searchDocuments } from "../api";
import { toLinkOption } from "../components/Link/linkOption";

export interface LinkSearchOption {
  label: string;
  value: string;
  description?: string;
}

export interface UseLinkSearch {
  /** `null` until the first answer, so a host can tell "nothing found" from "not asked yet". */
  data: ComputedRef<LinkSearchOption[] | null>;
  loading: ComputedRef<boolean>;
  error: ComputedRef<unknown>;
  search: (txt?: string) => Promise<void>;
}

export function useLinkSearch(
  doctype: MaybeRefOrGetter<string | undefined>,
  filters: MaybeRefOrGetter<unknown> = {},
  limit?: number
): UseLinkSearch {
  const data = shallowRef<LinkSearchOption[] | null>(null);
  const loading = ref(false);
  const error = ref<unknown>(null);
  let generation = 0;

  async function search(txt = ""): Promise<void> {
    const target = toValue(doctype);
    if (!target) return;
    const mine = ++generation;
    loading.value = true;
    try {
      const { data: found } = await searchDocuments(target, {
        txt,
        filters: toValue(filters),
        limit,
      });
      if (mine !== generation) return;
      data.value = found.map(toLinkOption);
      error.value = null;
    } catch (failure) {
      if (mine === generation) error.value = failure;
    } finally {
      if (mine === generation) loading.value = false;
    }
  }

  return {
    data: computed(() => data.value),
    loading: computed(() => loading.value),
    error: computed(() => error.value),
    search,
  };
}
