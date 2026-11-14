<!-- The canvas's tab strip, drawn from two tabs up. Tabs drag to reorder; a field dropped on a tab's
     name goes to the end of that tab's first section. A double-click renames a tab in place. -->
<template>
	<div class="flex items-end gap-1" :class="{ 'border-b': tabs.length > 1 }" data-canvas-tabs>
		<Draggable
			v-if="tabs.length > 1"
			:model-value="tabs"
			:item-key="(tab: LayoutTreeTab) => tab.name"
			group="canvas-tabs"
			class="flex min-w-0 flex-1 gap-5 overflow-x-auto overflow-y-hidden"
			role="tablist"
			ghost-class="opacity-40"
			v-bind="DRAG_OPTIONS"
			:disabled="!canvas.editable"
			@change="dropTab"
		>
			<template #item="{ element: tab, index }">
				<Draggable
					:model-value="[]"
					item-key="name"
					:group="{ name: 'canvas-fields', pull: false, put: canvas.editable }"
					:sort="false"
					class="canvas-tab-drop -mb-px flex shrink-0 rounded-t-4"
					ghost-class="canvas-drop-line"
					v-bind="DRAG_OPTIONS"
					:data-canvas-tab="tab.name"
					@change="dropField(canvas, $event, { tab: tab.name })"
				>
					<template #item><span /></template>
					<template #header>
						<input
							v-if="renaming === tab.name"
							ref="renameInput"
							:value="tab.label ?? ''"
							:placeholder="__('Untitled tab')"
							class="w-28 border-0 border-b-2 border-outline-gray-5 bg-transparent px-0 pb-2 pt-0 text-base text-ink-gray-9 focus:outline-none focus:ring-0"
							@keydown.enter.prevent="($event.target as HTMLInputElement).blur()"
							@keydown.esc.prevent="renaming = null"
							@blur="rename(tab, ($event.target as HTMLInputElement).value)"
						/>
						<button
							v-else
							type="button"
							role="tab"
							class="relative shrink-0 whitespace-nowrap rounded-t-4 border-b-2 px-2 pb-2 pt-1 text-base"
							:class="[
								tab === canvas.openTab.value
									? 'border-outline-gray-5 bg-surface-gray-2 text-ink-gray-9'
									: [
											'border-transparent hover:text-ink-gray-7',
											tab.label ? 'text-ink-gray-5' : 'text-ink-gray-4',
									  ],
							]"
							:aria-selected="tab === canvas.openTab.value"
							@click.stop="select(tab)"
							@dblclick="startRename(tab)"
						>
							{{ tabLabel(tab, index) }}
							<RuleMark class="ml-1" :canvas="canvas" kind="tab" :node="tab" />
						</button>
					</template>
				</Draggable>
			</template>
		</Draggable>
		<div v-if="canvas.editable" class="flex shrink-0 items-center gap-1 pb-1.5">
			<Tooltip :text="__('Add tab')">
				<Button
					variant="ghost"
					size="sm"
					icon="lucide-plus"
					:aria-label="__('Add tab')"
					data-canvas-add-tab
					@click.stop="acts.perform('canvas.add_tab')"
				/>
			</Tooltip>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { Button, Tooltip } from "frappe-ui";
import Draggable from "vuedraggable";
import { tabStripLabel } from "@framework/ui/FormLayout";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { LayoutTreeTab } from "./layoutTree";
import { DRAG_OPTIONS, dropField, dropTab } from "./canvasDrops";
import { selectOn } from "./canvasMenu";
import type { DesignCanvas } from "./designCanvas";
import RuleMark from "./RuleMark.vue";

const props = defineProps<{ canvas: DesignCanvas }>();

const tabs = computed(() => props.canvas.tabs.value);
const renaming = ref<string | null>(null);
const renameInput = ref<HTMLInputElement | null>(null);

/** An unlabelled first tab reads "Details", as on the record page. */
function tabLabel(tab: LayoutTreeTab, index: number) {
	if (tab.label) return __(tab.label, [], props.canvas.state.doctype);
	return index ? __("Untitled tab") : tabStripLabel("", true);
}

function select(tab: LayoutTreeTab) {
	selectOn(props.canvas, { kind: "tab", tab: tab.name! });
}

async function startRename(tab: LayoutTreeTab) {
	if (!props.canvas.editable) return;
	renaming.value = tab.name!;
	await nextTick();
	renameInput.value?.focus();
}

function rename(tab: LayoutTreeTab, label: string) {
	if (renaming.value !== tab.name) return;
	renaming.value = null;
	if (label.trim() === (tab.label ?? "")) return;
	void acts.perform("canvas.set_container_property", {
		container: tab.name,
		property: "label",
		value: label.trim(),
	});
}
</script>
