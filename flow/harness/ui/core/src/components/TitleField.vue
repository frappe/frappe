<template>
	<!-- a name edited in place: Enter or leaving it saves, Escape keeps the old one, as does an empty one -->
	<TextInput
		ref="field"
		v-model="draft"
		size="sm"
		variant="outline"
		:aria-label="label"
		@keydown.enter.prevent="(e) => composing(e) || save(true)"
		@keydown.esc.prevent.stop="(e) => composing(e) || cancel()"
		@blur="save(false)"
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
// where the focus was, a menu's trigger once it has handed it back: Enter and Escape return it there
let from = null

// an IME's Enter picks a candidate and its Escape drops one; Safari marks its closing key only by keyCode 229
const composing = (e) => e.isComposing || e.keyCode === 229

onMounted(() => {
	const active = field.value?.inputElement?.getRootNode().activeElement
	from = active && active !== document.body ? active : null
	field.value?.focus()
	field.value?.inputElement?.select()
})

function finish(event, title, back) {
	if (done) return
	done = true
	if (back && from) setTimeout(() => from.isConnected && from.focus())
	emit(event, title)
}

// leaving the field saves too, and leaves the focus where it went
function save(back) {
	const title = draft.value.trim()
	if (title && title !== props.value) finish("save", title, back)
	else finish("cancel", undefined, back)
}

function cancel() {
	finish("cancel", undefined, true)
}
</script>
