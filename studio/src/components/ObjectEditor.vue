<!-- Extracted from Builder -->
<template>
	<div ref="objectEditor" class="flex flex-col gap-2" @paste="pasteObj">
		<div v-for="(value, key) in obj" :key="key" class="flex gap-2">
			<Input
				placeholder="Property"
				:modelValue="key"
				@update:modelValue="(val: string) => replaceKey(key, val)"
				class="dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:focus:bg-zinc-700 rounded-md text-sm text-gray-800"
			/>
			<Input
				placeholder="Value"
				:modelValue="value"
				@update:modelValue="(val: string) => updateObjectValue(key, val)"
				class="dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:focus:bg-zinc-700 rounded-md text-sm text-gray-800"
			/>
			<Button
				variant="outline"
				icon="x"
				class="dark:border-zinc-600 dark:bg-zinc-800 dark:hover:bg-zinc-700 p-2 dark:text-gray-100 dark:outline-0 dark:hover:text-gray-100"
				@click="deleteObjectKey(key as string)"
			></Button>
		</div>
		<Button
			variant="subtle"
			label="Add"
			class="dark:bg-zinc-800 dark:text-gray-100"
			@click="addObjectKey"
		></Button>
		<p
			class="dark:bg-zinc-800 dark:text-zinc-300 rounded-sm bg-gray-100 p-2 text-2xs text-gray-800"
			v-show="description"
		>
			<span v-html="description"></span>
		</p>
	</div>
</template>

<script setup lang="ts">
import { mapToObject, replaceMapKey } from "@/utils/helpers"
import { ref } from "vue"

const props = defineProps<{
	obj: Record<string, string>
	description?: string
}>()

const emit = defineEmits({
	"update:obj": (obj: Record<string, string>) => true,
})

const addObjectKey = () => {
	const map = new Map(Object.entries(props.obj))
	map.set("", "")
	emit("update:obj", mapToObject(map))
}

const updateObjectValue = (key: string, value: string) => {
	const map = new Map(Object.entries(props.obj))
	map.set(key, value)
	emit("update:obj", mapToObject(map))
}

const replaceKey = (oldKey: string, newKey: string) => {
	const map = new Map(Object.entries(props.obj))
	emit("update:obj", mapToObject(replaceMapKey(map, oldKey, newKey)))
}

const deleteObjectKey = (key: string) => {
	const map = new Map(Object.entries(props.obj))
	map.delete(key)
	emit("update:obj", mapToObject(map))
}

const objectEditor = ref<HTMLElement | null>(null)

const pasteObj = (e: ClipboardEvent) => {
	const text = e.clipboardData?.getData("text/plain")
	if (text) {
		if (!text.includes(":")) return
		const map = new Map(Object.entries(props.obj))
		try {
			const objString = text.match(/{[^{}]+}/)?.[0]
			if (!objString) throw new Error("Invalid object")
			const obj = new Function("return " + objString)()
			if (typeof obj === "object") {
				for (const [key, value] of Object.entries(obj)) {
					map.set(key, value as string)
				}
				map.delete("")
			}
		} catch (e) {
			const lines = text.split(";")
			for (const line of lines) {
				const [key, value] = line.split(":")
				if (!key || !value) continue
				map.set(key.trim(), value.replace(";", "").trim())
			}
			map.delete("")
		}
		emit("update:obj", mapToObject(map))
	}
}
</script>
