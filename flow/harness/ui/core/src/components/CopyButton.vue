<template>
	<button
		v-bind="$attrs"
		:title="copied ? 'Copied' : title"
		:style="copied ? { opacity: 1 } : undefined"
		@click.stop="copy"
	>
		<FeatherIcon :name="copied ? 'check' : 'copy'" class="h-3.5 w-3.5" />
	</button>
</template>

<script setup>
import { onBeforeUnmount, ref } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

const props = defineProps({
	text: { type: String, required: true },
	title: { type: String, default: "Copy" },
})

const copied = ref(false)
let timer = null

function copy() {
	navigator.clipboard?.writeText(props.text)
	copied.value = true
	clearTimeout(timer)
	timer = setTimeout(() => (copied.value = false), 2000)
}

onBeforeUnmount(() => clearTimeout(timer))
</script>
