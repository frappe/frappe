<template>
	<div class="object-browser font-mono text-xs">
		<!-- object name -->
		<div
			v-if="name"
			@click="toggleExpanded('root')"
			class="flex cursor-pointer items-center gap-0.5 font-bold"
		>
			<FeatherIcon :name="isExpanded('root') ? 'chevron-down' : 'chevron-right'" class="h-3 w-3" />
			<span class="text-pink-700">{{ name }}</span>
		</div>

		<!-- object properties -->
		<div v-if="!name || isExpanded('root')" class="ml-4">
			<div v-for="(value, key) in object" :key="key">
				<div class="my-[7px] flex items-center gap-0.5">
					<FeatherIcon
						@click="toggleExpanded(key)"
						v-if="isExpandable(value)"
						:name="isExpanded(key) ? 'chevron-down' : 'chevron-right'"
						class="h-3 w-3 cursor-pointer"
					/>
					<span class="text-pink-700">{{ key }}:</span>
					<span class="truncate text-violet-700"> {{ formatValue(value) }} </span>
				</div>

				<!-- nested object properties -->
				<div v-if="isExpanded(key)" class="ml-2">
					<ObjectBrowser :object="value" />
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue"

defineProps({
	object: {
		type: Object,
		required: true,
	},
	name: {
		type: String,
		default: "",
	},
})

const expandedKeys = ref(new Set<string>())

const isExpandable = (value: string | Function | object) => {
	return ["function", "object"].includes(typeof value) && value !== null
}

const isExpanded = (key: string) => {
	return expandedKeys.value.has(key)
}

const toggleExpanded = (key: string) => {
	if (expandedKeys.value.has(key)) {
		expandedKeys.value.delete(key)
	} else {
		expandedKeys.value.add(key)
	}
}

const formatFunctionPreview = (fn: Function) => {
	const fnString = fn.toString().replace(/^function/, "f")
	const firstLine = fnString.slice(0, fnString.indexOf("\n"))
	return `${firstLine}`
}

const formatValue = (value: string | Function | object) => {
	if (!isExpandable(value)) {
		if (typeof value === "string") return `"${value}"`
		return String(value)
	} else {
		if (typeof value === "function") {
			return formatFunctionPreview(value)
		} else return "Object"
	}
}
</script>
