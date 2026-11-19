<!-- A Link field's "Fetched fields" row: "Fetch a field…" and the fields that already copy from it. -->
<template>
	<PanelRow :label="__('Fetched fields')" :box="false">
		<div class="flex min-h-7 flex-col justify-center">
			<FetchAddButton :link="field" />
			<p v-if="line" class="px-2 pb-1 text-p-sm text-ink-gray-5" data-panel-fetched>
				{{ line }}
			</p>
		</div>
	</PanelRow>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import FetchAddButton from "./FetchAddButton.vue";
import { fetchedLine } from "./fetchFrom";
import PanelRow from "./PanelRow.vue";

const props = defineProps<{ canvas: DesignCanvas; field: RawMetaField }>();

const line = computed(() => fetchedLine(props.canvas.working.value.fields, props.field.fieldname));
</script>
