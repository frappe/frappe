<!-- "Fields not on this layout" under a read-only canvas, which has no side panel to list them in. -->
<template>
	<div class="mt-10 border-t pt-4" data-canvas-tray>
		<button
			type="button"
			class="flex h-7 items-center gap-1.5 text-base-medium text-ink-gray-8"
			:aria-expanded="canvas.trayOpen.value"
			@click="canvas.trayOpen.value = !canvas.trayOpen.value"
		>
			<span
				class="size-4 text-ink-gray-5"
				:class="canvas.trayOpen.value ? 'lucide-chevron-down' : 'lucide-chevron-right'"
				aria-hidden="true"
			/>
			{{ __("Fields not on this layout") }}
			<span class="text-ink-gray-5">{{ rows.length }}</span>
		</button>
		<div
			v-show="canvas.trayOpen.value"
			class="mt-2 flex min-h-8 flex-col"
			data-canvas-tray-list
		>
			<div
				v-for="row in rows"
				:key="row.field.fieldname"
				class="-mx-2 flex h-8 items-center gap-2 rounded-4 px-2"
				:class="
					isSelected(row.field.fieldname)
						? 'ring-1 ring-outline-gray-4'
						: 'hover:bg-surface-gray-2'
				"
				:data-canvas-tray-field="row.field.fieldname"
				:data-canvas-selected="isSelected(row.field.fieldname) || undefined"
				@click.stop="
					acts.perform('canvas.select', {
						kind: 'field',
						fieldname: row.field.fieldname,
					})
				"
			>
				<span class="min-w-0 truncate text-base text-ink-gray-8">{{
					label(row.field)
				}}</span>
				<span class="shrink-0 text-sm text-ink-gray-5">{{ __(row.field.fieldtype) }}</span>
				<Badge v-if="row.new" theme="gray" :label="__('New since the save')" />
				<Badge v-if="row.asked" theme="gray" :label="__('Asked for on save')" />
			</div>
		</div>
		<p
			v-if="canvas.trayOpen.value && !rows.length"
			class="pointer-events-none -mt-8 flex h-8 items-center text-base text-ink-gray-5"
		>
			{{ __("Every field is on this layout.") }}
		</p>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Badge } from "frappe-ui";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";

const props = defineProps<{ canvas: DesignCanvas }>();

const rows = computed(() => props.canvas.offLayout.value);

function label(field: RawMetaField) {
	return field.label ? __(field.label, [], props.canvas.state.doctype) : field.fieldname;
}

function isSelected(fieldname: string) {
	const selection = props.canvas.selection.value;
	return selection?.kind === "field" && selection.fieldname === fieldname;
}
</script>
