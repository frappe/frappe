<template>
	<div v-if="deprecatedProps.length" class="flex flex-col gap-3">
		<div class="border-t border-outline-gray-1" />
		<!-- chevron in the selector slot, so the name lines up with the prop labels -->
		<div class="flex cursor-pointer items-center" @click="showDeprecatedProps = !showDeprecatedProps">
			<span
				class="mr-1 size-3 shrink-0 text-ink-gray-4"
				:class="showDeprecatedProps ? 'lucide-chevron-down' : 'lucide-chevron-right'"
			/>
			<div class="flex min-w-0 flex-1 items-center justify-between">
				<div class="flex items-center gap-1.5 text-xs leading-5 text-ink-gray-5">
					{{ isUnregistered ? "Saved props" : "Deprecated" }}
					<Badge :label="`${deprecatedProps.length}`" size="sm" />
				</div>
				<Tooltip :text="tooltip">
					<button
						type="button"
						class="text-xs text-ink-gray-5 hover:text-ink-gray-8"
						@click.stop="removeDeprecatedProps"
					>
						Remove all
					</button>
				</Tooltip>
			</div>
		</div>
		<template v-if="showDeprecatedProps">
			<div
				v-for="prop in deprecatedProps"
				:key="prop.name"
				class="flex w-full items-center [&_[data-input-label]]:text-ink-gray-4 [&_input]:bg-surface-gray-1 [&_input]:text-ink-gray-5"
			>
				<DynamicValueSelector
					:block="block"
					:isVariableBound="prop.value?.$type === 'variable' ? prop.value.name : null"
					:class="['opacity-50', { 'mt-1 self-start': prop.inputType === 'code' }]"
					@update:modelValue="(varName, bindVariable) => setDynamicValue(prop.name, varName, bindVariable)"
				/>
				<Code
					v-if="prop.inputType === 'code'"
					:label="prop.name"
					language="javascript"
					:modelValue="formatValue(prop.value)"
					:showLineNumbers="false"
					class="min-w-0 flex-1 overflow-hidden opacity-70"
					@update:modelValue="(newValue) => block.setProp(prop.name, newValue)"
				/>
				<InlineInput
					v-else
					:label="prop.name"
					:type="prop.inputType"
					:modelValue="formatValue(prop.value)"
					class="flex-1"
					@update:modelValue="(newValue) => block.setProp(prop.name, newValue)"
				/>
			</div>
		</template>
	</div>
</template>

<script setup lang="ts">
// Props saved on the block that the component no longer declares — a frappe-ui
// breaking change, a rename, or a typo. Vue still spreads them onto the component
// as fallthrough attrs (a stale `extensions` can break a block), and the props
// panel can't show them, so they are collected here to copy from and remove.
import { computed, ref } from "vue"
import { Tooltip } from "frappe-ui"
import Block from "@/utils/block"
import Code from "@/components/Code.vue"
import InlineInput from "@/components/InlineInput.vue"
import DynamicValueSelector from "@/components/DynamicValueSelector.vue"
import components from "@/data/components"
import { isObjectEmpty } from "@/utils/helpers"
import { isDynamicValue } from "@/utils/code"
import type { ComponentProps } from "@/types"
import { Badge } from "frappe-ui"

const PASS_THROUGH_ATTRS = ["class", "style", "id", "key", "ref", "slot"]

const props = defineProps<{ block: Block; propConfigs: ComponentProps }>()

const showDeprecatedProps = ref(false)

const isUnregistered = computed(() => props.block.isUnregisteredComponent())
const tooltip = computed(() =>
	isUnregistered.value
		? `${props.block.componentName} is missing; copy these props into its replacement`
		: `${props.block.componentName} no longer accepts these props`,
)

const deprecatedProps = computed(() => {
	// no configs usually means the schema hasn't loaded, not that every prop is stale
	if (isObjectEmpty(props.propConfigs) && !isUnregistered.value) return []

	const stored = props.block.componentProps || {}
	return Object.keys(stored)
		.filter(isDeprecatedProp)
		.map((propName) => ({
			name: propName,
			value: stored[propName],
			inputType: inferInputType(stored[propName]),
		}))
})

function removeDeprecatedProps() {
	deprecatedProps.value.forEach((prop) => props.block.removeProp(prop.name))
}

function setDynamicValue(propName: string, varName: string, bindVariable: boolean) {
	props.block.setProp(propName, bindVariable ? { $type: "variable", name: varName } : `{{ ${varName} }}`)
}

function formatValue(value: any) {
	return value?.$type === "variable" ? `{{ ${value.name} }}` : value
}

function isDeprecatedProp(propName: string) {
	const hiddenProps = components.get(props.block.componentName)?.hideProps || []
	return !(propName in props.propConfigs) && !hiddenProps.includes(propName) && !isPassThroughAttr(propName)
}

function isPassThroughAttr(propName: string) {
	return (
		PASS_THROUGH_ATTRS.includes(propName) ||
		propName.startsWith("data-") ||
		propName.startsWith("aria-") ||
		propName.startsWith("on")
	)
}

function inferInputType(value: any) {
	if (isDynamicValue(value) || value?.$type === "variable") return "code"
	if (typeof value === "boolean") return "checkbox"
	if (typeof value === "number") return "number"
	if (value && typeof value === "object") return "code"
	return "text"
}
</script>
