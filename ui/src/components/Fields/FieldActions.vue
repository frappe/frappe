<!-- The actions an app placed on a field, at the end of its control: one is an icon button, two or more a menu. -->
<template>
	<template v-if="actions.length === 1">
		<Button
			variant="ghost"
			size="sm"
			:icon="actions[0].icon ?? 'lucide-zap'"
			:aria-label="actions[0].label"
			:title="actions[0].label"
			data-slot="field-action"
			@click.stop="actions[0].run()"
			@pointerdown.stop
		/>
	</template>
	<Dropdown v-else-if="actions.length" :options="menu" placement="right">
		<Button
			variant="ghost"
			size="sm"
			icon="lucide-ellipsis"
			:aria-label="__('Actions')"
			data-slot="field-actions"
			@pointerdown.stop
		/>
	</Dropdown>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { Button, Dropdown } from "frappe-ui";
import { translate as __ } from "../../utils/translate";
import { FieldActionsKey } from "./types";
import type { FieldMeta } from "./types";

const props = defineProps<{ field: FieldMeta; value: unknown }>();

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
