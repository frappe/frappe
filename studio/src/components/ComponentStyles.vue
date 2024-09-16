<template>
	<div v-if="blockController.isAnyBlockSelected()" class="flex select-none flex-col pb-16">
		<div class="sticky top-[41px] z-50 mt-[-15px] flex w-full bg-white py-3">
			<TextInput
				ref="searchInput"
				type="text"
				class="w-full"
				size="sm"
				variant="outline"
				placeholder="Search properties"
				v-model="store.stylePropertyFilter"
				@input="
					(e) => {
						store.stylePropertyFilter = e.target.value
					}
				"
			/>
		</div>
		<div class="flex flex-col gap-3">
			<CollapsibleSection
				:sectionName="section.name"
				v-for="section in filteredSections"
				:sectionCollapsed="section.collapsed"
			>
				<template v-for="property in getFilteredProperties(section)">
					<component :is="property.component" v-bind="property.getProps()" v-on="property.events || {}">
						{{ property.innerText || "" }}
					</component>
				</template>
			</CollapsibleSection>
		</div>
	</div>
	<div v-else>
		<p class="dark:text-zinc-500 text-center text-sm text-gray-600">Select a block to edit properties.</p>
	</div>
</template>

<script setup lang="ts">
import { TextInput } from "frappe-ui"
import Block from "@/utils/block"
import OptionToggle from "@/components/OptionToggle.vue"
import useStore from "@/store"
import blockController from "@/utils/blockController"
import { Ref, computed, ref } from "vue"
import BlockFlexLayoutHandler from "@/components/BlockFlexLayoutHandler.vue"
import CollapsibleSection from "@/components/CollapsibleSection.vue"

const props = defineProps({
	block: {
		type: Block,
		required: false,
	},
})

const store = useStore()

// command + f should focus on search input
window.addEventListener("keydown", (e) => {
	if (e.key === "f" && (e.metaKey || e.ctrlKey)) {
		e.preventDefault()
		document.querySelector(".properties-search-input")?.querySelector("input")?.focus()
	}
})

type BlockProperty = {
	component: any
	getProps: () => Record<string, unknown>
	events?: Record<string, unknown>
	searchKeyWords: string
	condition?: () => boolean
	innerText?: string
}

type PropertySection = {
	name: string
	properties: BlockProperty[]
	condition?: () => boolean
	collapsed?: boolean
}

const searchInput = ref(null) as Ref<HTMLElement | null>

const filteredSections = computed(() => {
	return sections.filter((section) => {
		let showSection = true
		if (section.condition) {
			showSection = section.condition()
		}
		if (showSection && store.stylePropertyFilter) {
			showSection = getFilteredProperties(section).length > 0
		}
		return showSection
	})
})

const getFilteredProperties = (section: PropertySection) => {
	return section.properties.filter((property) => {
		let showProperty = true
		if (property.condition) {
			showProperty = property.condition()
		}
		if (showProperty && store.stylePropertyFilter) {
			showProperty =
				section.name.toLowerCase().includes(store.stylePropertyFilter.toLowerCase()) ||
				property.searchKeyWords.toLowerCase().includes(store.stylePropertyFilter.toLowerCase())
		}
		return showProperty
	})
}

const layoutSectionProperties = [
	{
		component: OptionToggle,
		getProps: () => {
			return {
				label: "Type",
				options: [
					{
						label: "Stack",
						value: "flex",
					},
					{
						label: "Grid",
						value: "grid",
					},
				],
				modelValue: blockController.getStyle("display") || "flex",
			}
		},
		searchKeyWords: "Layout, Display, Flex, Grid, Flexbox, Flex Box, FlexBox",
		events: {
			"update:modelValue": (val: StyleValue) => {
				blockController.setStyle("display", val)
				if (val === "grid") {
					if (!blockController.getStyle("gridTemplateColumns")) {
						blockController.setStyle("gridTemplateColumns", "repeat(2, minmax(200px, 1fr))")
					}
					if (!blockController.getStyle("gap")) {
						blockController.setStyle("gap", "10px")
					}
					if (blockController.getStyle("height")) {
						if (blockController.getSelectedBlocks()[0].hasChildren()) {
							blockController.setStyle("height", null)
						}
					}
				}
			},
		},
	},
	{
		component: BlockFlexLayoutHandler,
		getProps: () => {},
		searchKeyWords:
			"Layout, Flex, Flexbox, Flex Box, FlexBox, Justify, Space Between, Flex Grow, Flex Shrink, Flex Basis, Align Items, Align Content, Align Self, Flex Direction, Flex Wrap, Flex Flow, Flex Grow, Flex Shrink, Flex Basis, Gap",
	},
]

const sections = [
	{
		name: "Layout",
		properties: layoutSectionProperties,
		condition: () => !blockController.multipleBlocksSelected(),
	},
] as PropertySection[]
</script>
