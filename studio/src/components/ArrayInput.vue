<template>
	<div class="flex h-full w-full flex-col gap-3">
		<InputLabel
			v-if="label"
			:class="[required ? `after:text-ink-red-7 after:content-['_*']` : '']"
			class="mb-1"
		>
			{{ label }}
		</InputLabel>

		<!-- primitive items: one remove button per row, clear affordance hidden -->
		<div v-if="!itemTypes" class="flex flex-col gap-1.5">
			<EmptyState v-if="items.length === 0 && emptyMessage" :message="emptyMessage" />
			<div v-for="(item, index) in items" :key="index" class="flex items-center gap-2">
				<Input
					class="flex-1"
					hideClearButton
					:modelValue="item"
					@update:modelValue="(newValue: string) => updateItem(index, newValue)"
				/>
				<Button
					class="flex-shrink-0 text-xs"
					variant="ghost"
					icon="lucide-x"
					title="Remove"
					@click="removeItem(index)"
				/>
			</div>
		</div>

		<!-- object items: one card per item with a field per itemTypes entry -->
		<template v-else-if="items.length > 0">
			<div
				v-for="(item, index) in items"
				:key="index"
				class="group/item relative flex flex-col gap-1.5 rounded-md border p-3"
			>
				<div
					v-for="(fieldSchema, fieldKey) in itemTypes"
					:key="fieldKey"
					class="flex w-full flex-row items-center gap-1"
				>
					<template v-if="fieldKey === 'icon'">
						<InputLabel class="text-xs">{{ fieldKey }}</InputLabel>
						<IconPicker
							:modelValue="getUnwrappedIconValue(item[fieldKey])"
							@update:modelValue="
								(val) => updateItemField(index, fieldKey as string, `{{ getIcon('${val}') }}`)
							"
							class="w-full bg-surface-base"
						/>
					</template>
					<InlineInput
						v-else
						:label="fieldKey"
						:type="fieldSchema.inputType"
						:modelValue="item[fieldKey]"
						@update:modelValue="(newValue) => updateItemField(index, fieldKey as string, newValue)"
						class="flex-1"
					/>
				</div>
				<div
					title="Remove"
					class="absolute right-0 top-0 hidden -translate-y-1/2 translate-x-1/2 cursor-pointer rounded-full border border-outline-gray-2 bg-surface-base p-0.5 hover:bg-surface-gray-1 group-hover/item:block"
				>
					<FeatherIcon name="x" @click="removeItem(index)" class="size-3 rounded-full" />
				</div>
			</div>
		</template>
		<EmptyState v-else :message="emptyMessage || 'No items added'" />

		<Button variant="outline" class="w-full" icon-left="plus" @click="addItem">
			{{ addLabel || "Add" }}
		</Button>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Button } from "frappe-ui"
import { IconPicker } from "frappe-ui/icons"
import Input from "@/components/Input.vue"
import InputLabel from "@/components/InputLabel.vue"
import InlineInput from "@/components/InlineInput.vue"
import EmptyState from "@/components/EmptyState.vue"

const props = defineProps<{
	modelValue: any[]
	label?: string
	itemTypes?: Record<string, any>
	required?: boolean
	emptyMessage?: string
	addLabel?: string
	newItemValue?: any
}>()

const emit = defineEmits(["update:modelValue", "add", "remove"])

const items = computed(() => {
	return Array.isArray(props.modelValue) ? props.modelValue : []
})

const getUnwrappedIconValue = (value: string | undefined) => {
	if (!value) return ""
	// Match both {{ getIcon('name') }} and getIcon('name') formats
	const match = value.match(/(?:\{\s*)?(?:getIcon|useIcon)\(['"]([^'"]+)['"]\)(?:\s*\})?/)
	return match ? match[1] : value
}

const updateItemField = (index: number, key: string, value: any) => {
	const newItems = [...items.value]
	newItems[index] = { ...newItems[index], [key]: value }
	emit("update:modelValue", newItems)
}

const updateItem = (index: number, value: any) => {
	const newItems = [...items.value]
	newItems[index] = value
	emit("update:modelValue", newItems)
}

const removeItem = (index: number) => {
	const newItems = items.value.filter((_, i) => i !== index)
	emit("update:modelValue", newItems)
	emit("remove", index)
}

const addItem = () => {
	const newItems = [...items.value, getNewItem()]
	emit("update:modelValue", newItems)
	emit("add")
}

const getNewItem = () => {
	if (props.newItemValue !== undefined) return props.newItemValue
	if (!props.itemTypes) return ""
	const newItem: Record<string, any> = {}
	Object.keys(props.itemTypes).forEach((key) => {
		newItem[key] = ""
	})
	return newItem
}
</script>
