<template>
	<Tooltip :text="description" :hoverDelay="1">
		<span
			v-bind="$attrs"
			class="block w-1/2 min-w-20 max-w-40 items-center truncate text-xs leading-5 text-ink-gray-5"
		>
			<slot />
		</span>
	</Tooltip>
</template>

<script setup lang="ts">
import { Tooltip } from "frappe-ui"

defineProps<{ description?: string }>()
defineOptions({ inheritAttrs: false })
</script>
