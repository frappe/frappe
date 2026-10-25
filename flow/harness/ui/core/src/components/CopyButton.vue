<template>
	<button
		v-bind="$attrs"
		:title="copied ? 'Copied' : title"
		:style="copied ? { opacity: 1 } : undefined"
		@click.stop="copy"
	>
		<FeatherIcon :name="copied ? 'check' : icon" class="h-3.5 w-3.5" />
		<slot :copied="copied" />
	</button>
</template>

<script setup>
import { onBeforeUnmount, ref } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

const props = defineProps({
	text: { type: String, required: true },
	title: { type: String, default: "Copy" },
	icon: { type: String, default: "copy" },
})

const copied = ref(false)
let timer = null

async function copy() {
	if (!(await writeText(props.text))) return
	copied.value = true
	clearTimeout(timer)
	timer = setTimeout(() => (copied.value = false), 2000)
}

// the Clipboard API needs a secure context: plain http (a bench, a LAN address) falls
// back to the copy command
async function writeText(text) {
	try {
		await navigator.clipboard.writeText(text)
		return true
	} catch {
		const active = document.activeElement
		const field = document.createElement("textarea")
		field.value = text
		field.style.cssText = "position: fixed; opacity: 0"
		document.body.append(field)
		field.select()
		const done = document.execCommand?.("copy")
		field.remove()
		active?.focus?.()
		return done
	}
}

onBeforeUnmount(() => clearTimeout(timer))
</script>
