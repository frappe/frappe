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
					(e: Event) => {
						store.stylePropertyFilter = (e.target as HTMLInputElement).value
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
		<EmptyState message="Select a block to edit styles" />
	</div>
</template>

<script setup lang="ts">
import { TextInput } from "frappe-ui"
import Block from "@/utils/block"
import OptionToggle from "@/components/OptionToggle.vue"
import useStudioStore from "@/stores/studioStore"
import blockController from "@/utils/blockController"
import { Ref, computed, ref } from "vue"
import BlockFlexLayoutHandler from "@/components/BlockFlexLayoutHandler.vue"
import BlockGridLayoutHandler from "@/components/BlockGridLayoutHandler.vue"
import BlockPositionHandler from "@/components/BlockPositionHandler.vue"
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import DimensionInput from "@/components/DimensionInput.vue"
import InlineInput from "@/components/InlineInput.vue"
import EmptyState from "@/components/EmptyState.vue"

import { StyleValue } from "@/types"

const props = defineProps({
	block: {
		type: Block,
		required: false,
	},
})

const store = useStudioStore()

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
		component: BlockGridLayoutHandler,
		getProps: () => {},
		searchKeyWords:
			"Layout, Grid, GridTemplate, Grid Template, GridGap, Grid Gap, GridRow, Grid Row, GridColumn, Grid Column",
	},
	{
		component: BlockFlexLayoutHandler,
		getProps: () => {},
		searchKeyWords:
			"Layout, Flex, Flexbox, Flex Box, FlexBox, Justify, Space Between, Flex Grow, Flex Shrink, Flex Basis, Align Items, Align Content, Align Self, Flex Direction, Flex Wrap, Flex Flow, Flex Grow, Flex Shrink, Flex Basis, Gap",
	},
	{
		component: InlineInput,
		getProps: () => {
			return {
				label: "Overflow X",
				type: "select",
				options: ["auto", "visible", "hidden", "scroll"],
				modelValue: blockController.getStyle("overflowX") || blockController.getStyle("overflow"),
			}
		},
		searchKeyWords:
			"Overflow, X, OverflowX, Overflow X, Auto, Visible, Hide, Scroll, horizontal scroll, horizontalScroll",
		events: {
			"update:modelValue": (val: StyleValue) => blockController.setStyle("overflowX", val),
		},
	},
	{
		component: InlineInput,
		getProps: () => {
			return {
				label: "Overflow Y",
				type: "select",
				options: ["auto", "visible", "hidden", "scroll"],
				modelValue: blockController.getStyle("overflowY") || blockController.getStyle("overflow"),
			}
		},
		searchKeyWords:
			"Overflow, Y, OverflowY, Overflow Y, Auto, Visible, Hide, Scroll, vertical scroll, verticalScroll",
		events: {
			"update:modelValue": (val: StyleValue) => blockController.setStyle("overflowY", val),
		},
	},
]

const dimensionSectionProperties = [
	{
		component: DimensionInput,
		searchKeyWords: "Width",
		getProps: () => {
			return {
				label: "Width",
				property: "width",
			}
		},
	},
	{
		component: DimensionInput,
		searchKeyWords: "Min, Width, MinWidth, Min Width",
		getProps: () => {
			return {
				label: "Min Width",
				property: "minWidth",
			}
		},
	},
	{
		component: DimensionInput,
		searchKeyWords: "Max, Width, MaxWidth, Max Width",
		getProps: () => {
			return {
				label: "Max Width",
				property: "maxWidth",
			}
		},
	},
	{
		component: "hr",
		getProps: () => {
			return {
				class: "dark:border-zinc-700",
			}
		},
		searchKeyWords: "",
	},
	{
		component: DimensionInput,
		searchKeyWords: "Height",
		getProps: () => {
			return {
				label: "Height",
				property: "height",
			}
		},
	},
	{
		component: DimensionInput,
		searchKeyWords: "Min, Height, MinHeight, Min Height",
		getProps: () => {
			return {
				label: "Min Height",
				property: "minHeight",
			}
		},
	},
	{
		component: DimensionInput,
		searchKeyWords: "Max, Height, MaxHeight, Max Height",
		getProps: () => {
			return {
				label: "Max Height",
				property: "maxHeight",
			}
		},
	},
]

const positionSectionProperties = [
	{
		component: BlockPositionHandler,
		searchKeyWords:
			"Position, Top, Right, Bottom, Left, PositionTop, Position Top, PositionRight, Position Right, PositionBottom, Position Bottom, PositionLeft, Position Left, Free, Fixed, Absolute, Relative, Sticky",
		getProps: () => {},
	},
]

const spacingSectionProperties = [
	{
		component: InlineInput,
		searchKeyWords: "Margin, Top, MarginTop, Margin Top",
		getProps: () => {
			return {
				label: "Margin",
				modelValue: blockController.getMargin(),
			}
		},
		events: {
			"update:modelValue": (val: string) => blockController.setMargin(val),
		},
		condition: () => !blockController.isRoot(),
	},
	{
		component: InlineInput,
		searchKeyWords: "Padding, Top, PaddingTop, Padding Top",
		getProps: () => {
			return {
				label: "Padding",
				modelValue: blockController.getPadding(),
			}
		},
		events: {
			"update:modelValue": (val: string) => blockController.setPadding(val),
		},
	},
]

const sections = [
	{
		name: "Layout",
		properties: layoutSectionProperties,
		condition: () => !blockController.multipleBlocksSelected(),
	},
	{
		name: "Dimension",
		properties: dimensionSectionProperties,
	},
	{
		name: "Position",
		properties: positionSectionProperties,
		condition: () => !blockController.multipleBlocksSelected(),
		collapsed: computed(() => {
			return (
				!blockController.getStyle("top") &&
				!blockController.getStyle("right") &&
				!blockController.getStyle("bottom") &&
				!blockController.getStyle("left")
			)
		}),
	},
	{
		name: "Spacing",
		properties: spacingSectionProperties,
		collapsed: computed(
			() =>
				!blockController.getStyle("marginTop") &&
				!blockController.getStyle("paddingTop") &&
				!blockController.getStyle("marginBottom") &&
				!blockController.getStyle("paddingBottom"),
		),
	},
] as PropertySection[]
</script>
