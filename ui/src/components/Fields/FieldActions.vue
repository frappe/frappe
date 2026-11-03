<!-- The actions an app placed on a field, at the end of its control: one is an icon button, two or more a menu. -->
<template>
	<button
		v-if="actions.length === 1"
		type="button"
		:aria-label="actions[0].label"
		:title="actions[0].label"
		data-slot="field-action"
		:class="buttonClass"
		@click.stop="actions[0].run()"
		@pointerdown.stop
	>
		<span :class="[actions[0].icon ?? 'lucide-zap', 'size-3.5']" />
	</button>
	<Dropdown v-else-if="actions.length" :options="menu" placement="right">
		<button
			type="button"
			:aria-label="__('Actions')"
			data-slot="field-actions"
			:class="buttonClass"
			@pointerdown.stop
		>
			<span class="lucide-ellipsis size-3.5" />
		</button>
	</Dropdown>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { Dropdown } from "frappe-ui";
import { translate as __ } from "../../utils/translate";
import { FieldActionsKey } from "./types";
import type { FieldMeta } from "./types";

const props = defineProps<{ field: FieldMeta; value: unknown }>();

const buttonClass =
	"grid size-4 shrink-0 place-items-center rounded-1 text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-7 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3 data-[state=open]:bg-surface-gray-3 data-[state=open]:text-ink-gray-7";

const host = inject(FieldActionsKey, null);

const actions = computed(() => host?.for(props.field, props.value) ?? []);
const menu = computed(() =>
	actions.value.map((action) => ({
		label: action.label,
		icon: action.icon,
		onClick: action.run,
	}))
);
</script>
