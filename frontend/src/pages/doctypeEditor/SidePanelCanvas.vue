<!-- The Side panel layout: a 380px column in the record panel's look. The built-ins (name, quick
     actions, people) are one locked block; the layout's fields follow as label-left rows. -->
<template>
	<div
		class="mx-auto w-[380px] rounded-7 border border-outline-gray-2 bg-surface-base"
		data-canvas-side-panel
	>
		<div class="px-4 py-3">
			<div
				class="flex items-center gap-2 rounded-6 bg-surface-gray-2 px-3 py-2.5 text-p-sm text-ink-gray-6"
				data-canvas-builtins
			>
				<Icon name="lucide-lock" class="size-3.5 shrink-0 text-ink-gray-5" />
				{{ __("Name, quick actions and people are built in") }}
			</div>
		</div>
		<div
			v-if="empty"
			class="flex flex-col items-center gap-3 border-t border-outline-gray-1 px-6 py-10 text-center"
			data-canvas-side-panel-empty
		>
			<p class="text-base-medium text-ink-gray-8">
				{{ __("No fields on the side panel yet") }}
			</p>
			<p class="text-p-sm text-ink-gray-6">
				{{
					__(
						"Pick fields from the panel on the right. Each one shows on every record's right side."
					)
				}}
			</p>
			<Button
				v-if="canvas.editable"
				variant="subtle"
				size="sm"
				icon-right="lucide-arrow-right"
				:label="__('Add a field')"
				@click.stop="addField"
			/>
		</div>
		<div v-else class="border-t border-outline-gray-1 px-4 py-4">
			<CanvasForm :canvas="canvas" :tabbed="false" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, nextTick } from "vue";
import { Button, Icon } from "frappe-ui";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import CanvasForm from "./CanvasForm.vue";
import type { DesignCanvas } from "./designCanvas";
import { providePanelRows } from "./inertForm";

const props = defineProps<{ canvas: DesignCanvas }>();

providePanelRows();

const empty = computed(() =>
	props.canvas.tabs.value.every((tab) =>
		tab.sections.every((section) => section.columns.every((column) => !column.fields.length))
	)
);

async function addField() {
	await acts.perform("canvas.select", null);
	await nextTick();
	document.querySelector<HTMLInputElement>("input[data-panel-tray-search]")?.focus();
}
</script>
