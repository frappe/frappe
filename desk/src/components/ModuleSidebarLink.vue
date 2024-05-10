<template>
	<div class="flex cursor-pointer items-center gap-2 rounded py-1 px-2 hover:bg-gray-200">
		<Icon :name="link.icon" class="h-5 w-5 text-gray-700" />
		<div class="flex items-center gap-1 text-base text-gray-700">
			{{ link.label }}
		</div>
	</div>
</template>

<script setup>
import Icon from "@/components/Icon.vue"

const props = defineProps({
	link: {
		type: Object,
		required: true,
	},
})
</script>
