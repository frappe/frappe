<template>
	<div class="flex items-start gap-2">
		<Icon
			v-if="item.icon"
			:name="item.icon"
			class="mt-0.5 size-4 shrink-0 text-ink-gray-6"
			aria-hidden="true"
		/>
		<div class="min-w-0">
			<div class="truncate">{{ item.label }}</div>
			<div v-if="item.description" class="truncate text-p-sm text-ink-gray-5">
				{{ item.description }}
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Icon } from "frappe-ui";
import type { AutomationCanvasOption } from "./types";

defineProps<{ item: AutomationCanvasOption }>();
</script>
