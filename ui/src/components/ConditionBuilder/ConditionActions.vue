<!--
  The per-row overflow menu: Turn into a Group / Ungroup / Remove. `Button`
  overwrites `aria-label` from its `label`, so the icon-only trigger is named
  through `aria-labelledby`, including the row's field.

  Past the depth limit a leaf has only Remove left, and the single action is
  drawn as itself rather than as a menu of one.

  Reordering is not in here: the handle is the way a row moves, which leaves it
  pointer-only. A host that needs a keyboard path puts one in `#condition-actions`.
-->
<template>
	<div v-if="!readonly" data-slot="condition-actions" class="w-max">
		<Dropdown v-if="!only" placement="right" :options="options">
			<Button variant="ghost" icon="lucide-more-horizontal" :aria-labelledby="nameIds" />
		</Dropdown>
		<Button
			v-else
			variant="ghost"
			:icon="only.icon"
			:theme="only.theme"
			:aria-labelledby="nameIds"
			@click="only.onClick"
		/>
		<span :id="nameId" class="sr-only">{{ name }}</span>
	</div>
</template>

<script setup lang="ts">
import { computed, useId } from "vue";
import { Button, Dropdown } from "frappe-ui";
import { useConditionBuilderContext } from "./internal/context";
import { canNest } from "./tree";
import type { ConditionPath } from "./types";

const props = defineProps<{
	path: ConditionPath;
	isGroup: boolean;

	/** Id of the element holding this row's field label, rendered by the row. */
	fieldLabelId?: string;
}>();

const context = useConditionBuilderContext();
const labels = context.labels;
const readonly = computed(() => context.readonly.value);
const nameId = useId();

const nameIds = computed(() => (props.fieldLabelId ? `${props.fieldLabelId} ${nameId}` : nameId));

interface ActionItem {
	label: string;
	icon?: string;
	theme?: "red";
	onClick: () => void;
}

const options = computed<ActionItem[]>(() => {
	const items: ActionItem[] = [];

	// Wrapping a leaf has the same reach as adding a group to its parent.
	const parentPath = props.path.slice(0, -1);

	if (!props.isGroup && canNest(parentPath, context.maxDepth.value)) {
		items.push({
			label: labels.value.turnIntoGroup,
			icon: "lucide-group",
			onClick: () => context.turnIntoGroup(props.path),
		});
	}

	if (props.isGroup) {
		items.push({
			label: labels.value.ungroup,
			icon: "lucide-ungroup",
			onClick: () => context.ungroup(props.path),
		});
	}

	items.push({
		label: props.isGroup ? labels.value.removeGroup : labels.value.remove,
		icon: "lucide-trash-2",
		theme: "red",
		onClick: () => context.remove(props.path),
	});

	return items;
});

/** The one action, when there is only one. Null draws the menu. */
const only = computed<ActionItem | null>(() =>
	options.value.length === 1 ? options.value[0] : null
);

// Named by the action once it is the control, by the menu while it is a menu.
const name = computed(() => {
	if (only.value) return only.value.label;
	return props.isGroup ? labels.value.groupActions : labels.value.rowActions;
});
</script>
