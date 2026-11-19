<!-- A child table's Preview tab: the dialog a grid row opens, drawn from the child's Details layout as
     the editor has it. Typing changes only this copy. -->
<template>
	<div class="mx-auto w-full max-w-3xl py-6" data-row-dialog-preview>
		<p class="mb-3 text-p-sm text-ink-gray-5">
			{{ __("A row of {0} opens this form. Changes here are not saved.", [tableLabel]) }}
		</p>
		<div
			class="overflow-hidden rounded-7 border border-outline-gray-1 bg-surface-elevation-1 shadow-xl"
		>
			<div class="flex items-center justify-between gap-2 px-6 pb-2 pt-5">
				<h3 class="truncate text-2xl-semibold leading-6 text-ink-gray-8">
					{{ __("{0} — Row {1}", [tableLabel, 1]) }}
				</h3>
				<span class="lucide-x size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
			</div>
			<FormLayout
				v-model:doc="doc"
				:layout="layout"
				:doctype="canvas.state.doctype"
				class="px-6 pb-6"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { FormLayout } from "@framework/ui/FormLayout";
import { __ } from "@/i18n";
import { joinLayout } from "@/recordPage/formLayoutSource/joinLayout";
import type { DesignCanvas } from "./designCanvas";
import { DETAILS } from "./editorModel";
import { refuseWrites } from "./previewRefusals";
import { tabsOf } from "./workingLayouts";

const props = defineProps<{ canvas: DesignCanvas; tableLabel: string }>();

refuseWrites();
const doc = ref<Record<string, unknown>>({});
const layout = computed(() => {
	const working = props.canvas.working.value;
	return joinLayout(tabsOf(working, DETAILS), working.fields);
});
</script>
