<!--
  QuickFilter — a controlled, meta-driven list-view control that projects over the
  SAME `Filter[]` list the Filter control binds (ADR-0005). It owns no data
  resource; its two faces are split into focused children and this component just
  derives the shared field state and dispatches between them:

    • normal mode  → `QuickFilterInputs`    (one value input per surfaced field)
    • customize    → `QuickFilterCustomize` (draggable field chips + "Add Filter")

  Three `v-model`s: `filters` (the shared Filter[] — the SoT `useListView` hands
  both controls), `fields` (the surfaced inputs, optional; defaults to the
  doctype's `in_standard_filter` fields from Meta via `getQuickFilterFields`, and a
  host may bind it to persist the user's customized + reordered set), and
  `customizing` (the edit-mode toggle, owned by the host so a trigger beside Sort
  can drive it).

  Field edits emit live through `v-model:fields`, so the host's snapshot watcher
  already persists customization — there is no separate save. `done` is emitted only
  when the user clicks Done to leave customize mode; it carries the final surfaced set
  purely so a host that opted out of binding `v-model:fields` can still read it.
-->
<template>
	<QuickFilterCustomize
		v-if="customizing"
		:fields="surfaced"
		:addable-fields="addableFields"
		@update:fields="onUpdateFields"
		@done="onDone"
	/>
	<QuickFilterInputs v-else :fields="surfaced" v-model:filters="filters" />
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import { getFilterableFields } from "../Filter/getFilterableFields";
import { getQuickFilterFields } from "./getQuickFilterFields";
import QuickFilterInputs from "./QuickFilterInputs.vue";
import QuickFilterCustomize from "./QuickFilterCustomize.vue";
import type { Filter, FilterField } from "../Filter/types";

const props = defineProps<{ doctype: string }>();

// `done` fires when the user leaves customize mode (the Done button). Edits already
// flow live via `update:fields`, so this is NOT a save — it carries the final
// surfaced set only for a host that opted out of binding `v-model:fields`.
const emit = defineEmits<{ done: [FilterField[]] }>();

// Three controlled models. `fields` is left undefined when the host doesn't bind
// it, so the Meta-derived default is used locally; mutating in customize mode
// promotes that default into the model.
const filters = defineModel<Filter[]>("filters", { default: () => [] });
const fields = defineModel<FilterField[] | undefined>("fields", { default: undefined });
const customizing = defineModel<boolean>("customizing", { default: false });

const { meta } = useDoctypeMeta(props.doctype);

// Default surfaced fields from Meta until the host/user customizes (`fields`
// bound). Mutating in customize mode promotes the default into the model.
const defaultFields = computed<FilterField[]>(() =>
	getQuickFilterFields(meta.value?.fields ?? [], props.doctype)
);
const surfaced = computed<FilterField[]>(() => fields.value ?? defaultFields.value);

// Every labelled field offered by the customize/add picker (drawn from the Filter
// module's `getFilterableFields`, so `name` and any labelled field is addable),
// minus the already-surfaced ones.
const allFields = computed<FilterField[]>(() =>
	getFilterableFields(meta.value?.fields ?? [], props.doctype)
);
const addableFields = computed<FilterField[]>(() => {
	const shown = new Set(surfaced.value.map((f) => f.fieldname));
	return allFields.value.filter((f) => !shown.has(f.fieldname));
});

// Customize edits (add / remove / reorder) re-emit the whole surfaced list; storing
// it through the model promotes the Meta-derived default into a persisted set.
function onUpdateFields(next: FilterField[]) {
	fields.value = next;
}

// Leave customize mode. Emits `surfaced` (the effective list) rather than the raw
// `fields` model, so a host that never bound `v-model:fields` still receives the
// Meta-derived default the user kept. Not a save — persistence already happened live.
function onDone() {
	customizing.value = false;
	emit("done", surfaced.value);
}
</script>
