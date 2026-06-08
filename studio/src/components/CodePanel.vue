<template>
	<CollapsibleSection sectionName="Watchers">
		<div class="flex flex-col gap-1">
			<div
				v-if="studioPageWatchers.data?.length"
				v-for="watcher in studioPageWatchers.data"
				:key="watcher.name"
				class="group/item flex flex-row items-center justify-between"
			>
				<div class="flex flex-row justify-between">
					<div class="font-mono text-xs font-semibold text-pink-700">{{ watcher.source }}</div>
				</div>
				<ItemActions :menuOptions="getWatcherMenu(watcher)" @edit="openWatcher(watcher)" />
			</div>
			<EmptyState v-else message="No watchers added" />
		</div>

		<div class="mt-2 flex flex-col">
			<Button icon-left="plus" @click="showWatcherDialog = true">Add Watcher</Button>
			<Dialog
				v-model="showWatcherDialog"
				:title="pageWatcher.name ? 'Edit Watcher' : 'Add Watcher'"
				size="3xl"
				@after-leave="
					() => {
						pageWatcher = {
							source: '',
							script: '',
							immediate: false,
							deep: false,
							parent: '',
							name: '',
						}
					}
				"
				:dismissible="false"
			>
				<template #default>
					<div class="flex flex-col space-y-4">
						<FormControl
							type="combobox"
							:options="store.variableOptions"
							label="Source"
							placeholder="Select variable"
							:openOnFocus="true"
							v-model="pageWatcher.source"
						/>
						<Code
							label="Script"
							language="javascript"
							height="400px"
							maxHeight="400px"
							v-model="pageWatcher.script"
							:emitOnChange="true"
							:completions="getCompletions"
							@save="editPageWatcher(pageWatcher)"
						/>
						<FormControl
							type="number"
							label="Debounce (ms)"
							placeholder="300"
							v-model="pageWatcher.debounce"
							description="Delay the execution until the set time has passed since the last change"
						/>
						<div class="flex flex-col space-y-1">
							<FormControl
								type="checkbox"
								label="Immediate: Run on page load"
								v-model="pageWatcher.immediate"
							/>
							<FormDescription description="Trigger when the page loads, not just when the source changes" />
						</div>
						<div class="flex flex-col space-y-1">
							<FormControl type="checkbox" label="Deep: Watch nested properties" v-model="pageWatcher.deep" />
							<FormDescription
								description="Trigger when nested properties within the source change, in addition to the source itself"
							/>
						</div>
					</div>
				</template>
				<template #actions>
					<Button
						variant="solid"
						:label="pageWatcher.name ? 'Update' : 'Add'"
						@click="savePageWatcher(pageWatcher)"
						class="w-full"
					/>
				</template>
			</Dialog>
		</div>
	</CollapsibleSection>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { createListResource, Dialog, FormControl } from "frappe-ui"
import EmptyState from "@/components/EmptyState.vue"
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import Code from "@/components/Code.vue"
import type { StudioPage } from "@/types/Studio/StudioPage"
import type { StudioPageWatcher } from "@/types/Studio/StudioPageWatcher"
import useStudioStore from "@/stores/studioStore"
import { toast } from "frappe-ui"
import { confirm } from "@/utils/helpers"
import { useStudioCompletions } from "@/utils/useStudioCompletions"
import ItemActions from "@/components/ItemActions.vue"
import FormDescription from "@/components/FormDescription.vue"

const props = defineProps<{
	page: StudioPage
}>()

const getCompletions = useStudioCompletions(true)

const studioPageWatchers = createListResource({
	doctype: "Studio Page Watcher",
	parent: "Studio Page",
	filters: {
		parent: props.page.name,
	},
	fields: ["name", "source", "script", "immediate", "deep", "debounce", "parent"],
	orderBy: "modified desc",
	pageLength: 50,
	auto: true,
})

const showWatcherDialog = ref(false)
const pageWatcher = ref<StudioPageWatcher>({
	source: "",
	script: "",
	immediate: false,
	deep: false,
	debounce: 0,
	parent: "",
	name: "",
})
const store = useStudioStore()

const openWatcher = (watcher: StudioPageWatcher) => {
	pageWatcher.value = { ...watcher }
	showWatcherDialog.value = true
}

const getWatcherMenu = (watcher: StudioPageWatcher) => {
	return [
		{
			label: "Delete",
			icon: "lucide-trash",
			theme: "red",
			onClick: () => deletePageWatcher(watcher),
		},
	]
}

const addPageWatcher = (watcher: StudioPageWatcher) => {
	studioPageWatchers.insert.submit(
		{
			source: watcher.source,
			script: watcher.script,
			immediate: watcher.immediate,
			deep: watcher.deep,
			debounce: watcher.debounce,
			parent: props.page.name,
			parenttype: "Studio Page",
			parentfield: "watchers",
		},
		{
			onSuccess() {
				showWatcherDialog.value = false
			},
			onError(error: any) {
				toast.error("Failed to add the watcher", {
					description: error.messages.join(", "),
				})
			},
		},
	)
}

const editPageWatcher = (watcher: StudioPageWatcher) => {
	studioPageWatchers.setValue
		.submit({
			name: watcher.name,
			source: watcher.source,
			script: watcher.script,
			immediate: watcher.immediate,
			deep: watcher.deep,
			debounce: watcher.debounce,
		})
		.then(async () => {
			// setValue didn't update the list, so reloading explicitly
			await studioPageWatchers.reload()
			toast.success("Watcher updated successfully")
		})
}

const savePageWatcher = (watcher: StudioPageWatcher) => {
	if (watcher.name) {
		editPageWatcher(watcher)
	} else {
		addPageWatcher(watcher)
	}
}

const deletePageWatcher = async (watcher: StudioPageWatcher) => {
	const confirmed = await confirm(`Are you sure you want to delete the watcher for ${watcher.source}?`)
	if (confirmed) {
		studioPageWatchers.delete
			.submit(watcher.name)
			.then(() => {
				toast.success(`Watcher for ${watcher.source} deleted successfully`)
			})
			.catch(() => {
				toast.error(`Failed to delete watcher for ${watcher.source}`)
			})
	}
}
</script>
