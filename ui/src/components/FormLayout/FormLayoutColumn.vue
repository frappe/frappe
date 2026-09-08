<template>
	<div class="column flex flex-col gap-4 min-w-0 flex-1">
		<div v-if="column.label && !column.hideLabel" class="text-ink-gray-9 max-w-fit text-base">
			{{ column.label }}
		</div>
		<template v-for="field in visibleFields" :key="field.fieldname">
			<FormLayoutField :field="field" />
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import FormLayoutField from "./FormLayoutField.vue";
import type { Column } from "./types";

const props = defineProps<{ column: Column }>();

const visibleFields = computed(() => props.column.fields.filter((f) => !f.hidden));
</script>
