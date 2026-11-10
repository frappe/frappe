<!-- Extracted from Builder -->
<template>
	<div>
		<div class="text-sm-medium flex cursor-pointer items-center justify-between" @click="toggleCollapsed">
			<h3 class="flex items-center gap-1.5 text-base text-ink-gray-9">
				{{ sectionName }}
				<slot name="title-suffix" />
			</h3>
			<Button
				class="text-ink-gray-6 hover:bg-surface-gray-2"
				:icon="collapsed ? 'lucide-chevron-right' : 'lucide-chevron-down'"
				:variant="'ghost'"
				size="sm"
			></Button>
		</div>
		<div v-if="!collapsed">
			<div class="mb-4 mt-3 flex flex-col gap-3"><slot /></div>
		</div>
	</div>
</template>
<script lang="ts" setup>
import { Button } from "frappe-ui"
import { ref, toValue, watch } from "vue"

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
