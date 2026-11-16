<!-- The open layout's tabs, sections, columns and fields, and "Add section". Every canvas draws it;
     the tab strip shows once the layout has two tabs, and until then "Add tab" sits beside "Add section"
     (not on the Side panel or a child table). -->
<template>
	<CanvasContextMenu
		v-if="canvas.contextMenu.value"
		:canvas="canvas"
		:at="canvas.contextMenu.value"
	/>
	<CanvasTabs v-if="canvas.tabs.value.length > 1" class="mb-6" :canvas="canvas" />
	<Draggable
		v-for="drawn in drawnTabs"
		:class="{ 'canvas-tab-held': drawn !== tab }"
		:key="drawn.name"
		:model-value="drawn.sections"
		:item-key="(section: LayoutTreeSection) => section.name"
		group="canvas-sections"
		handle=".section-grip"
		class="flex flex-col gap-10"
		ghost-class="opacity-40"
		v-bind="DRAG_OPTIONS"
		:disabled="!canvas.editable || drawn !== tab"
		@start="holdOnTab(canvas)"
		@end="releaseFromTab(canvas)"
		@change="dropSection(canvas, $event, drawn.name!)"
	>
		<template #item="{ element: section }">
			<CanvasSection :canvas="canvas" :section="section" />
		</template>
	</Draggable>
	<p v-if="tab && !tab.sections.length" class="mt-6 text-base text-ink-gray-5">
		{{ __("This tab has no sections.") }}
	</p>
	<div v-if="canvas.editable" class="mt-10 flex gap-2 border-t pt-4" data-canvas-add-section>
		<Button
			variant="subtle"
			size="sm"
			icon-left="lucide-plus"
			:label="__('Add section')"
			@click.stop="acts.perform('canvas.add_section')"
		/>
		<Button
			v-if="takesTabs && canvas.tabs.value.length < 2"
			variant="subtle"
			size="sm"
			icon-left="lucide-panel-top"
			:label="__('Add tab')"
			data-canvas-add-tab
			@click.stop="acts.perform('canvas.add_tab')"
		/>
	</div>
</template>

<script setup lang="ts">
import { computed, watch } from "vue";
import { Button } from "frappe-ui";
import Draggable from "vuedraggable";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import CanvasSection from "./CanvasSection.vue";
import CanvasTabs from "./CanvasTabs.vue";
import { CanvasContextMenu } from "./canvasContextMenu";
import { DRAG_OPTIONS, dropSection, holdOnTab, releaseFromTab } from "./canvasDrops";
import type { DesignCanvas } from "./designCanvas";
import type { LayoutTreeSection } from "./layoutTree";

const props = withDefaults(defineProps<{ canvas: DesignCanvas; tabbed?: boolean }>(), {
	tabbed: true,
});

/** The Side panel and a child table's row dialog have no tabs. */
const takesTabs = computed(() => props.tabbed && !props.canvas.state.definition.istable);
const tab = computed(() => props.canvas.openTab.value);
// Sortable drops its whole drag when a list unmounts: while a field or section is held, every tab it
// passed over stays drawn (collapsed unless open) until the drop.
const drawnTabs = computed(() =>
	props.canvas.tabs.value.filter(
		(candidate) =>
			candidate === tab.value || props.canvas.held.value?.seen.includes(candidate.name!)
	)
);
watch(
	() => tab.value?.name,
	(name) => {
		const { held } = props.canvas;
		if (name && held.value && !held.value.seen.includes(name))
			held.value = { ...held.value, seen: [...held.value.seen, name] };
	}
);
</script>
