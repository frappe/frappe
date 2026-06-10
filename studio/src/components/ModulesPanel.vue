<template>
	<CollapsibleSection :sectionName="title">
		<div class="flex flex-col gap-1.5">
			<div
				v-if="attached.data?.length"
				v-for="row in attached.data"
				:key="row.name"
				class="group/item flex flex-row items-center justify-between gap-2"
			>
				<div class="flex min-w-0 flex-col gap-1">
					<span class="truncate font-mono text-xs font-semibold text-pink-700">
						{{ row.module_name || row.module_path }}
					</span>
					<span class="truncate text-2xs text-ink-gray-5">{{ row.module_path }}</span>
				</div>
				<Button
					variant="ghost"
					icon="x"
					class="opacity-0 group-hover/item:opacity-100"
					@click="removeModule(row)"
				/>
			</div>
			<EmptyState v-else :message="`No ${scope} modules imported`" />
		</div>

		<div class="mt-2">
			<Autocomplete
				:options="availableOptions"
				placeholder="Import a module"
				modelValue=""
				@update:modelValue="addModule"
			>
				<template #target="{ togglePopover }">
					<Button class="w-full" icon-left="plus" @click="togglePopover">Import Module</Button>
				</template>
				<template #item-suffix="{ option }">
					<span class="ml-2 truncate text-2xs text-ink-gray-4">{{ option.module_path }}</span>
				</template>
			</Autocomplete>
		</div>
	</CollapsibleSection>
</template>

<script setup lang="ts">
import { computed, watch } from "vue"
import { createListResource, Autocomplete, Button, toast } from "frappe-ui"
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import EmptyState from "@/components/EmptyState.vue"
import { studioModulesResource, loadModules } from "@/data/studioModules"
import useCodeStore from "@/stores/codeStore"
import type { StudioModuleMeta } from "@/types/StudioModule"

const props = defineProps<{
	scope: "app" | "page"
	parentDoctype: string
	parentName: string
	frappeApp?: string
}>()

const codeStore = useCodeStore()
const title = computed(() => (props.scope === "app" ? "App Modules" : "Page Modules"))

// rows attached to this app/page (Studio Module Import child table)
const attached = createListResource({
	doctype: "Studio Module Import",
	parent: props.parentDoctype,
	fields: ["name", "module_name", "module_path", "parent"],
	filters: { parent: props.parentName },
	orderBy: "idx asc",
	pageLength: 100,
	auto: true,
})

watch(
	() => props.parentName,
	(name) => {
		attached.filters = { parent: name }
		attached.reload()
	},
)

// load filesystem discovery for the picker options
if (props.frappeApp && !studioModulesResource.data) {
	studioModulesResource.reload({ frappe_app: props.frappeApp })
}

// available modules to import = discovered modules minus already-attached
const availableOptions = computed(() => {
	const taken = new Set((attached.data || []).map((r: { module_path: string }) => r.module_path))
	return (studioModulesResource.data || [])
		.filter((m: StudioModuleMeta) => !taken.has(m.module_path))
		.map((m: StudioModuleMeta) => ({
			label: m.module_name,
			value: m.module_path,
			module_path: m.module_path,
			module_name: m.module_name,
		}))
})

async function syncExposure() {
	const paths = (attached.data || []).map((r: { module_path: string }) => r.module_path)
	if (props.scope === "app") codeStore.setAppModulePaths(paths)
	else codeStore.setPageModulePaths(paths)
	await loadModules(paths)
}

async function addModule(option: { value: string; module_name: string } | null) {
	if (!option?.value) return
	try {
		await attached.insert.submit({
			parent: props.parentName,
			parenttype: props.parentDoctype,
			parentfield: "modules",
			module_path: option.value,
			module_name: option.module_name,
		})
		await attached.reload()
		await syncExposure()
	} catch (error: any) {
		toast.error("Failed to import module", { description: error?.messages?.join(", ") })
	}
}

async function removeModule(row: { name: string }) {
	try {
		await attached.delete.submit(row.name)
		await attached.reload()
		await syncExposure()
	} catch {
		toast.error("Failed to remove module")
	}
}
</script>
