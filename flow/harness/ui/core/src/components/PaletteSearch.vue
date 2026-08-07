<template>
	<div class="flex h-10 flex-none items-center gap-2 border-b border-outline-gray-1 px-3">
		<FeatherIcon name="search" class="h-3.5 w-3.5 flex-none text-ink-gray-4" />
		<input
			ref="input"
			v-model="model"
			v-bind="$attrs"
			spellcheck="false"
			class="h-full w-full min-w-0 border-0 bg-transparent p-0 text-xs text-ink-gray-9 outline-none placeholder:text-ink-gray-4 focus:ring-0"
		/>
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue"
import FeatherIcon from "frappe-ui/src/components/FeatherIcon.vue"

defineOptions({ inheritAttrs: false })
const props = defineProps({ autofocus: { type: Boolean, default: false } })
const model = defineModel({ type: String, default: "" })

const input = ref(null)
onMounted(() => props.autofocus && input.value?.focus())
</script>
