<!--
  QuickFilterCustomize — the edit-mode face of the QuickFilter strip. It surfaces
  the chosen quick-filter *fields* (not their values): a draggable chip per field
  with a remove affordance, plus an "Add Filter" picker over every labelled field
  not yet shown. It never touches the shared `Filter[]` — removing or reordering a
  chip only changes which inputs `QuickFilterInputs` renders (and in what order);
  any existing condition survives and still shows in the Filter popover.

  Mirrors the sibling controls' edit affordances: the "Add Filter" trigger reuses
  the Filter control's `#trigger`-slot ghost Button (gray-5, `+` icon, no chevron),
  and drag-to-reorder reuses SortBy's `vuedraggable` + grip-handle pattern. All
  mutations re-emit the full surfaced list via `update:fields`, leaving the
  promote-default-on-customize decision to the parent.
-->
<template>
	<!-- `Draggable` IS the wrapping flex row (not a `display:contents` pass-through):
	     Sortable measures the container's box to decide drop positions, so a boxless
	     wrapper mis-places drops across wrapped rows. The "Add Filter" picker rides in
	     the `#footer` slot — inside the same row, after the chips — and `draggable`
	     scopes sorting to `.quick-filter-chip` so the footer button never drags. -->
	<Draggable
		class="flex flex-wrap items-center gap-2"
		:modelValue="fields"
		:item-key="(f) => f.fieldname"
		handle=".quick-filter-drag-handle"
		draggable=".quick-filter-chip"
		tag="div"
		@update:modelValue="reorder"
	>
		<template #item="{ element: field }">
			<Button class="quick-filter-chip group whitespace-nowrap" :label="field.label">
				<template #prefix>
					<span
						class="quick-filter-drag-handle lucide-grip-vertical size-3.5 cursor-grab text-ink-gray-5"
						aria-hidden="true"
					/>
				</template>
				<template #suffix>
					<span
						class="lucide-x size-3.5 cursor-pointer"
						aria-hidden="true"
						@click.stop="removeField(field)"
					/>
				</template>
			</Button>
		</template>

		<!-- Footer (non-draggable): the "Add Filter" picker, then a Done button pushed
		     to the far end. Done lives here — not as the host's customize toggle — so
		     exiting customize mode is part of this surface; the host hides its control
		     cluster while customizing. Field edits already emit live (and the host
		     autosaves the snapshot), so Done only leaves edit mode — it is not a
		     persistence affordance, hence "Done", not "Save" (`done`). -->
		<template #footer>
			<!-- Same "Add Filter" affordance as the Filter control: a `#trigger`-slot
			     ghost Button opening the field picker. The label is static, so no
			     per-add `:key` remount or placeholder/chevron CSS hacks are needed. -->
			<Combobox
				:options="addableFields"
				:modelValue="null"
				@update:selectedOption="addField"
			>
				<template #trigger>
					<Button
						class="!text-ink-gray-5"
						variant="ghost"
						label="Add Filter"
						iconLeft="lucide-plus"
					/>
				</template>
			</Combobox>
			<Button class="ml-auto" variant="solid" label="Done" @click="emit('done')" />
		</template>
	</Draggable>
</template>

<script setup lang="ts">
import { Button, Combobox } from "frappe-ui";
// @ts-ignore — vuedraggable ships no bundled types
import Draggable from "vuedraggable";
import type { FilterField } from "../Filter/types";

const props = defineProps<{
	/** The fields currently surfaced as quick inputs, in display order. */
	fields: FilterField[];
	/** Every labelled field not yet surfaced — the Add picker's options. */
	addableFields: FilterField[];
}>();

// `update:fields` re-emits the full surfaced list on every mutation (the parent
// owns whether that promotes the Meta-derived default into a persisted custom set);
// `done` asks the parent to leave customize mode (edits are already live, so this
// carries nothing — it is not a save).
const emit = defineEmits<{ "update:fields": [FilterField[]]; done: [] }>();

// Combobox's `update:selectedOption` hands back the chosen option (or null); its
// `value` is the fieldname. Resolve it against the addable set (the only fields
// the picker offers).
function addField(option: unknown) {
	if (!option) return;
	const fieldname =
		typeof option === "string" ? option : (option as { value?: string }).value ?? null;
	const field = props.addableFields.find((f) => f.fieldname === fieldname);
	if (!field || props.fields.some((f) => f.fieldname === field.fieldname)) return;
	emit("update:fields", [...props.fields, field]);
}

function removeField(field: FilterField) {
	emit(
		"update:fields",
		props.fields.filter((f) => f.fieldname !== field.fieldname)
	);
}

function reorder(next: FilterField[]) {
	emit("update:fields", next);
}
</script>
