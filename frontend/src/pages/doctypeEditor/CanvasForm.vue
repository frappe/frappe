<!-- The open layout's tabs, sections, columns and fields, and "Add section" under a rule. Every
     canvas draws it: Details and New record on the page, the others inside their frame, where the
     tab strip shows only once the layout has two tabs. -->
<template>
	<CanvasTabs v-if="tabbed || canvas.tabs.value.length > 1" class="mb-6" :canvas="canvas" />
	<Draggable
		:model-value="tab?.sections ?? []"
		:item-key="(section: LayoutTreeSection) => section.name"
		group="canvas-sections"
		handle=".section-grip"
		class="flex flex-col gap-10"
		ghost-class="opacity-40"
		v-bind="DRAG_OPTIONS"
		:disabled="!canvas.editable"
		@change="tab && dropSection($event, tab.name!)"
	>
		<template #item="{ element: section }">
			<CanvasSection :canvas="canvas" :section="section" />
		</template>
	</Draggable>
	<p v-if="tab && !tab.sections.length" class="mt-6 text-base text-ink-gray-5">
		{{ __("This tab has no sections.") }}
	</p>
	<div v-if="canvas.editable" class="mt-10 flex border-t pt-4" data-canvas-add-section>
		<Button
			variant="subtle"
			size="sm"
			icon-left="lucide-plus"
			:label="__('Add section')"
			@click.stop="acts.perform('canvas.add_section')"
		/>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Button } from "frappe-ui";
import Draggable from "vuedraggable";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import CanvasSection from "./CanvasSection.vue";
import CanvasTabs from "./CanvasTabs.vue";
import { DRAG_OPTIONS, dropSection } from "./canvasDrops";
import type { DesignCanvas } from "./designCanvas";
import type { LayoutTreeSection } from "./layoutTree";

const props = withDefaults(defineProps<{ canvas: DesignCanvas; tabbed?: boolean }>(), {
	tabbed: true,
});

const tab = computed(() => props.canvas.openTab.value);
</script>
