<!--
  A group's add affordance, extracted so both conjunction placements draw the
  same control. Two things to add, so it is a menu, until `maxDepth` leaves only
  one and the control is the button itself. Adding a group is dropped rather than
  disabled: nothing the user can do from here would re-enable it.
-->
<template>
	<Dropdown v-if="canAddGroup" v-slot="{ open }" :options="options">
		<Button
			data-slot="add-condition"
			:label="labels.addCondition"
			icon-left="lucide-plus"
			:icon-right="open ? 'lucide-chevron-up' : 'lucide-chevron-down'"
		/>
	</Dropdown>
	<Button
		v-else
		data-slot="add-condition"
		:label="labels.addCondition"
		icon-left="lucide-plus"
		@click="addCondition"
	/>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Button, Dropdown } from "frappe-ui";
import { useConditionBuilderContext } from "./internal/context";
import type { ConditionPath } from "./types";

const props = defineProps<{
	/** The group to add into. */
	path: ConditionPath;

	/** False when a new group here would exceed `maxDepth`. */
	canAddGroup?: boolean;
}>();

const context = useConditionBuilderContext();
const labels = context.labels;

function addCondition() {
	context.addCondition(props.path);
}

interface AddItem {
	label: string;
	onClick: () => void;
}

const options = computed<AddItem[]>(() => {
	return [
		{
			label: labels.value.addCondition,
			onClick: () => context.addCondition(props.path),
		},
		{
			label: labels.value.addGroup,
			onClick: () => context.addGroup(props.path),
		},
	];
});
</script>
