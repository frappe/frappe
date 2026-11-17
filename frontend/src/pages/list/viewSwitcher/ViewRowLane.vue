<!-- A view row's suffix lane: one fixed box holding the modified dot, else the default's house; ⋯ takes its place on hover. -->
<template>
	<div
		class="group/lane relative mr-0.5 grid h-full w-7 shrink-0 place-items-center"
		data-view-lane
	>
		<!-- A mark and ⋯ share one cell, so the swap moves nothing and the label never truncates again. -->
		<span
			v-if="modified"
			role="img"
			:aria-label="__('Unsaved changes')"
			class="col-start-1 row-start-1 size-1.5 rounded-full bg-surface-gray-7"
			:title="__('Unsaved changes')"
			:class="hasMenu && HIDE_FOR_MENU"
			data-view-mark="modified"
		/>
		<span
			v-else-if="isDefault"
			role="img"
			:aria-label="__('Default view')"
			class="lucide-house col-start-1 row-start-1 size-3.5 text-ink-gray-6"
			:class="hasMenu && HIDE_FOR_MENU"
			data-view-mark="default"
		/>
		<Dropdown v-if="hasMenu" :options="options" side="bottom" align="start">
			<Button
				variant="ghost"
				size="xs"
				icon="lucide-ellipsis"
				:label="__('View options')"
				class="col-start-1 row-start-1 opacity-0 focus-visible:opacity-100 group-hover/sidebar-item:opacity-100 group-has-[:focus-visible]/sidebar-item:opacity-100 data-[state=open]:opacity-100 group-data-[state=active]/sidebar-item:hover:bg-surface-gray-4 group-data-[state=active]/sidebar-item:data-[state=open]:bg-surface-gray-4"
				data-view
				data-view-menu
			/>
		</Dropdown>
	</div>
</template>

<script setup lang="ts">
import { Button, Dropdown, type DropdownOptions } from "frappe-ui";
import { computed } from "vue";

const props = defineProps<{
	/** The view has changes: a dot, over the house. */
	modified?: boolean;
	isDefault?: boolean;
	/** The view's acts; with none, no ⋯ is drawn and the mark stays on hover. */
	options: DropdownOptions;
}>();

const hasMenu = computed(() => props.options.length > 0);

// The mark gives the cell to ⋯ while the row is hovered, holds focus, or its menu is open.
const HIDE_FOR_MENU =
	"group-hover/sidebar-item:opacity-0 group-has-[:focus-visible]/sidebar-item:opacity-0 group-has-[[data-state=open]]/lane:opacity-0";
</script>
