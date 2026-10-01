<template>
	<div
		role="button"
		tabindex="0"
		:aria-expanded="entry.type === 'dir' ? expanded : undefined"
		class="relative flex cursor-pointer items-center gap-1.5 rounded-4 py-[5px] pr-1.5 text-sm hover:bg-surface-gray-2"
		:class="active ? 'bg-surface-gray-3 font-medium text-ink-gray-9' : 'text-ink-gray-8'"
		:style="{ paddingLeft: depth * INDENT + 8 + 'px' }"
		:title="path"
		@click="activate"
		@keydown.enter.prevent="activate"
		@keydown.space.prevent="activate"
	>
		<span
			v-for="level in depth"
			:key="level"
			class="pointer-events-none absolute inset-y-0 w-px bg-[--outline-gray-1]"
			:style="{ left: (level - 1) * INDENT + 16 + 'px' }"
		/>
		<span class="grid h-4 w-4 flex-none place-items-center">
			<FeatherIcon
				:name="entry.type === 'dir' ? (expanded ? 'chevron-down' : 'chevron-right') : 'file'"
				class="h-3.5 w-3.5 text-ink-gray-5"
			/>
		</span>
		<span class="min-w-0 truncate">{{ entry.name }}</span>
	</div>
	<template v-if="entry.type === 'dir' && expanded && children">
		<FileTree v-for="child in children" :key="child.name" :entry="child" :dir="path" :depth="depth + 1" />
	</template>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

const INDENT = 16

const props = defineProps({
	entry: { type: Object, required: true }, // { name, type: "dir" | "file" }
	dir: { type: String, required: true }, // absolute path of the parent directory
	depth: { type: Number, default: 0 },
})

const flow = inject("flow")
const path = computed(() => `${props.dir.replace(/\/+$/, "")}/${props.entry.name}`)
const active = computed(() => props.entry.type === "file" && flow.state.workspace.active === path.value)
const expanded = ref(false)
const children = ref(null)

async function activate() {
	if (props.entry.type === "file") return flow.openFile(path.value)
	expanded.value = !expanded.value
	if (!expanded.value) return
	const data = await flow.listFiles(path.value) // refetch on every expand: stays fresh
	if (data) children.value = data.entries
}
</script>
