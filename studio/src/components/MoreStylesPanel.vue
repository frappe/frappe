<template>
	<div class="flex flex-col gap-3" @paste="pasteStyles">
		<div
			v-for="row in propertyRows"
			:key="row.property"
			class="group flex items-center gap-1"
			:data-style-property="row.styleProperty"
		>
			<DynamicStyleSetter
				:block="selectedBlock ?? undefined"
				:property="row.dynamicValueProperty"
				@update:modelValue="(expression: string) => blockController.setStyle(row.styleProperty, expression)"
			/>
			<InlineInput
				class="min-w-0 flex-1"
				:label="row.label"
				v-bind="row.controlProps"
				:modelValue="blockController.getStyle(row.styleProperty) ?? null"
				:placeholder="getRenderedValue(row.styleProperty)"
				@update:modelValue="(val: StyleValue) => blockController.setStyle(row.styleProperty, val)"
			/>
			<IconButton
				:icon="LucideX"
				label="Remove property"
				size="sm"
				tooltipPlacement="left"
				class="w-4 shrink-0 opacity-0 focus:opacity-100 group-hover:opacity-100"
				@click="removeProperty(row.property)"
			/>
		</div>

		<Autocomplete
			:key="pickerResetCount"
			:modelValue="null"
			placeholder="Add CSS property"
			:getOptions="searchProperties"
			:allowArbitraryValue="true"
			@update:modelValue="addProperty"
		/>
	</div>
</template>

<script lang="ts">
import { reactive } from "vue"

// rows added from the picker stay visible until removed, even while empty.
// Keyed by block and module-scoped so the list survives section collapse and reselection.
const addedPropertiesByBlock = reactive(new Map<string, Set<string>>())

const getAddedProperties = (componentId: string) => addedPropertiesByBlock.get(componentId)

const addAddedProperty = (componentId: string, property: string) => {
	if (!addedPropertiesByBlock.has(componentId)) {
		addedPropertiesByBlock.set(componentId, new Set())
	}
	addedPropertiesByBlock.get(componentId)!.add(property)
}
</script>

<script setup lang="ts">
import { computed, nextTick, ref, type CSSProperties } from "vue"
import Autocomplete from "@/components/Autocomplete.vue"
import DynamicStyleSetter from "@/components/DynamicStyleSetter.vue"
import IconButton from "@/components/IconButton.vue"
import InlineInput from "@/components/InlineInput.vue"
import useCanvasStore from "@/stores/canvasStore"
import blockController from "@/utils/blockController"
import {
	getCSSPropertyControl,
	getCSSPropertyOptions,
	isValidCSSPropertyName,
	normalizeCSSPropertyName,
} from "@/utils/cssMetadata"
import { kebabToCamelCase, toTitleCase } from "@/utils/helpers"
import { getStylePropertiesWithoutControls } from "@/utils/stylePropertiesWithoutControls"
import type { StyleValue } from "@/types"
import LucideX from "~icons/lucide/x"

// the union of usedStyleProperties declared in ComponentStyles.vue
const props = defineProps<{ controlledProperties: Set<string> }>()

const canvasStore = useCanvasStore()
const pickerResetCount = ref(0)

const selectedBlock = computed(() =>
	blockController.isAnyBlockSelected() ? blockController.getFirstSelectedBlock() : null,
)

// styles that apply at the active breakpoint, including the ones it inherits
const activeProperties = computed(() => {
	const block = selectedBlock.value
	if (!block) return new Set<string>()
	const breakpoint = canvasStore.activeCanvas?.activeBreakpoint || "desktop"
	const properties = getStylePropertiesWithoutControls(block.getStyles(breakpoint), props.controlledProperties)
	getAddedProperties(block.componentId)?.forEach((property) => properties.add(property))
	return properties
})

const propertyRows = computed(() =>
	Array.from(activeProperties.value).map((property) => {
		const styleProperty = kebabToCamelCase(property) as keyof CSSProperties
		const label = toTitleCase(property)
		return {
			property,
			styleProperty,
			label,
			controlProps: getCSSPropertyControl(property),
			// BlockProperty-shaped descriptor so DynamicStyleSetter can label itself
			// and read the current value, like it does for curated rows
			dynamicValueProperty: {
				component: InlineInput,
				searchKeyWords: "",
				getProps: () => ({ label, property: styleProperty }),
				getValue: () => (blockController.getStyle(styleProperty) ?? null) as string | null,
			},
		}
	}),
)

const getRenderedValue = (property: keyof CSSProperties) =>
	String(selectedBlock.value?.getRenderedStyle(property) ?? "unset")

const searchProperties = async (query: string) => {
	const options = getCSSPropertyOptions(
		query,
		new Set([...props.controlledProperties, ...activeProperties.value]),
	)
	const arbitraryOption = getArbitraryOption(query)
	if (arbitraryOption && !options.some((option) => option.value === arbitraryOption.value)) {
		options.push(arbitraryOption)
	}
	return options
}

// keeps nonstandard property names and "color: red" declarations addable without
// echoing controlled properties back as dead options
const getArbitraryOption = (query: string) => {
	const trimmed = query.trim()
	if (!trimmed) return null
	if (trimmed.includes(":")) {
		return parseCSSDeclarations(trimmed).length ? { label: `Set "${trimmed}"`, value: trimmed } : null
	}
	const property = normalizeCSSPropertyName(trimmed)
	return canAddProperty(property) ? { label: `Add "${property}"`, value: property } : null
}

const canAddProperty = (property: string) =>
	isValidCSSPropertyName(property) &&
	!props.controlledProperties.has(property) &&
	!activeProperties.value.has(property)

const resetPicker = () => {
	pickerResetCount.value += 1
}

const focusProperty = async (property: string) => {
	await nextTick()
	const row = document.querySelector(`[data-style-property="${kebabToCamelCase(property)}"]`)
	const input = row?.querySelector("input") as HTMLInputElement | null
	input?.scrollIntoView({ block: "nearest" })
	input?.focus()
}

const addProperty = (raw: string | null) => {
	resetPicker()
	const block = selectedBlock.value
	if (!raw || !block) return

	// "color: red" style input sets the value right away; a bare name adds an empty row
	if (raw.includes(":")) {
		applyDeclarations(parseCSSDeclarations(raw))
		return
	}

	const property = normalizeCSSPropertyName(raw)
	if (!canAddProperty(property)) return
	addAddedProperty(block.componentId, property)
	focusProperty(property)
}

const removeProperty = (property: string) => {
	getAddedProperties(selectedBlock.value?.componentId || "")?.delete(property)
	blockController.removeStyle(kebabToCamelCase(property) as keyof CSSProperties)
}

// accepts "a: b; c: d" text and devtools-style multi-line CSS
const parseCSSDeclarations = (text: string) => {
	const declarations: Array<{ property: string; value: string }> = []
	for (const line of text.split(/[;\n]/)) {
		const separatorIndex = line.indexOf(":")
		if (separatorIndex === -1) continue
		const property = normalizeCSSPropertyName(line.slice(0, separatorIndex).replace(/["'{}]/g, ""))
		const value = line
			.slice(separatorIndex + 1)
			.trim()
			.replace(/^["']/, "")
			.replace(/[,"']+$/, "")
		if (property && value && isValidCSSPropertyName(property)) declarations.push({ property, value })
	}
	return declarations
}

// values land on their dedicated control when one exists, in More Styles otherwise
const applyDeclarations = (declarations: Array<{ property: string; value: string }>) => {
	const block = selectedBlock.value
	if (!block) return
	declarations.forEach(({ property, value }) => {
		blockController.setStyle(kebabToCamelCase(property) as keyof CSSProperties, value)
		if (!props.controlledProperties.has(property)) addAddedProperty(block.componentId, property)
	})
}

const pasteStyles = (event: ClipboardEvent) => {
	const text = event.clipboardData?.getData("text/plain") || ""
	if (!text.includes(":")) return

	// a single declaration pasted into an input is a value edit, not a bulk paste
	const target = event.target as HTMLElement | null
	const isInputTarget = target?.tagName === "INPUT" || target?.tagName === "TEXTAREA"
	if (isInputTarget && !/[;\n{]/.test(text)) return

	const declarations = parseCSSDeclarations(text)
	if (!declarations.length) return
	event.preventDefault()
	applyDeclarations(declarations)
}
</script>
