<!-- A cell an app described on its column in `list.js`: an icon before the text, or a badge; a badge with filters is a button. -->
<template>
	<button
		v-if="view.theme && view.filters"
		type="button"
		:aria-label="__('Filter by {0}', [label])"
		class="rounded-1 focus-visible:ring-2 focus-visible:ring-outline-gray-3"
		@click.stop.prevent="emit('filter', view.filters)"
	>
		<Badge :label="label" :theme="view.theme" class="cursor-pointer" />
	</button>
	<Badge v-else-if="view.theme" :label="label" :theme="view.theme" />
	<div v-else class="flex min-w-0 items-center gap-1.5 text-base text-ink-gray-8">
		<Icon v-if="view.icon" :name="view.icon" class="text-ink-gray-6" />
		<Tooltip v-if="view.title" :text="view.title" class="min-w-0">
			<span class="block truncate">{{ label }}</span>
		</Tooltip>
		<span v-else class="truncate">{{ label }}</span>
	</div>
</template>

<script setup lang="ts">
import type { FieldMeta } from "@framework/ui/fields/types";
import { useFieldDisplay } from "@framework/ui/FormLayout";
import { Badge, Tooltip } from "frappe-ui";
import { computed } from "vue";
import { __ } from "@/i18n";
import Icon from "@/icons/Icon.vue";
import type { CellView } from "@/list/cells";

const props = defineProps<{
	field: FieldMeta;
	row: Record<string, unknown>;
	view: CellView;
}>();

const emit = defineEmits<{ filter: [filters: NonNullable<CellView["filters"]>] }>();

const display = useFieldDisplay();

const label = computed(
	() =>
		props.view.text ??
		props.view.label ??
		display(props.field, props.row[props.field.fieldname], { row: props.row })
);
</script>
