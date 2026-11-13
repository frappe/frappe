<!-- What a field shows in Customize: "Custom" on a field the site added, a dot on a standard
     field the site changed (its tooltip names what), an eye on a hidden one. -->
<template>
	<template v-if="marks">
		<Tooltip v-if="marks.hidden" :text="__('Hidden on the form')">
			<span
				class="lucide-eye-off size-3.5 shrink-0 text-ink-gray-5"
				:aria-label="__('Hidden')"
				data-canvas-mark="hidden"
			/>
		</Tooltip>
		<Badge
			v-if="marks.custom"
			:label="__('Custom')"
			theme="gray"
			size="sm"
			class="shrink-0"
			data-canvas-mark="custom"
		/>
		<Tooltip v-else-if="marks.changed.length" :text="changedText">
			<span
				class="grid size-3.5 shrink-0 place-items-center"
				:aria-label="__('Changed on this site')"
				data-canvas-mark="changed"
			>
				<span class="size-1.5 rounded-full bg-surface-gray-7" />
			</span>
		</Tooltip>
	</template>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Badge, Tooltip } from "frappe-ui";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import { propertyLabel } from "./fieldPanel";

const props = defineProps<{ canvas: DesignCanvas; fieldname: string }>();

const marks = computed(() => props.canvas.customize?.marks(props.fieldname) ?? null);
const changedText = computed(() =>
	__("Changed on this site: {0}", [(marks.value?.changed ?? []).map(propertyLabel).join(", ")])
);
</script>
