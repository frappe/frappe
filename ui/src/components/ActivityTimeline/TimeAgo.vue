<template>
	<!-- relative label ("2h ago") with the absolute date on hover; size class passes through -->
	<Tooltip :text="dateFormat(timestamp)">
		<span class="text-ink-gray-5" v-bind="$attrs">{{ timeAgo(timestamp) }}</span>
	</Tooltip>
</template>

<script setup lang="ts">
import { Tooltip } from "frappe-ui";
import { dateFormat, timeAgo } from "./utils";

defineProps<{ timestamp: string }>();
defineOptions({ inheritAttrs: false });
</script>
