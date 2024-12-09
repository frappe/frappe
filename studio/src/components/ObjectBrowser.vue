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
				<div class="group/key my-[7px] flex cursor-pointer items-start gap-0.5" @click="toggleExpanded(key)">
					<FeatherIcon
						v-if="isObject(value)"
						:name="isExpanded(key) ? 'chevron-down' : 'chevron-right'"
						class="-ml-0.5 h-3 w-3"
					/>
					<span class="text-pink-700">{{ key }}:</span>
					<span
						:class="[
							// wrap truncated text on expansion to display the entire value
							!isObject(value) && isExpanded(key) ? 'whitespace-normal text-wrap break-all' : 'truncate',
							'text-violet-700',
						]"
					>
						{{ formatValue(value) }}
					</span>

					<IconButton
						icon="copy"
						label="Copy object path"
						class="invisible ml-auto px-2 hover:visible group-hover/key:visible"
						size="sm"
						:hoverDelay="1"
						@click.prevent="copyToClipboard('{{ ' + getObjectPath(key) + ' }}')"
					/>
				</div>

				<!-- nested object properties -->
				<div v-if="isObject(value) && isExpanded(key)" class="ml-2">
					<ObjectBrowser :object="value" :parentPath="getObjectPath(key)" />
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { copyToClipboard } from "@/utils/helpers"
import { ref, computed } from "vue"
import IconButton from "@/components/IconButton.vue"

const props = withDefaults(
	defineProps<{
		object: object
		name?: string
		parentPath?: string
	}>(),
	{
		name: "",
		parentPath: "",
	},
)

const expandedKeys = ref(new Set<string>())

const isObject = (value: string | Function | object) => {
	return typeof value === "object" && value !== null
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
	if (typeof value === "function") {
		return formatFunctionPreview(value)
	} else if (isObject(value)) {
		return "Object"
	} else {
		if (typeof value === "string") return `"${value}"`
		return String(value)
	}
}

const objectParentPath = computed(() => props.parentPath || props.name)
const getObjectPath = (key: string) => {
	return `${objectParentPath.value}.${key}`
}
</script>
