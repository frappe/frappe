<template>
	<Popover v-model:open="isOpen" trigger="manual" side="bottom" align="start" bare>
		<template #trigger>
			<button
				type="button"
				class="flex h-7 w-full items-center gap-2 rounded-4 border px-2 text-start text-base text-ink-gray-8 transition-colors focus-visible:border-outline-gray-4 focus-visible:bg-surface-base focus-visible:outline-none"
				:class="VARIANT_CLASSES[variant]"
				@click="isOpen = !isOpen"
			>
				<span v-if="icon" :class="[icon, 'size-4 shrink-0']" aria-hidden="true" />
				<span class="truncate" :class="{ 'text-ink-gray-4': !icon }">
					{{ icon ? iconLabel(icon) : "Select icon" }}
				</span>
				<span
					v-if="icon"
					class="lucide-x ml-auto size-3 shrink-0 text-ink-gray-5 hover:text-ink-gray-8"
					title="Clear"
					@click.stop="select('')"
				/>
			</button>
		</template>
		<template #default>
			<div
				class="flex w-72 flex-col gap-2 rounded-6 bg-surface-elevation-2 p-2 shadow-xl ring-1 ring-outline-gray-1"
			>
				<TextInput v-model="query" placeholder="Search icons" autofocus />
				<div v-if="!icons.length" class="py-6 text-center text-sm text-ink-gray-5">Loading…</div>
				<div v-else-if="!matches.length" class="py-6 text-center text-sm text-ink-gray-5">No icons found</div>
				<div v-else class="grid max-h-64 grid-cols-8 gap-1 overflow-y-auto">
					<button
						v-for="option in matches"
						:key="option"
						type="button"
						class="flex size-8 items-center justify-center rounded-4 text-ink-gray-7 hover:bg-surface-gray-2"
						:class="{ 'bg-surface-gray-3 text-ink-gray-9': option === icon }"
						:title="iconLabel(option)"
						@click="select(option)"
					>
						<span :class="[option, 'size-4']" aria-hidden="true" />
					</button>
				</div>
			</div>
		</template>
	</Popover>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Popover, TextInput } from "frappe-ui"
import { getIcon } from "@/utils/globalUtils"

const MAX_RESULTS = 240

const VARIANT_CLASSES = {
	subtle:
		"border-[--surface-gray-2] bg-surface-gray-2 hover:border-outline-elevation-2 hover:bg-surface-gray-3",
	outline: "border-outline-gray-2 bg-surface-base hover:border-outline-gray-3 hover:shadow-sm",
}

const props = withDefaults(defineProps<{ modelValue?: string; variant?: keyof typeof VARIANT_CLASSES }>(), {
	variant: "subtle",
})

// older saved values wrap the name in the removed sprite helper: {{ getIcon('name') }}
const icon = computed(() => {
	const legacyName = props.modelValue?.match(/getIcon\(['"]([^'"]+)['"]\)/)?.[1]
	return legacyName ? getIcon(legacyName) : props.modelValue
})
const emit = defineEmits<{ "update:modelValue": [value: string] }>()

const isOpen = ref(false)
const query = ref("")
const icons = ref<{ name: string; keywords: string }[]>([])

watch(isOpen, async (open) => {
	if (!open || icons.value.length) return
	const { default: tags } = await import("lucide-static/tags.json")
	icons.value = Object.entries(tags as Record<string, string[]>).map(([name, keywords]) => ({
		name: `lucide-${name}`,
		keywords: `${name} ${keywords.join(" ")}`,
	}))
})

const matches = computed(() => {
	const term = query.value.trim().toLowerCase()
	const found = term ? icons.value.filter((icon) => icon.keywords.includes(term)) : icons.value
	return found.slice(0, MAX_RESULTS).map((icon) => icon.name)
})

function iconLabel(icon: string) {
	return icon.replace(/^lucide-/, "")
}

function select(icon: string) {
	emit("update:modelValue", icon)
	isOpen.value = false
	query.value = ""
}
</script>
