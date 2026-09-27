<template>
	<DialogRoot :open="show" @update:open="onOpenChange">
		<DialogPortal>
			<DialogOverlay class="fixed inset-0 z-[100] bg-black-overlay-200 dark:bg-black-overlay-700" />
			<DialogContent
				class="fixed left-1/2 top-[10%] z-[100] w-full max-w-[560px] -translate-x-1/2 overflow-hidden rounded-5 bg-surface-base shadow-[0_24px_60px_-12px_rgba(0,0,0,0.25)] ring-1 ring-black/[0.06] focus-visible:outline-none dark:ring-white/[0.08]"
				@open-auto-focus.prevent
				@escape-key-down.prevent="onEscapeKey">
				<DialogTitle class="sr-only">Command Palette</DialogTitle>

				<!-- Search bar -->
				<div class="flex items-center border-b border-outline-gray-1 px-1">
					<span class="lucide-search ml-3 size-4 shrink-0 text-ink-gray-4" aria-hidden="true" />
					<!-- Step badge -->
					<button
						v-if="stepLabel"
						type="button"
						class="text-base-semibold ml-3 flex shrink-0 items-center gap-2 py-1 text-ink-gray-7 transition-colors hover:bg-surface-gray-3"
						@click="goBack">
						{{ stepLabel }}
						<span class="lucide-chevron-right size-3 text-ink-gray-4" aria-hidden="true" />
					</button>
					<input
						ref="inputRef"
						v-model="localQuery"
						:placeholder="placeholder || (stepLabel ? 'Search...' : 'Search commands...')"
						class="w-full border-none bg-transparent py-3.5 pl-3 pr-4 text-base text-ink-gray-8 placeholder-ink-gray-4 outline-none ring-0 focus:outline-none focus:ring-0"
						autocomplete="off"
						spellcheck="false"
						@keydown="handleKeydown" />
					<kbd
						class="text-xs-medium mr-1.5 flex shrink-0 items-center gap-0.5 rounded-4 border border-outline-gray-2 px-1.5 py-1 text-ink-gray-4"
						title="Close">
						esc
					</kbd>
				</div>

				<!-- Results list -->
				<div ref="listRef" class="max-h-[380px] min-h-[120px] overflow-y-auto py-2">
					<template v-if="hasItems">
						<template v-for="group in groups" :key="group.title">
							<div v-if="group.items.length" class="mb-1 last:mb-0">
								<div v-if="!group.hideTitle" class="px-4 pb-1 pt-2 text-sm tracking-wider text-ink-gray-4">
									{{ group.title }}
								</div>
								<div
									v-for="(item, idx) in group.items"
									:key="item.name"
									:data-active="flatIndex(group, idx) === activeIndex"
									:class="['cursor-pointer px-2', { 'pointer-events-none opacity-40': item.disabled }]"
									@mouseenter="!item.disabled && (activeIndex = flatIndex(group, idx))"
									@click="!item.disabled && select(item)">
									<component
										:is="group.component"
										:item="item"
										:show-description="group.showDescription === true"
										:active="flatIndex(group, idx) === activeIndex" />
								</div>
							</div>
						</template>
					</template>
					<div v-else class="flex flex-col items-center py-12 text-ink-gray-4">
						<span
							:class="[
								loading
									? 'lucide-loader-circle animate-spin'
									: localQuery
										? 'lucide-search-x'
										: 'lucide-search',
								'mb-2.5 size-8 opacity-40',
							]"
							aria-hidden="true" />
						<span class="text-base">
							<template v-if="loading">Searching...</template>
							<template v-else-if="localQuery">No results for "{{ localQuery }}"</template>
							<template v-else>{{ hint || "No commands found" }}</template>
						</span>
					</div>
				</div>

				<!-- Footer -->
				<div class="flex items-center gap-4 border-t border-outline-gray-1 px-4 py-2.5">
					<span class="flex items-center gap-1.5 text-xs text-ink-gray-4">
						<span class="flex gap-1">
							<kbd class="rounded-4 border border-outline-gray-2 p-0.5 text-[11px] font-medium">
								<span class="lucide-arrow-up size-3" />
							</kbd>
							<kbd class="rounded-4 border border-outline-gray-2 p-0.5 text-[11px] font-medium">
								<span class="lucide-arrow-down size-3" />
							</kbd>
						</span>
						Navigate
					</span>
					<span class="flex items-center gap-1.5 text-xs text-ink-gray-4">
						<kbd class="rounded-4 border border-outline-gray-2 p-0.5 text-[11px] font-medium">
							<span class="lucide-corner-down-left size-3" />
						</kbd>
						Select
					</span>
				</div>
			</DialogContent>
		</DialogPortal>
	</DialogRoot>
</template>

<script setup lang="ts">
import { DialogContent, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from "reka-ui"
import { computed, nextTick, ref, watch } from "vue"

export interface CommandPaletteItem {
	name: string
	title: string
	description?: string
	icon?: string | object
	disabled?: boolean
	keepOpen?: boolean
	[key: string]: unknown
}

export interface CommandPaletteGroup {
	title: string
	hideTitle?: boolean
	showDescription?: boolean
	component: object
	items: CommandPaletteItem[]
}

const emit = defineEmits<{
	"update:show": [value: boolean]
	"update:searchQuery": [value: string]
	select: [item: CommandPaletteItem]
	back: []
}>()

const props = withDefaults(
	defineProps<{
		show: boolean
		searchQuery?: string
		groups: CommandPaletteGroup[]
		stepLabel?: string
		placeholder?: string
		hint?: string
		loading?: boolean
	}>(),
	{
		show: false,
		searchQuery: "",
		loading: false,
	},
)

const localQuery = ref(props.searchQuery)
watch(localQuery, (val) => emit("update:searchQuery", val))
watch(
	() => props.searchQuery,
	(val) => {
		if (val !== localQuery.value) localQuery.value = val
	},
)

const inputRef = ref<HTMLInputElement | null>(null)
const listRef = ref<HTMLElement | null>(null)
const activeIndex = ref(0)

const flatItems = computed(() => props.groups.flatMap((g) => g.items.filter((item) => !item.disabled)))

watch(
	() => props.groups,
	() => {
		activeIndex.value = 0
	},
	{ deep: true },
)

function flatIndex(group: CommandPaletteGroup, itemIdx: number) {
	let offset = 0
	for (const g of props.groups) {
		if (g === group) break
		offset += g.items.length
	}
	return offset + itemIdx
}

const hasItems = computed(() => flatItems.value.length > 0)

function scrollActiveIntoView() {
	nextTick(() => {
		const el = listRef.value?.querySelector('[data-active="true"]')
		el?.scrollIntoView({ block: "nearest" })
	})
}

function handleKeydown(e: KeyboardEvent) {
	if (e.key === "ArrowDown") {
		e.preventDefault()
		activeIndex.value = Math.min(activeIndex.value + 1, flatItems.value.length - 1)
		scrollActiveIntoView()
	} else if (e.key === "ArrowUp") {
		e.preventDefault()
		activeIndex.value = Math.max(activeIndex.value - 1, 0)
		scrollActiveIntoView()
	} else if (e.key === "Enter") {
		e.preventDefault()
		const item = flatItems.value[activeIndex.value]
		if (item) select(item)
	} else if (e.key === "Backspace" && !localQuery.value && props.stepLabel) {
		e.preventDefault()
		emit("back")
	}
}

function onOpenChange(val: boolean) {
	emit("update:show", val)
	if (!val) {
		setTimeout(() => {
			localQuery.value = ""
			activeIndex.value = 0
		}, 150)
	}
}

function onEscapeKey() {
	if (localQuery.value) {
		localQuery.value = ""
	} else if (props.stepLabel) {
		emit("back")
	} else {
		onOpenChange(false)
	}
}

function goBack() {
	emit("back")
}

watch(
	() => props.show,
	(val) => {
		if (val) {
			activeIndex.value = 0
			nextTick(() => {
				inputRef.value?.focus()
				inputRef.value?.select()
			})
		}
	},
)

function select(item: CommandPaletteItem) {
	emit("select", item)
	if (item.keepOpen) {
		// a clicked step takes focus from the search, where the next keystrokes belong
		inputRef.value?.focus()
	} else {
		emit("update:show", false)
	}
}
</script>
