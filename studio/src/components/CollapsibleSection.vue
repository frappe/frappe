<!-- Extracted from Builder -->
<template>
	<div>
		<div class="text-sm-medium flex items-center justify-between">
			<h3 class="cursor-pointer text-base text-ink-gray-9" @click="toggleCollapsed">
				{{ sectionName }}
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
import { ref, watch } from "vue"

const props = defineProps({
	sectionName: {
		type: String,
		required: true,
	},
	sectionCollapsed: {
		type: [Boolean, Object],
		default: false,
	},
})

const propCollapsed = ref(props.sectionCollapsed)
const collapsed = ref(false)

const toggleCollapsed = () => {
	collapsed.value = !collapsed.value
}

watch(
	() => propCollapsed.value,
	(newVal) => {
		collapsed.value = newVal as boolean
	},
	{ immediate: true },
)
</script>
