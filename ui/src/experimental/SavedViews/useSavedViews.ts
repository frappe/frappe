import { computed, ref, toValue, watch } from "vue";
import type { ComputedRef, MaybeRefOrGetter } from "vue";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import { getFilterableFields } from "../../components/Filter/getFilterableFields";
import { toSnapshot, toWire } from "./savedView";
import { savedViewApi } from "./savedViewApi";
import type { ViewName } from "./savedViewApi";
import type { ListViewSnapshot, UseListView } from "../../components/ListView/useListView";
import type { SavedView } from "./types";

export interface UseSavedViewsOptions {
  app: MaybeRefOrGetter<string>;
  activeView?: MaybeRefOrGetter<SavedView | null | undefined>;
  onChange?: () => unknown;
}

export interface UseSavedViews {
  activeSnapshot: ComputedRef<Partial<ListViewSnapshot>>;
  applyTo: (view: UseListView) => () => void;
  createView: (options: {
    label: string;
    icon?: string;
    shared?: boolean;
    section?: string | null;
  }) => Promise<ViewName>;
  updateView: (
    view: ViewName,
    changes: { label?: string; icon?: string }
  ) => Promise<void>;
  duplicateView: (view: ViewName) => Promise<ViewName>;
  saveView: (
    view: ViewName,
    snapshot: Partial<ListViewSnapshot>
  ) => Promise<ViewName>;
  saveAsNew: (
    snapshot: Partial<ListViewSnapshot>,
    options: { label: string; icon?: string; shared?: boolean }
  ) => Promise<ViewName>;
  loadLanding: () => Promise<void>;
  landingLoaded: ComputedRef<boolean>;
  landingSnapshot: ComputedRef<Partial<ListViewSnapshot>>;
  saveLanding: (snapshot: Partial<ListViewSnapshot>) => Promise<ViewName>;
  setAsDefault: (view: ViewName) => Promise<ViewName>;
  deleteView: (view: ViewName) => Promise<ViewName>;
  moveView: (view: ViewName, shared: boolean) => Promise<ViewName>;
}

export function useSavedViews(
  doctype: MaybeRefOrGetter<string>,
  options: UseSavedViewsOptions
): UseSavedViews {
  const { meta } = useDoctypeMeta(doctype);
  const scope = () => ({ doctype: toValue(doctype), app: toValue(options.app) });

  const filterFields = computed(() =>
    meta.value?.fields
      ? getFilterableFields(meta.value.fields, toValue(doctype))
      : []
  );
  const rawFields = computed(() => meta.value?.fields ?? []);

  const activeView = computed(() => toValue(options.activeView) ?? undefined);
  const activeSnapshot = computed(() =>
    activeView.value ? toSnapshot(activeView.value, filterFields.value) : {}
  );

  const applyTo = (view: UseListView) =>
    watch(activeSnapshot, (snapshot) => view.restore(snapshot), {
      immediate: true,
    });

  const landingView = ref<SavedView | null>(null);
  const landingFetched = ref(false);
  watch(
    () => toValue(doctype),
    () => {
      landingView.value = null;
      landingFetched.value = false;
    }
  );
  const landingSnapshot = computed(() =>
    landingView.value ? toSnapshot(landingView.value, filterFields.value) : {}
  );

  const afterMutation = async <T>(result: T): Promise<T> => {
    await options.onChange?.();
    return result;
  };

  return {
    activeSnapshot,
    applyTo,
    createView: (values) =>
      savedViewApi.create({ ...scope(), ...values }).then(afterMutation),
    updateView: (view, changes) =>
      savedViewApi.update(view, changes).then(() => afterMutation(undefined)),
    duplicateView: (view) =>
      savedViewApi.duplicate(view, toValue(options.app)).then(afterMutation),
    saveView: (view, snapshot) =>
      savedViewApi
        .saveState(view, toWire(snapshot, rawFields.value))
        .then(afterMutation),
    saveAsNew: (snapshot, values) =>
      savedViewApi
        .create({
          ...scope(),
          ...values,
          state: toWire(snapshot, rawFields.value),
        })
        .then(afterMutation),
    loadLanding: () =>
      savedViewApi.getLanding(toValue(doctype)).then((view) => {
        landingView.value = view;
        landingFetched.value = true;
      }),
    landingLoaded: computed(() => landingFetched.value),
    landingSnapshot,
    saveLanding: (snapshot) =>
      savedViewApi.saveLanding(
        toValue(doctype),
        toWire(snapshot, rawFields.value)
      ),
    setAsDefault: (view) => savedViewApi.setAsDefault(view).then(afterMutation),
    deleteView: (view) => savedViewApi.deleteView(view).then(afterMutation),
    moveView: (view, shared) =>
      savedViewApi
        .move(view, shared, toValue(options.app))
        .then(afterMutation),
  };
}
