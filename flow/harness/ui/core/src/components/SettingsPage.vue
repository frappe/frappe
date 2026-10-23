<template>
	<div class="min-h-0 flex-1 overflow-y-auto px-4 pb-6 pt-3 sm:px-8 md:pt-8">
		<div class="flex items-center gap-2">
			<button v-if="back && !headerBack" class="flow-icon-btn -my-1 -ml-1.5" :title="back" @click="emit('back')">
				<FeatherIcon name="arrow-left" class="h-4 w-4" />
			</button>
			<h2 class="text-base font-semibold text-ink-gray-9">{{ title }}</h2>
			<!-- -my-1.5: a button doesn't grow the heading's row, so the heading sits as on other tabs -->
			<div v-if="!layout.narrow" class="-my-1.5 ml-auto flex items-center gap-3"><slot name="actions" /></div>
		</div>
		<p v-if="description" class="mt-1 text-xs leading-5 text-ink-gray-6">{{ description }}</p>
		<div class="pt-4"><slot /></div>
		<!-- a narrow frame has no room beside the heading: the actions end the page -->
		<div v-if="layout.narrow && $slots.actions" class="flex items-center gap-3 pt-4"><slot name="actions" /></div>
	</div>
	<div
		v-if="$slots.footer"
		class="flex shrink-0 flex-wrap items-center gap-3 border-t border-outline-gray-1 px-4 py-4 sm:px-8"
	>
		<slot name="footer" />
	</div>
</template>

<script setup>
import FeatherIcon from "./FeatherIcon.vue"

import { layout } from "../layout.js"
import { useSettingsBack } from "../settingsBack.js"

// A settings panel: a heading and its body in one scrolling column, at the dialog's type scale.
// `back` (the button's title) puts a way back before the heading (in a narrow frame's header),
// for a page that replaced another, like a record's form; `actions` sits at the heading's right
// (a narrow frame's after the body) and `footer` is pinned under the body, for a form's buttons.
const props = defineProps({
	title: { type: String, required: true },
	description: { type: String, default: "" },
	back: { type: String, default: "" },
})
const emit = defineEmits(["back"])
const headerBack = useSettingsBack(() => !!props.back, () => emit("back"))
</script>
