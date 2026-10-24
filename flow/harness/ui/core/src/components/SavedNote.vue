<template>
	<span
		class="flex items-center gap-1 text-xs text-ink-gray-5 transition-opacity"
		:class="shown ? 'opacity-100 duration-150' : 'opacity-0 duration-500'"
		aria-hidden="true"
	>
		<FeatherIcon name="check" class="h-3.5 w-3.5" />
		Saved
	</span>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

// "Saved" beside a setting that applies as it changes, as there's no Save button: it shows
// whenever `value` changes and fades a moment after the last change
const props = defineProps({ value: { type: [String, Number], default: null } })
const shown = ref(false)
let hide = 0
watch(
	() => props.value,
	() => {
		shown.value = true
		clearTimeout(hide)
		hide = setTimeout(() => (shown.value = false), 1500)
	},
)
onBeforeUnmount(() => clearTimeout(hide))
</script>
