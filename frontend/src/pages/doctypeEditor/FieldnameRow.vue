<!-- The panel's Fieldname row: a new field's follows its label until the save; a saved one renames
     on a custom DocType and is locked on a standard one. -->
<template>
	<PanelRow :label="__('Fieldname')" :box="false" :lock="lane">
		<template v-if="mode === 'renamable'">
			<div
				class="min-h-7 rounded-4 focus-within:bg-surface-gray-2 focus-within:ring-1 focus-within:ring-inset focus-within:ring-outline-gray-3 hover:bg-surface-gray-2"
			>
				<TextInput
					variant="ghost"
					class="[&_input]:font-mono [&_input]:text-sm"
					:model-value="field.fieldname"
					data-panel-fieldname
					@change="rename"
				/>
			</div>
			<p class="px-2 pb-1 pt-0.5 text-p-sm text-ink-gray-5" data-panel-fieldname-note>
				<template v-if="was">
					{{ __("Was") }} <code class="font-mono text-ink-gray-7">{{ was }}</code
					>.
				</template>
				{{ moves }}
				{{
					__("Reports, scripts and filters that name {0} must change.", [
						was || field.fieldname,
					])
				}}
			</p>
		</template>
		<div v-else class="flex min-h-7 flex-col justify-center px-2">
			<div class="flex h-7 items-center gap-1.5">
				<span
					class="min-w-0 truncate font-mono text-sm text-ink-gray-7"
					data-panel-fieldname
				>
					{{ field.fieldname }}
				</span>
				<span
					v-if="mode === 'locked' && !lane"
					class="lucide-lock size-3.5 shrink-0 text-ink-gray-4"
					aria-hidden="true"
				/>
			</div>
			<p v-if="!lane" class="pb-1 text-p-sm text-ink-gray-5" data-panel-fieldname-note>
				{{
					mode === "locked"
						? lockedNote
						: canvas.state.pending
						? __("Follows the label until the first save.")
						: __("Follows the label until you save.")
				}}
			</p>
		</div>
	</PanelRow>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { TextInput } from "frappe-ui";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { acts } from "@/acts/dispatcher";
import { __, __n } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import { fieldnameMode } from "./fieldPanel";
import PanelRow from "./PanelRow.vue";

const props = defineProps<{ canvas: DesignCanvas; field: RawMetaField }>();

const mode = computed(() => fieldnameMode(props.canvas, props.field.fieldname));
const lockedNote = computed(() =>
	__("A standard field keeps its fieldname. Renaming it needs a patch in the app.")
);
const lane = computed(() =>
	props.canvas.customize && mode.value === "locked" ? lockedNote.value : ""
);
const was = computed(() => {
	const saved = props.canvas.savedName(props.field.fieldname);
	return saved && saved !== props.field.fieldname ? saved : "";
});
const moves = computed(() => {
	const count = props.canvas.valueCount(props.field.fieldname);
	return count
		? __n(
				"Renames the column on save; its {0} value moves with it.",
				"Renames the column on save; its {0} values move with it.",
				count,
				[count]
		  )
		: __("Renames the column on save; no record holds a value in it.");
});

async function rename(event: Event) {
	const input = event.target as HTMLInputElement;
	const typed = input.value.trim();
	const { fieldname } = props.field;
	if (typed === fieldname) return;
	await acts.perform("fields.rename_field", { fieldname, new_fieldname: typed });
	// A refused rename leaves the prop as it was, so the input would keep the typed name.
	if (!props.canvas.field(typed)) input.value = fieldname;
}
</script>
