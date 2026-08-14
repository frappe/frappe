<template>
	<div class="flex flex-col gap-3" @paste="pasteStyles">
		<div
			v-for="row in visibleRows"
			:key="row.property"
			class="flex items-center gap-1"
			:data-style-property="row.styleProperty"
			@contextmenu="showRemoveContextMenu($event, row.property)"
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
		</div>
		<ContextMenu
			ref="removeContextMenu"
			:options="removeContextMenuOptions"
			@select="(action: CallableFunction) => action()"
		/>

		<Combobox
			ref="propertyCombobox"
			:options="propertyOptions"
			placeholder="Add CSS property"
			empty-text="No matching properties"
			open-on-focus
			@update:query="propertySearch = $event"
			@update:modelValue="addProperty"
		>
			<template #suffix>
				<span />
			</template>
			<template #item-label="{ item }">
				<span class="flex min-w-0 flex-col gap-0.5">
					<span class="truncate text-sm text-ink-gray-8">
						{{ toTitleCase(item.value) }}
					</span>
					<code class="truncate font-mono text-xs text-ink-gray-5">
						{{ item.value }}
					</code>
				</span>
			</template>
			<template #item-add-property="{ query }">
				<span class="flex min-w-0 items-center gap-2">
					<span class="min-w-0 truncate text-sm text-ink-gray-8">
						Add
						<code class="font-mono text-xs text-ink-gray-6">{{ normalizeCSSPropertyName(query) }}</code>
					</span>
				</span>
			</template>
			<template #item-set-declaration="{ query }">
				<span class="flex min-w-0 items-center gap-2">
					<span class="min-w-0 truncate text-sm text-ink-gray-8">
						Set
						<code class="font-mono text-xs text-ink-gray-6">{{ query }}</code>
					</span>
				</span>
			</template>
		</Combobox>
	</div>
</template>

<script lang="ts">
import { reactive } from "vue"

// rows added from the picker stay visible until removed, even while empty.
// Keyed by block and module-scoped so the list survives section collapse and reselection.
const addedPropertiesByBlock = reactive(new Map<string, Set<string>>())

export const getAddedProperties = (componentId: string) => addedPropertiesByBlock.get(componentId)

const addAddedProperty = (componentId: string, property: string) => {
	if (!addedPropertiesByBlock.has(componentId)) {
		addedPropertiesByBlock.set(componentId, new Set())
	}
	addedPropertiesByBlock.get(componentId)!.add(property)
}
</script>

<script setup lang="ts">
import { Combobox } from "frappe-ui"
import { computed, nextTick, ref, type CSSProperties } from "vue"
import ContextMenu from "@/components/ContextMenu.vue"
import DynamicStyleSetter from "@/components/DynamicStyleSetter.vue"
import InlineInput from "@/components/InlineInput.vue"
import useCanvasStore from "@/stores/canvasStore"
import useStudioStore from "@/stores/studioStore"
import blockController from "@/utils/blockController"
import {
	getCSSPropertyControl,
	getCSSPropertyOptions,
	isValidCSSPropertyName,
	normalizeCSSPropertyName,
} from "@/utils/cssMetadata"
import { isTargetEditable, kebabToCamelCase, toTitleCase } from "@/utils/helpers"
import { getStylePropertiesWithoutControls } from "@/utils/stylePropertiesWithoutControls"
import type { ContextMenuOption, StyleValue } from "@/types"

// the union of usedStyleProperties declared in ComponentStyles.vue
const props = defineProps<{ controlledProperties: Set<string> }>()

const canvasStore = useCanvasStore()
const studioStore = useStudioStore()
const propertySearch = ref("")
const propertyCombobox = ref<{ reset: () => void } | null>(null)

const selectedBlock = computed(() =>
	blockController.isAnyBlockSelected() ? blockController.getFirstSelectedBlock() : null,
)

// styles that apply at the active breakpoint, including the ones it inherits
const activeProperties = computed(() => {
	const block = selectedBlock.value
	if (!block) return new Set<string>()
	const breakpoint = canvasStore.activeCanvas?.activeBreakpoint || "desktop"
	const properties = getStylePropertiesWithoutControls(
		block.getStyles(breakpoint),
		props.controlledProperties,
	)
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

// narrow rows to the panel-wide property filter; a match on the section itself
// (e.g. searching "more styles") keeps the full list instead of blanking it
const visibleRows = computed(() => {
	const query = studioStore.propertyFilter?.toLowerCase() || ""
	if (!query) return propertyRows.value
	const matchingRows = propertyRows.value.filter(
		(row) =>
			row.property.includes(query) ||
			row.styleProperty.toLowerCase().includes(query) ||
			row.label.toLowerCase().includes(query),
	)
	return matchingRows.length ? matchingRows : propertyRows.value
})

const normalizedPropertySearch = computed(() => normalizeCSSPropertyName(propertySearch.value))

// labels carry the query so the combobox's substring filter keeps fuzzy matches;
// the item-label slot renders the clean property name instead
const searchablePropertyOptions = computed(() =>
	getCSSPropertyOptions(
		propertySearch.value,
		new Set([...props.controlledProperties, ...activeProperties.value]),
	).map((option) => ({
		...option,
		label: normalizedPropertySearch.value
			? `${option.label} ${normalizedPropertySearch.value}`
			: option.label,
	})),
)

// trailing escape hatches: nonstandard property names and "color: red" declarations
// stay addable without echoing controlled properties back as dead options
const propertyOptions = computed(() => [
	...searchablePropertyOptions.value,
	{
		type: "custom" as const,
		key: "add-property",
		label: "Add property",
		slot: "add-property",
		condition: ({ query }: { query: string }) => canAddProperty(normalizeCSSPropertyName(query)),
		onClick: ({ query }: { query: string }) => addProperty(query),
	},
	{
		type: "custom" as const,
		key: "set-declaration",
		label: "Set declaration",
		slot: "set-declaration",
		condition: ({ query }: { query: string }) =>
			query.includes(":") && parseCSSDeclarations(query).length > 0,
		onClick: ({ query }: { query: string }) => addProperty(query),
	},
])

const canAddProperty = (property: string) =>
	isValidCSSPropertyName(property) &&
	!props.controlledProperties.has(property) &&
	!activeProperties.value.has(property)

const resetPicker = () => {
	propertySearch.value = ""
	nextTick(() => propertyCombobox.value?.reset())
}

const focusProperty = async (property: string) => {
	await nextTick()
	const row = document.querySelector(`[data-style-property="${kebabToCamelCase(property)}"]`)
	const input = row?.querySelector("input") as HTMLInputElement | null
	input?.scrollIntoView({ block: "nearest" })
	input?.focus()
}

const addProperty = (raw: string | null) => {
	const block = selectedBlock.value
	// the null emitted by the combobox's own reset must not reset again (loop)
	if (!raw || !block) return

	// "color: red" style input sets the value right away; a bare name adds an empty row
	if (raw.includes(":")) {
		applyDeclarations(parseCSSDeclarations(raw))
	} else {
		const property = normalizeCSSPropertyName(raw)
		if (canAddProperty(property)) {
			addAddedProperty(block.componentId, property)
			focusProperty(property)
		}
	}
	resetPicker()
}

const removeProperty = (property: string) => {
	getAddedProperties(selectedBlock.value?.componentId || "")?.delete(property)
	blockController.removeStyle(kebabToCamelCase(property) as keyof CSSProperties)
}

const removeContextMenu = ref<InstanceType<typeof ContextMenu> | null>(null)
const contextMenuProperty = ref<string | null>(null)

const removeContextMenuOptions: ContextMenuOption[] = [
	{
		label: "Remove",
		action: () => contextMenuProperty.value && removeProperty(contextMenuProperty.value),
	},
]

const showRemoveContextMenu = (event: MouseEvent, property: string) => {
	if (isTargetEditable(event)) return
	event.preventDefault()
	contextMenuProperty.value = property
	removeContextMenu.value?.show(event.pageX, event.pageY)
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
