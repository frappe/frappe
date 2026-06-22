<!-- Extracted from Builder - modified later -->
<template>
	<div ref="searchBlock" class="focus-within:outline-none" @keydown="handleKeydown">
		<div class="mb-4">
			<OptionToggle
				v-model="searchMode"
				:options="[
					{ label: 'Search', value: 'search', 'icon-left': 'search' },
					{ label: 'Find & Replace', value: 'replace', 'icon-left': 'edit-3' },
				]"
			/>
		</div>

		<div class="mb-4 flex gap-2">
			<Input
				ref="searchInput"
				class="flex-1"
				type="text"
				:placeholder="searchMode === 'replace' ? 'Find...' : 'Search blocks...'"
				v-model="query"
				@input="setQuery"
				@keydown.enter="handlePrimaryAction"
				id="searchInput"
			/>

			<Popover class="relative inline-block text-left">
				<template #target="{ isOpen, togglePopover }">
					<Button
						@click="togglePopover"
						variant="outline"
						icon="lucide-filter"
						label="Filters"
						:class="[
							'flex items-center gap-2 text-sm',
							selectedFiltersCount > 0 ? 'border-ink-gray-6 bg-ink-gray-1' : '',
						]"
					>
						<span
							v-if="selectedFiltersCount > 0"
							class="bg-ink-gray-7 ml-1 rounded-full px-2 py-0.5 text-xs text-ink-base"
						>
							{{ selectedFiltersCount }}
						</span>
						<FeatherIcon :name="isOpen ? 'chevron-up' : 'chevron-down'" class="size-4" />
					</Button>
				</template>
				<template #body>
					<div class="w-48 rounded-lg bg-surface-base py-2 shadow-lg ring-1 ring-black ring-opacity-5">
						<div class="text-xs-medium px-3 py-2 text-ink-gray-5">Filter search results by:</div>
						<div class="space-y-1 px-2">
							<label
								v-for="filter in filters"
								:key="filter.name"
								class="flex cursor-pointer items-center rounded px-2 py-1.5 text-sm text-ink-gray-8 hover:bg-surface-gray-1"
							>
								<Input
									type="checkbox"
									:checked="filter.selected"
									@change="toggleFilter(filter)"
									class="focus:ring-ink-gray-5 mr-3 size-4 rounded border-outline-gray-1 text-ink-gray-7"
								/>
								<span>{{ filter.name }}</span>
							</label>
						</div>
						<div class="border-surface-gray-3 mt-1 border-t px-2 pt-2">
							<Button @click="clearAllFilters" variant="subtle" class="w-full">Clear all filters</Button>
						</div>
					</div>
				</template>
			</Popover>
		</div>

		<div v-if="canvasStore.activeCanvas?.selectedBlocks?.length" class="mb-4">
			<label class="flex cursor-pointer items-center text-sm text-ink-gray-7">
				<Input
					type="checkbox"
					v-model="searchInSelectedBlock"
					@change="performSearch"
					label="Search inside selected block only"
					class="focus:ring-ink-gray-5 border-outline-gray-1 text-ink-gray-7"
				></Input>
			</label>
		</div>

		<div v-if="searchMode === 'replace'" class="mb-4">
			<Input
				class="w-full"
				type="text"
				placeholder="Replace with..."
				v-model="replaceQuery"
				@keydown.enter="handlePrimaryAction"
			/>
		</div>

		<div
			v-if="query && (searchMode === 'search' || (searchMode === 'replace' && results.length > 0))"
			class="mb-4"
		>
			<Button
				v-if="searchMode === 'replace'"
				@click="handlePrimaryAction"
				variant="solid"
				class="w-full"
				:disabled="!replaceQuery"
			>
				Replace All ({{ results.length }} matches)
			</Button>
			<div v-if="searchMode === 'replace' && replacedCount > 0" class="mt-2 text-xs text-ink-gray-5">
				{{ replacedCount }} replacements made
			</div>
		</div>

		<div v-if="!query" class="mt-6 text-center">
			<div class="flex flex-col items-center justify-center py-8">
				<div class="mb-4 flex size-16 items-center justify-center rounded-full bg-surface-gray-2">
					<FeatherIcon name="search" class="size-8 text-ink-gray-4" />
				</div>
				<h3 class="text-sm-medium mb-2 text-ink-gray-6">Search your blocks</h3>
			</div>
		</div>

		<div v-else-if="results.length > 0" class="max-h-64 overflow-y-auto">
			<!-- Search Results -->
			<div v-for="(result, index) in results" :key="result.componentId">
				<div
					class="mb-2 flex cursor-pointer items-center justify-between rounded px-3 py-2 text-sm text-ink-gray-7 hover:bg-surface-gray-1"
					@mouseover.stop="canvasStore.activeCanvas?.setHoveredBlock(result.componentId)"
					@click="canvasStore.activeCanvas?.scrollBlockIntoView(result)"
				>
					<div class="line-clamp-2 flex-1">
						{{ result.getBlockDescription() }}
						<div class="mt-1 text-xs text-ink-gray-5">
							{{ getMatchDetails(result) }}
						</div>
					</div>
					<Button
						v-if="searchMode === 'replace'"
						@click.stop="replaceInBlock(result, index)"
						variant="subtle"
						class="ml-3 px-2 py-1 text-xs"
						:disabled="!replaceQuery"
					>
						Replace
					</Button>
				</div>
			</div>
		</div>

		<div v-else-if="query && results.length === 0" class="mt-6 text-center">
			<!-- No Results State -->
			<div class="flex flex-col items-center justify-center py-6">
				<FeatherIcon name="search" class="mb-3 size-6 text-ink-gray-4" />
				<h3 class="text-sm-medium mb-1 text-ink-gray-6">No results found</h3>
				<p class="text-xs text-ink-gray-5">Try different keywords or adjust your filters</p>
			</div>
		</div>
	</div>
</template>
<script setup lang="ts">
import type Block from "@/utils/block"
import useCanvasStore from "@/stores/canvasStore"
import { watchDebounced } from "@vueuse/core"
import { FeatherIcon, Popover, Input, Button } from "frappe-ui"
import { computed, nextTick, onMounted, Ref, ref } from "vue"
import { toast } from "frappe-ui"
import OptionToggle from "@/components/OptionToggle.vue"
import { jsToJson } from "@/utils/serializer"

const canvasStore = useCanvasStore()

const searchBlock = ref(null) as Ref<HTMLInputElement | null>
const searchInput = ref(null) as Ref<HTMLInputElement | null>
const query = ref("")
const replaceQuery = ref("")
const searchMode = ref<"search" | "replace">("search")
const replacedCount = ref(0)
const results = ref([]) as Ref<Block[]>
const searchInSelectedBlock = ref(false)

const propertyHandlers = [
	{
		key: "component",
		name: "Component",
		matches: (block: Block, term: string) =>
			[block.componentName, block.blockName].some((name) => name?.toLowerCase().includes(term)),
		replace: () => false,
	},
	{
		key: "componentProps",
		name: "Props",
		matches: (block: Block, term: string) => {
			try {
				const propsJson = jsToJson(block.componentProps)
				return propsJson.toLowerCase().includes(term)
			} catch {
				return false
			}
		},
		replace: (block: Block, searchTerm: string, replaceTerm: string) => {
			let replaced = false
			replaced = replaceInProperty(block.componentProps, searchTerm, replaceTerm) || replaced
			return replaced
		},
	},
	{
		key: "componentEvents",
		name: "Events",
		matches: (block: Block, term: string) => {
			try {
				const eventsJson = jsToJson(block.componentEvents)
				return eventsJson.toLowerCase().includes(term)
			} catch {
				return false
			}
		},
		replace: () => false,
	},
	{
		key: "attributes",
		name: "Attributes",
		matches: (block: Block, term: string) => {
			return Object.entries(block.getAttributes()).some((val) => String(val).toLowerCase().includes(term))
		},
		replace: (block: Block, searchTerm: string, replaceTerm: string) => {
			let replaced = false
			replaced = replaceInProperty(block.attributes, searchTerm, replaceTerm) || replaced
			return replaced
		},
	},
	{
		key: "styles",
		name: "Style",
		matches: (block: Block, term: string) => {
			const styles = { ...block.baseStyles, ...block.mobileStyles, ...block.tabletStyles }
			return Object.values(styles).some((val) => String(val).toLowerCase().includes(term))
		},
		replace: (block: Block, searchTerm: string, replaceTerm: string) => {
			let replaced = false
			replaced = replaceInProperty(block.baseStyles, searchTerm, replaceTerm) || replaced
			replaced = replaceInProperty(block.mobileStyles, searchTerm, replaceTerm) || replaced
			replaced = replaceInProperty(block.tabletStyles, searchTerm, replaceTerm) || replaced
			return replaced
		},
	},
	{
		key: "classes",
		name: "CSS Classes",
		matches: (block: Block, term: string) => {
			return block.classes?.some((c) => c.toLowerCase().includes(term))
		},
		replace: (block: Block, searchTerm: string, replaceTerm: string) => {
			if (!block.classes) return false
			let hasReplacement = false
			const regex = new RegExp(escapeRegExp(searchTerm), "gi")
			block.classes = block.classes.map((c) => {
				if (regex.test(c)) {
					hasReplacement = true
					return c.replace(regex, replaceTerm)
				}
				return c
			})
			return hasReplacement
		},
	},
]

const filters = ref(
	propertyHandlers.map((h) => ({
		name: h.name,
		selected: false,
		key: h.key,
	})),
)

const selectedFiltersCount = computed(() => {
	return filters.value.filter((f) => f.selected).length
})

const setQuery = (value: string) => {
	query.value = value
	replacedCount.value = 0
}

const handlePrimaryAction = () => {
	if (searchMode.value === "search") {
		performSearch()
	} else if (searchMode.value === "replace" && results.value.length > 0) {
		replaceAll()
	}
}

const handleKeydown = (event: KeyboardEvent) => {
	// Cmd+F or Ctrl+F for quick search
	if ((event.metaKey || event.ctrlKey) && event.key === "f") {
		event.preventDefault()
		const input = searchInput.value?.querySelector?.("input") || searchInput.value
		if (input && "focus" in input && typeof input.focus === "function") {
			input.focus()
		}
	}
	// Escape to clear search
	if (event.key === "Escape") {
		query.value = ""
		replaceQuery.value = ""
	}
}

const toggleFilter = (filter: any) => {
	filter.selected = !filter.selected
	performSearch()
}

const clearAllFilters = () => {
	filters.value.forEach((filter) => {
		filter.selected = false
	})
	performSearch()
}

const getMatchDetails = (block: Block) => {
	if (!query.value) return ""

	const lowerSearchTerm = query.value.toLowerCase()
	const details = propertyHandlers.filter((h) => h.matches(block, lowerSearchTerm)).map((h) => h.name)

	return details.length > 0 ? `Found in: ${details.join(", ")}` : ""
}

const replaceInProperty = (obj: any, searchTerm: string, replaceTerm: string): boolean => {
	let hasReplacement = false

	if (typeof obj === "string") {
		return obj.toLowerCase().includes(searchTerm.toLowerCase())
	}

	if (typeof obj === "object" && obj !== null) {
		for (const key in obj) {
			if (typeof obj[key] === "string") {
				const regex = new RegExp(escapeRegExp(searchTerm), "gi")
				if (regex.test(obj[key])) {
					obj[key] = obj[key].replace(regex, replaceTerm)
					hasReplacement = true
				}
			} else if (typeof obj[key] === "object") {
				hasReplacement = replaceInProperty(obj[key], searchTerm, replaceTerm) || hasReplacement
			}
		}
	}

	return hasReplacement
}

const escapeRegExp = (string: string) => {
	return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
}

const replaceInBlock = (block: Block, index: number) => {
	if (!replaceQuery.value || !query.value) return

	let hasReplacement = false
	const searchTerm = query.value
	const replaceTerm = replaceQuery.value
	const activeFilterKeys = filters.value.filter((f) => f.selected).map((f) => f.key)
	const replacers =
		activeFilterKeys.length > 0
			? propertyHandlers.filter((h) => activeFilterKeys.includes(h.key))
			: propertyHandlers

	for (const replacer of replacers) {
		if (replacer.replace(block, searchTerm, replaceTerm)) {
			hasReplacement = true
		}
	}

	if (hasReplacement) {
		replacedCount.value++
		results.value.splice(index, 1)
		toast.success(`Replaced in ${block.getBlockDescription()}`)
	} else {
		toast.error("No replacements made")
	}
}

const replaceAll = () => {
	if (!replaceQuery.value || !query.value) return

	let totalReplacements = 0
	const blocksToReplace = [...results.value]

	blocksToReplace.forEach((block, index) => {
		const originalCount = replacedCount.value
		replaceInBlock(block, 0) // Always use index 0 since we're working with a copy
		if (replacedCount.value > originalCount) {
			totalReplacements++
		}
	})

	if (totalReplacements > 0) {
		toast.success(`Made ${totalReplacements} replacements across ${totalReplacements} blocks`)
		performSearch()
	} else {
		toast.error("No replacements made")
	}
}

const performSearch = () => {
	results.value = []
	if (query.value) {
		const filteredBlocks = searchWithFilters(query.value)
		if (filteredBlocks?.length) {
			results.value = filteredBlocks
		}
	}
}

const searchWithFilters = (searchTerm: string): Block[] => {
	const searchResults: Block[] = []
	const limit = 50
	const lowerSearchTerm = searchTerm.toLowerCase()

	const activeFilterKeys = filters.value.filter((f) => f.selected).map((f) => f.key)

	const searchers =
		activeFilterKeys.length > 0
			? propertyHandlers.filter((h) => activeFilterKeys.includes(h.key))
			: propertyHandlers

	function searchInBlock(block: Block) {
		if (searchResults.length >= limit) return
		const matches = searchers.some((s) => s.matches(block, lowerSearchTerm))
		if (matches) {
			searchResults.push(block)
		}
		block.children?.forEach((child) => searchInBlock(child))

		if (block.componentSlots) {
			Object.values(block.componentSlots).forEach((slot) => {
				if (Array.isArray(slot.slotContent)) {
					slot.slotContent.forEach((child) => searchInBlock(child))
				}
			})
		}
	}

	const selectedBlocks = canvasStore.activeCanvas?.selectedBlocks
	const startingBlock =
		searchInSelectedBlock.value && selectedBlocks?.length
			? selectedBlocks[0]
			: canvasStore.activeCanvas?.getRootBlock()

	if (startingBlock) {
		searchInBlock(startingBlock)
	}

	return searchResults
}

onMounted(async () => {
	await nextTick()
	const searchElement = document.querySelector("#searchInput")
	if (searchElement && "focus" in searchElement && typeof searchElement.focus === "function") {
		searchElement.focus()
	}
})

watchDebounced(query, performSearch, {
	debounce: 300,
})

watchDebounced(() => filters.value.map((f) => f.selected).join(","), performSearch, {
	debounce: 300,
})

watchDebounced(searchInSelectedBlock, performSearch, {
	debounce: 300,
})

// Reset replaced count when switching modes
watchDebounced(
	searchMode,
	() => {
		replacedCount.value = 0
	},
	{ debounce: 100 },
)
</script>
