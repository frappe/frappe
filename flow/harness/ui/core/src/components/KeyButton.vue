<template>
	<Button :title="saved ? `Change the ${label}` : `Add the ${label}`" @click="open = true">
		<span class="lucide-key size-4 text-ink-gray-7" aria-hidden="true" />
	</Button>
	<Dialog v-model:open="open" :title="label" size="md" @close="onClose">
		<!-- the body replaces the dialog's `message`, so the line is drawn here -->
		<p class="mb-4 text-base text-ink-gray-6">
			{{ saved ? "A key is saved. Paste a new one to replace it." : "It is hidden once saved." }}
		</p>
		<form id="key-form" @submit.prevent="submit">
			<TextInput
				v-model="key"
				type="password"
				autocomplete="off"
				label="API key"
				:placeholder="saved ? '••••••••••••••••' : 'Paste your key'"
				autofocus
			/>
		</form>
		<template #actions>
			<div class="flex items-center gap-2">
				<a v-if="link" :href="link" target="_blank" rel="noopener" class="text-sm text-ink-gray-6 underline">Get a key</a>
				<Button label="Cancel" class="ml-auto" @click="open = false" />
				<Button type="submit" form="key-form" variant="solid" label="Save" :disabled="!key.trim()" />
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { onMounted, ref } from "vue"
import { Button } from "frappe-ui/src/components/Button"
import { Dialog } from "frappe-ui/src/components/Dialog"
import { TextInput } from "frappe-ui/src/components/TextInput"

// A key icon beside a setting that needs an API key; it asks for the key in a dialog, and asks
// on its own when it appears with none saved. "cancel": closed with none saved.
const props = defineProps({
	label: { type: String, required: true },
	saved: { type: Boolean, default: false },
	link: { type: String, default: "" }, // where to get a key
})
const emit = defineEmits(["save", "cancel"])
const open = ref(false)
const key = ref("")
let savedNow = false

onMounted(() => {
	if (!props.saved) open.value = true
})

function submit() {
	if (!key.value.trim()) return
	savedNow = true
	emit("save", key.value.trim())
	open.value = false
}

function onClose() {
	if (!savedNow && !props.saved) emit("cancel")
	key.value = ""
	savedNow = false
}
</script>
