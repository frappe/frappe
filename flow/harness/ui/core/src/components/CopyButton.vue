<template>
	<Button
		:variant="variant"
		:size="size"
		class="group/copy"
		:title="copied ? 'Copied' : title"
		:style="copied ? { opacity: 1 } : undefined"
		@click.stop="copy"
	>
		<template v-if="$slots.default" #prefix>
			<span class="size-3.5" :class="copied ? 'lucide-check' : icon" aria-hidden="true" />
		</template>
		<template v-if="$slots.default" #default>
			<slot :copied="copied" />
		</template>
		<!-- a bare icon rests quieter than the button's ink, as the other message actions do -->
		<template v-else #icon>
			<span
				class="size-3.5 text-ink-gray-5 group-hover/copy:text-ink-gray-8"
				:class="copied ? 'lucide-check' : icon"
				aria-hidden="true"
			/>
		</template>
	</Button>
</template>

<script setup>
import { onBeforeUnmount, ref } from "vue"
import { Button } from "frappe-ui/src/components/Button"

const props = defineProps({
	text: { type: String, required: true },
	title: { type: String, default: "Copy" },
	icon: { type: String, default: "lucide-copy" },
	variant: { type: String, default: "ghost" },
	size: { type: String, default: "xs" },
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
