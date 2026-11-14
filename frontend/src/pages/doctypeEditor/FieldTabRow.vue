<!-- The panel's Tab row, a second way to move a field to another tab: the drag works too. The
     field lands at the end of the first section of the tab it is moved to. -->
<template>
	<PanelRow :label="__('Tab')" v-bind="mark">
		<Dropdown :options="options" side="bottom" align="start">
			<button
				type="button"
				class="flex h-7 w-full items-center gap-2 rounded-4 px-2 text-left text-base text-ink-gray-8"
				data-panel-tab
			>
				<span
					class="lucide-panel-top size-4 shrink-0 text-ink-gray-5"
					aria-hidden="true"
				/>
				<span class="min-w-0 flex-1 truncate">{{ current }}</span>
				<span
					class="lucide-chevron-down size-4 shrink-0 text-ink-gray-5"
					aria-hidden="true"
				/>
			</button>
		</Dropdown>
	</PanelRow>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Dropdown } from "frappe-ui";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import { panelMark } from "./fieldPanel";
import PanelRow from "./PanelRow.vue";

const props = defineProps<{ canvas: DesignCanvas; field: RawMetaField }>();

const name = (label?: string) => label || __("Untitled tab");
const place = computed(() => props.canvas.place(props.field.fieldname));
const current = computed(() => {
	const tab = props.canvas.tabs.value.find((one) => one.name === place.value?.tab);
	return name(tab?.label);
});
const mark = computed(() => panelMark(props.canvas, props.field.fieldname, "tab"));
const options = computed(() =>
	props.canvas.tabs.value.map((tab) => ({
		label: name(tab.label),
		onClick: () => move(tab.name!),
	}))
);

async function move(tab: string) {
	if (tab === place.value?.tab) return;
	await acts.perform("canvas.move_field", { fieldname: props.field.fieldname, tab });
	if (props.canvas.place(props.field.fieldname)?.tab === tab)
		props.canvas.openTabName.value = tab;
}
</script>
