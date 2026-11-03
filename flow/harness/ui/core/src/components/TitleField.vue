<template>
	<!-- a name edited in place: Enter or leaving it saves, Escape keeps the old one, as does an empty one -->
	<TextInput
		ref="field"
		v-model="draft"
		size="sm"
		variant="outline"
		:aria-label="label"
		@keydown.enter.prevent="save"
		@keydown.esc.prevent.stop="cancel"
		@blur="save"
		@click.stop
		@pointerdown.stop
	/>
</template>

<script setup>
import { onMounted, ref } from "vue"
import { TextInput } from "frappe-ui/src/components/TextInput"

const props = defineProps({
	value: { type: String, required: true },
	label: { type: String, default: "Name" },
})
const emit = defineEmits(["save", "cancel"])

const draft = ref(props.value)
const field = ref(null)
let done = false

onMounted(() => {
	field.value?.focus()
	field.value?.inputElement?.select()
})

function save() {
	if (done) return
	done = true
	const title = draft.value.trim()
	if (title && title !== props.value) emit("save", title)
	else emit("cancel")
}

function cancel() {
	if (done) return
	done = true
	emit("cancel")
}
</script>
