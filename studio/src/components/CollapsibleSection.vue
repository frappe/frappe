<!-- Extracted from Builder -->
<template>
	<div>
		<div class="text-sm-medium flex items-center justify-between">
			<h3 class="flex cursor-pointer items-center gap-1.5 text-base text-ink-gray-9" @click="toggleCollapsed">
				{{ sectionName }}
				<slot name="title-suffix" />
			</h3>
			<Button
				class="text-ink-gray-6 hover:bg-surface-gray-2"
				:icon="collapsed ? 'lucide-chevron-right' : 'lucide-chevron-down'"
				:variant="'ghost'"
				size="sm"
				@click="toggleCollapsed"
			></Button>
		</div>
		<div v-if="!collapsed">
			<div class="mb-4 mt-3 flex flex-col gap-3"><slot /></div>
		</div>
	</div>
</template>
<script lang="ts" setup>
import { toValue } from "@vueuse/core"
import { Button } from "frappe-ui"
import { ref, watch } from "vue"

const props = withDefaults(
	defineProps<{
		sectionName: string
		sectionCollapsed?: boolean
	}>(),
	{
		sectionCollapsed: false,
	},
)

const collapsed = ref(false)

const toggleCollapsed = () => {
	collapsed.value = !collapsed.value
}

watch(
	() => props.sectionCollapsed,
	() => {
		collapsed.value = toValue(props.sectionCollapsed)
	},
	{ immediate: true },
)
</script>
