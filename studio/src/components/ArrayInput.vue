<template>
	<div class="group relative flex h-full w-full flex-col gap-1.5">
		<div class="flex items-start justify-between">
			<InputLabel v-if="label" :class="[required ? `after:text-red-600 after:content-['_*']` : '']">
				{{ label }}
			</InputLabel>
			<Button
				variant="ghost"
				size="sm"
				@click="isCodeMode = !isCodeMode"
				:icon="isCodeMode ? 'table' : 'code'"
			></Button>
		</div>

		<Code
			v-if="isCodeMode"
			language="javascript"
			:modelValue="codeValue"
			@update:modelValue="handleCodeUpdate"
			:showLineNumbers="false"
			class="mt-2 overflow-hidden"
		/>

		<div v-else class="mt-2 flex flex-col gap-3">
			<div
				v-for="(item, index) in items"
				:key="index"
				class="group flex flex-col gap-2 rounded-md border p-3"
			>
				<div
					v-for="(fieldSchema, fieldKey) in itemSchema"
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
							class="w-full bg-white"
						/>
					</template>
					<InlineInput
						v-else
						:label="fieldKey"
						:type="fieldSchema.type"
						:modelValue="item[fieldKey]"
						@update:modelValue="(newValue) => updateItemField(index, fieldKey as string, newValue)"
						class="flex-1"
					/>
				</div>
				<Button variant="outline" icon="x" class="w-full" @click="removeItem(index)" />
			</div>

			<Button variant="outline" class="mt-1 w-full" icon="plus" @click="addItem">Add Item</Button>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue"
import { Button } from "frappe-ui"
import Code from "@/components/Code.vue"
import { IconPicker } from "frappe-ui/icons"
import InputLabel from "@/components/InputLabel.vue"
import InlineInput from "@/components/InlineInput.vue"

const props = defineProps<{
	modelValue: any[]
	label?: string
	itemSchema?: Record<string, any>
	required?: boolean
}>()

const emit = defineEmits(["update:modelValue"])

const isCodeMode = ref(false)

const items = computed(() => {
	return Array.isArray(props.modelValue) ? props.modelValue : []
})

const codeValue = computed(() => {
	return JSON.stringify(props.modelValue || [], null, 2)
})

const handleCodeUpdate = (val: string) => {
	try {
		if (!val) {
			emit("update:modelValue", [])
			return
		}
		const parsed = JSON.parse(val)
		if (Array.isArray(parsed)) {
			emit("update:modelValue", parsed)
		}
	} catch (e) {
		// If invalid JSON, ignore until valid
	}
}

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

const removeItem = (index: number) => {
	const newItems = items.value.filter((_, i) => i !== index)
	emit("update:modelValue", newItems)
}

const addItem = () => {
	const newItems = [...items.value]
	const newItem: any = {}
	if (props.itemSchema) {
		Object.keys(props.itemSchema).forEach((key) => {
			newItem[key] = ""
		})
	}
	newItems.push(newItem)
	emit("update:modelValue", newItems)
}
</script>
