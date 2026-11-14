<!-- Every field type, A to Z, in a searchable list: a click adds a field of that type where the
     canvas is looking, a drag drops it on the exact place in the form. -->
<template>
	<div class="flex flex-col" data-panel-new-field>
		<PanelSection :label="label">
			<TextInput v-model="query" :placeholder="__('Search field types')">
				<template #prefix
					><Icon name="lucide-search" class="size-4 text-ink-gray-5"
				/></template>
				<template v-if="query" #suffix
					><button
						type="button"
						class="grid size-5 place-items-center rounded-3 text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-8"
						:aria-label="__('Clear')"
						data-types-clear
						@click="query = ''"
					>
						<Icon name="lucide-x" class="size-3.5" /></button
				></template>
			</TextInput>
			<Draggable
				v-if="types.length"
				:model-value="types"
				:group="{ name: 'canvas-fields', pull: 'clone', put: false }"
				:sort="false"
				:item-key="(row: NewType) => row.type"
				class="-mx-2 flex flex-col"
				v-bind="DRAG_OPTIONS"
				data-new-field-types
				:filter="null"
				fallback-class="canvas-drag-fallback"
				ghost-class="canvas-drop-line"
			>
				<template #item="{ element: { type: name } }">
					<ItemListRow
						as="button"
						type="button"
						class="min-h-8 cursor-grab text-left hover:bg-surface-gray-2 active:cursor-grabbing"
						:data-panel-new-type="name"
						:title="__('Click to add, or drag onto the form')"
						@click="add(name)"
					>
						<template #prefix
							><Icon :name="typeIcon(name)" class="size-4 text-ink-gray-5"
						/></template>
						<span class="block truncate text-ink-gray-8">{{ __(name) }}</span>
					</ItemListRow>
				</template>
			</Draggable>
			<p v-else class="text-p-sm text-ink-gray-5">{{ __("No field type matches.") }}</p>
		</PanelSection>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
// @ts-ignore, vuedraggable ships no bundled types
import Draggable from "vuedraggable";
import { Icon, ItemListRow, TextInput } from "frappe-ui";
import { __ } from "@/i18n";
import { DRAG_OPTIONS } from "./canvasDrops";
import type { DesignCanvas } from "./designCanvas";
import { addFieldType, type NewType } from "./newField";
import { FIELDTYPE_GROUPS, typeIcon } from "./fieldtypes";
import PanelSection from "./PanelSection.vue";

const props = defineProps<{ canvas: DesignCanvas; label: string }>();

const TYPES = [...FIELDTYPE_GROUPS.flatMap((group) => group.types), "Email"].sort();

const query = ref("");
const types = computed<NewType[]>(() => {
	const typed = query.value.trim().toLowerCase();
	return TYPES.filter((name) => __(name).toLowerCase().includes(typed)).map((type) => ({
		type,
	}));
});

function add(name: string) {
	void addFieldType(props.canvas, name, inView());
}

/** The end of the section in view; the open tab when it has none. */
function inView() {
	const { canvas } = props;
	const section = canvas.targetSection();
	return section ? canvas.addPlace(section) : { tab: canvas.openTab.value?.name };
}
</script>
