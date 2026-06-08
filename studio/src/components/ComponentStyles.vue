<template>
	<div v-if="blockController.isAnyBlockSelected()" class="flex select-none flex-col pb-16">
		<div class="flex flex-col gap-3">
			<CollapsibleSection
				:sectionName="section.name"
				v-for="section in filteredSections"
				:sectionCollapsed="section.collapsed"
			>
				<template v-for="property in getFilteredProperties(section)">
					<div v-if="property.allowDynamicValue" class="flex items-center">
						<DynamicStyleSelector
							:block="block"
							:property="property"
							@update:modelValue="
								(event) => {
									if (typeof property.events?.['update:modelValue'] === 'function') {
										property.events['update:modelValue'](event)
									} else if (typeof property.events?.['change'] === 'function') {
										property.events['change'](event)
									} else {
										// for DimensionInput
										const _property = property.getProps().property as keyof CSSProperties
										blockController.setStyle(_property, event)
									}
								}
							"
						/>
						<component
							class="flex-1"
							:is="property.component"
							v-bind="property.getProps()"
							v-on="property.events || {}"
						>
							{{ property.innerText || "" }}
						</component>
					</div>

					<component
						v-else
						:is="property.component"
						v-bind="property.getProps()"
						v-on="property.events || {}"
					>
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
import Block from "@/utils/block"
import OptionToggle from "@/components/OptionToggle.vue"
import useStudioStore from "@/stores/studioStore"
import blockController from "@/utils/blockController"
import { getEspressoTokens } from "@/utils/espressoTokens"
import { CSSProperties, computed } from "vue"

import BlockFlexLayoutHandler from "@/components/BlockFlexLayoutHandler.vue"
import BlockGridLayoutHandler from "@/components/BlockGridLayoutHandler.vue"
import BlockPositionHandler from "@/components/BlockPositionHandler.vue"
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import DimensionInput from "@/components/DimensionInput.vue"
import InlineInput from "@/components/InlineInput.vue"
import EmptyState from "@/components/EmptyState.vue"
import ColorInput from "@/components/ColorInput.vue"
import ObjectEditor from "@/components/ObjectEditor.vue"

import type { StyleValue } from "@/types"
import DynamicStyleSelector from "@/components/DynamicStyleSetter.vue"

const props = defineProps({
	block: {
		type: Block,
		required: false,
	},
})

const store = useStudioStore()

export type BlockProperty = {
	component: any
	getProps: () => Record<string, unknown>
	events?: Record<string, unknown>
	searchKeyWords: string
	condition?: () => boolean
	innerText?: string
	allowDynamicValue?: boolean
	getValue?: () => string | null
}

type PropertySection = {
	name: string
	properties: BlockProperty[]
	condition?: () => boolean
	collapsed?: boolean
}

const filteredSections = computed(() => {
	return sections.filter((section) => {
		let showSection = true
		if (section.condition) {
			showSection = section.condition()
		}
		if (showSection && store.propertyFilter) {
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
		if (showProperty && store.propertyFilter) {
			showProperty =
				section.name.toLowerCase().includes(store.propertyFilter.toLowerCase()) ||
				property.searchKeyWords.toLowerCase().includes(store.propertyFilter.toLowerCase())
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
				modelValue: blockController.getStyle("display"),
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
				options: ["unset", "auto", "visible", "hidden", "scroll"],
				modelValue: blockController.getStyle("overflowX") ?? blockController.getStyle("overflow") ?? "",
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
				options: ["unset", "auto", "visible", "hidden", "scroll"],
				modelValue: blockController.getStyle("overflowY") ?? blockController.getStyle("overflow") ?? "",
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
		allowDynamicValue: true,
		getValue: () => {
			return blockController.getStyle("width")
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
		allowDynamicValue: true,
		getValue: () => {
			return blockController.getStyle("minWidth")
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
		allowDynamicValue: true,
		getValue: () => {
			return blockController.getStyle("maxWidth")
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
		allowDynamicValue: true,
		getValue: () => {
			return blockController.getStyle("height")
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
		allowDynamicValue: true,
		getValue: () => {
			return blockController.getStyle("minHeight")
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
		allowDynamicValue: true,
		getValue: () => {
			return blockController.getStyle("maxHeight")
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

const isSingleValue = (value: StyleValue): boolean => {
	if (!value) return false
	return value.toString().trim().split(/\s+/).length === 1
}

const spacingSectionProperties = [
	{
		component: InlineInput,
		searchKeyWords: "Margin, Top, MarginTop, Margin Top",
		getProps: () => {
			const value = blockController.getMargin()
			return {
				label: "Margin",
				modelValue: value,
				enableSlider: isSingleValue(value),
				unitOptions: ["px", "%", "em", "rem"],
			}
		},
		events: {
			"update:modelValue": (val: string) => blockController.setMargin(val),
		},
		condition: () => !blockController.isRoot(),
		allowDynamicValue: true,
		getValue: () => {
			return blockController.getMargin()
		},
	},
	{
		component: InlineInput,
		searchKeyWords: "Padding, Top, PaddingTop, Padding Top",
		getProps: () => {
			const value = blockController.getPadding()
			return {
				label: "Padding",
				modelValue: value,
				enableSlider: isSingleValue(value),
				unitOptions: ["px", "%", "em", "rem"],
			}
		},
		events: {
			"update:modelValue": (val: string) => blockController.setPadding(val),
		},
		allowDynamicValue: true,
		getValue: () => {
			return blockController.getPadding()
		},
	},
]

const typographySectionProperties = [
	{
		component: InlineInput,
		getProps: () => {
			return {
				label: "Weight",
				styleProperty: "fontWeight",
				type: "autocomplete",
				options: getEspressoTokens("fontWeight"),
				modelValue: blockController.getStyle("fontWeight"),
			}
		},
		events: {
			"update:modelValue": (val: StyleValue) => blockController.setStyle("fontWeight", val),
		},
		searchKeyWords: "Font, Weight, FontWeight",
		allowDynamicValue: true,
	},
	{
		component: InlineInput,
		getProps: () => {
			return {
				label: "Size",
				type: "autocomplete",
				options: getEspressoTokens("fontSize"),
				modelValue: blockController.getProp("fontSize") || blockController.getStyle("fontSize"),
			}
		},
		events: {
			"update:modelValue": (val: string) => {
				if (val?.startsWith("text-")) {
					blockController.setProp("fontSize", val)
					blockController.setStyle("fontSize", "unset")
				} else {
					blockController.setStyle("fontSize", val)
					blockController.setProp("fontSize", "")
				}
			},
		},
		searchKeyWords: "Font, Size, FontSize",
		condition: () => blockController.isText(),
		allowDynamicValue: true,
	},
	{
		component: InlineInput,
		getProps: () => {
			return {
				label: "Height",
				type: "autocomplete",
				options: getEspressoTokens("lineHeight"),
				modelValue: blockController.getStyle("lineHeight"),
			}
		},
		events: {
			"update:modelValue": (val: StyleValue) => blockController.setStyle("lineHeight", val),
		},
		searchKeyWords: "Font, Height, LineHeight, Line Height",
		condition: () => blockController.isText(),
		allowDynamicValue: true,
	},
	{
		component: ColorInput,
		getProps: () => {
			return {
				label: "Color",
				modelValue: blockController.getStyle("color"),
				property: "textColor",
			}
		},
		events: {
			"update:modelValue": (val: StyleValue) => blockController.setStyle("color", val),
		},
		allowDynamicValue: true,
		searchKeyWords: "Text, Color, TextColor, Text Color",
	},
	{
		component: InlineInput,
		getProps: () => {
			return {
				label: "Letter",
				type: "autocomplete",
				options: getEspressoTokens("letterSpacing"),
				modelValue: blockController.getStyle("letterSpacing"),
			}
		},
		events: {
			"update:modelValue": (val: StyleValue) => blockController.setStyle("letterSpacing", val),
		},
		searchKeyWords: "Font, Letter, LetterSpacing, Letter Spacing",
		condition: () => blockController.isText(),
		allowDynamicValue: true,
	},
	{
		component: InlineInput,
		getProps: () => {
			return {
				label: "Transform",
				type: "select",
				options: [
					{
						value: null,
						label: "None",
					},
					{
						value: "uppercase",
						label: "Uppercase",
					},
					{
						value: "lowercase",
						label: "Lowercase",
					},
					{
						value: "capitalize",
						label: "Capitalize",
					},
				],
				modelValue: blockController.getStyle("textTransform"),
			}
		},
		events: {
			"update:modelValue": (val: StyleValue) => blockController.setStyle("textTransform", val),
		},
		searchKeyWords: "Font, Transform, TextTransform, Text Transform, Capitalize, Uppercase, Lowercase",
		condition: () => blockController.isText(),
		allowDynamicValue: true,
	},
	{
		component: OptionToggle,
		getProps: () => {
			return {
				label: "Align",
				styleProperty: "textAlign",
				options: [
					{
						label: "Left",
						value: "left",
						icon: "lucide-align-left",
						hideLabel: true,
					},
					{
						label: "Center",
						value: "center",
						icon: "lucide-align-center",
						hideLabel: true,
					},
					{
						label: "Right",
						value: "right",
						icon: "lucide-align-right",
						hideLabel: true,
					},
				],
				defaultValue: "left",
				modelValue: blockController.getStyle("textAlign"),
			}
		},
		events: {
			"update:modelValue": (val: StyleValue) => blockController.setStyle("textAlign", val),
		},
		searchKeyWords: "Font, Align, TextAlign, Text Align, Left, Center, Right, Justify",
		condition: () => blockController.isText(),
		allowDynamicValue: true,
	},
]

const styleSectionProperties = [
	{
		component: ColorInput,
		getProps: () => {
			return {
				label: "BG Color",
				modelValue: blockController.getStyle("backgroundColor"),
				property: "backgroundColor",
			}
		},
		searchKeyWords: "Background, BackgroundColor, Background Color, BG, BGColor, BG Color",
		events: {
			"update:modelValue": (val: StyleValue) => blockController.setStyle("backgroundColor", val),
		},
		allowDynamicValue: true,
		getValue: () => {
			return blockController.getStyle("backgroundColor")
		},
	},
	{
		component: ColorInput,
		getProps: () => {
			return {
				label: "Text Color",
				modelValue: blockController.getStyle("color"),
				property: "textColor",
			}
		},
		events: {
			"update:modelValue": (val: StyleValue) => blockController.setStyle("color", val),
		},
		allowDynamicValue: true,
		searchKeyWords: "Text, Color, TextColor, Text Color",
	},
	{
		component: ColorInput,
		getProps: () => {
			return {
				label: "Border Color",
				modelValue: blockController.getStyle("borderColor"),
				property: "borderColor",
			}
		},
		searchKeyWords: "Border, Color, BorderColor, Border Color",
		events: {
			"update:modelValue": (val: StyleValue) => {
				blockController.setStyle("borderColor", val)
				if (val) {
					if (!blockController.getStyle("borderWidth")) {
						blockController.setStyle("borderWidth", "1px")
						blockController.setStyle("borderStyle", "solid")
					}
				} else {
					blockController.setStyle("borderWidth", null)
					blockController.setStyle("borderStyle", null)
				}
			},
		},
		allowDynamicValue: true,
		getValue: () => {
			return blockController.getStyle("borderColor")
		},
	},
	{
		component: InlineInput,
		getProps: () => {
			return {
				label: "Border Width",
				modelValue: blockController.getStyle("borderWidth"),
				enableSlider: true,
				unitOptions: ["px", "%", "em", "rem"],
				minValue: 0,
			}
		},
		searchKeyWords: "Border, Width, BorderWidth, Border Width",
		events: {
			"update:modelValue": (val: StyleValue) => blockController.setStyle("borderWidth", val),
		},
		condition: () => blockController.getStyle("borderColor") || blockController.getStyle("borderWidth"),
		allowDynamicValue: true,
		getValue: () => {
			return blockController.getStyle("borderWidth")
		},
	},
	{
		component: InlineInput,
		getProps: () => {
			return {
				label: "Border Style",
				modelValue: blockController.getStyle("borderStyle"),
				type: "select",
				options: [
					{
						value: "solid",
						label: "Solid",
					},
					{
						value: "dashed",
						label: "Dashed",
					},
					{
						value: "dotted",
						label: "Dotted",
					},
				],
			}
		},
		searchKeyWords: "Border, Style, BorderStyle, Border Style, Solid, Dashed, Dotted",
		events: {
			"update:modelValue": (val: StyleValue) => blockController.setStyle("borderStyle", val),
		},
		condition: () => blockController.getStyle("borderColor"),
		allowDynamicValue: true,
		getValue: () => {
			return blockController.getStyle("borderStyle")
		},
	},
	{
		component: InlineInput,
		getProps: () => {
			return {
				type: "autocomplete",
				label: "Radius",
				modelValue: blockController.getStyle("borderRadius"),
				enableSlider: true,
				unitOptions: ["px", "%"],
				options: getEspressoTokens("borderRadius"),
				minValue: 0,
			}
		},
		searchKeyWords: "Border, Radius, BorderRadius, Border Radius",
		events: {
			"update:modelValue": (val: StyleValue) => blockController.setStyle("borderRadius", val),
		},
		allowDynamicValue: true,
		getValue: () => {
			return blockController.getStyle("borderRadius")
		},
	},
	{
		component: InlineInput,
		getProps: () => {
			return {
				label: "Z-Index",
				modelValue: blockController.getStyle("zIndex"),
			}
		},
		searchKeyWords: "Z, Index, ZIndex, Z Index, Z-index, Z-Index",
		events: {
			"update:modelValue": (val: StyleValue) => blockController.setStyle("zIndex", val),
		},
		condition: () =>
			!blockController.multipleBlocksSelected() &&
			!blockController.isRoot() &&
			blockController.getStyle("position") !== "static",
		allowDynamicValue: true,
		getValue: () => {
			return blockController.getStyle("zIndex")
		},
	},
	{
		component: InlineInput,
		getProps: () => {
			return {
				label: "Shadow",
				type: "select",
				options: getEspressoTokens("boxShadow"),
				modelValue: blockController.getStyle("boxShadow"),
			}
		},
		searchKeyWords: "Shadow, BoxShadow, Box Shadow",
		events: {
			"update:modelValue": (val: StyleValue) => blockController.setStyle("boxShadow", val),
		},
	},
	{
		component: InlineInput,
		getProps: () => {
			return {
				label: "Cursor",
				type: "select",
				options: [
					{ value: null, label: "Default" },
					{ value: "pointer", label: "Pointer" },
					{ value: "move", label: "Move" },
					{ value: "text", label: "Text" },
					{ value: "crosshair", label: "Crosshair" },
					{ value: "not-allowed", label: "Not Allowed" },
				],
				modelValue: blockController.getStyle("cursor"),
			}
		},
		searchKeyWords: "Cursor, Pointer, Move, Text, Crosshair, NotAllowed, Not Allowed",
		events: {
			"update:modelValue": (val: StyleValue) => blockController.setStyle("cursor", val),
		},
	},
]

const rawStyleSectionProperties = [
	{
		component: ObjectEditor,
		getProps: () => {
			return {
				obj: blockController.getRawStyles() as Record<string, string>,
				description: `
					<b>Note:</b>
					<br />
					<br />
					- Raw styles get applied across all devices
					<br />
				`,
			}
		},
		searchKeyWords: "Raw, RawStyle, Raw Style, CSS, Style, Styles",
		events: {
			"update:obj": (obj: Record<string, string>) => blockController.setRawStyles(obj),
		},
	},
]

const setClasses = (val: string) => {
	const classes = val.split(",").map((c) => c.trim())
	blockController.setClasses(classes)
}

const classesSectionProperties = [
	{
		component: InlineInput,
		getProps: () => {
			return {
				type: "textarea",
				label: "Tailwind Classes",
				modelValue: blockController.getClasses().join(", "),
			}
		},
		searchKeyWords: "Class, ClassName, Class Name",
		events: {
			"update:modelValue": (val: string) => setClasses(val || ""),
		},
		condition: () => !blockController.multipleBlocksSelected(),
	},
]

const sections = [
	{
		name: "Layout",
		properties: layoutSectionProperties,
		condition: () => !blockController.multipleBlocksSelected(),
		collapsed: computed(() => blockController.isText()),
	},
	{
		name: "Typography",
		properties: typographySectionProperties,
		condition: () => blockController.isText(),
	},
	{
		name: "Dimension",
		properties: dimensionSectionProperties,
	},
	{
		name: "Position",
		properties: positionSectionProperties,
		condition: () => !blockController.multipleBlocksSelected() && !blockController.isRoot(),
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
	},
	{
		name: "Style",
		properties: styleSectionProperties,
	},
	{
		name: "Raw Style",
		properties: rawStyleSectionProperties,
		collapsed: computed(() => {
			return Object.keys(blockController.getRawStyles()).length === 0
		}),
	},
	{
		name: "Classes",
		properties: classesSectionProperties,
		collapsed: computed(() => {
			return blockController.getClasses().length === 0
		}),
	},
] as PropertySection[]
</script>
