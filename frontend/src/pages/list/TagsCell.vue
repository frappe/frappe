<!-- The Tags column: `_user_tags` is a comma string, with a leading comma when set. -->
<template>
	<div class="flex min-w-0 items-center gap-1 overflow-hidden">
		<Badge v-for="tag in tags" :key="tag" :label="tag" theme="gray" class="shrink-0" />
	</div>
</template>

<script setup lang="ts">
import { Badge } from "frappe-ui";
import { computed } from "vue";

const props = defineProps<{ value: unknown }>();

const tags = computed(() =>
	typeof props.value === "string" ? props.value.split(",").filter(Boolean) : []
);
</script>
