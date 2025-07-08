<template>
	<CollapsibleSection sectionName="Watchers">
		<div class="flex flex-col gap-1">
			<div
				v-if="studioPageWatchers.data?.length"
				v-for="watcher in studioPageWatchers.data"
				:key="watcher.name"
				class="group/variable flex flex-row justify-between"
			>
				<div class="flex flex-row justify-between">
					<div class="font-mono text-xs font-semibold text-pink-700">{{ watcher.source }}</div>
				</div>
				<div
					class="invisible -mt-1 ml-auto self-start text-gray-600 group-hover/variable:visible has-[.active-item]:visible"
				>
					<Dropdown :options="getWatcherMenu(watcher)" trigger="click">
						<template v-slot="{ open }">
							<button
								class="flex cursor-pointer items-center rounded-sm p-1 text-gray-700 hover:bg-gray-300"
								:class="open ? 'active-item' : ''"
							>
								<FeatherIcon name="more-horizontal" class="h-3 w-3" />
							</button>
						</template>
					</Dropdown>
				</div>
			</div>
			<EmptyState v-else message="No watchers added" />
		</div>

		<div class="mt-2 flex flex-col">
			<Button icon-left="plus" @click="showWatcherDialog = true">Add Watcher</Button>
			<Dialog
				v-model="showWatcherDialog"
				:options="{
					title: pageWatcher.name ? 'Edit Watcher' : 'Add Watcher',
					size: '2xl',
				}"
				@after-leave="
					() => {
						pageWatcher = {
							source: '',
							script: '',
							immediate: false,
							parent: '',
							name: '',
						}
					}
				"
				:disableOutsideClickToClose="true"
			>
				<template #body-content>
					<div class="flex flex-col space-y-4">
						<FormControl
							type="autocomplete"
							:options="store.variableOptions"
							label="Source"
							placeholder="Select variable"
							:modelValue="pageWatcher.source"
							@update:modelValue="
								(selectedOption: SelectOption) => {
									pageWatcher.source = selectedOption.value
								}
							"
						/>
						<Code
							label="Script"
							language="javascript"
							height="250px"
							v-model="pageWatcher.script"
							:completions="getCompletions"
						/>
						<FormControl
							type="checkbox"
							label="Run Immediately?"
							description="By default, this script won't run unless the source value changes. Enable this to run the script immediately."
							v-model="pageWatcher.immediate"
						/>
					</div>
				</template>
				<template #actions>
					<Button
						variant="solid"
						:label="pageWatcher.name ? 'Update' : 'Add'"
						@click="
							() => {
								if (pageWatcher.name) {
									editPageWatcher(pageWatcher)
								} else {
									addPageWatcher(pageWatcher)
								}
							}
						"
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
import type { SelectOption } from "@/types"
import type { StudioPageWatcher } from "@/types/Studio/StudioPageWatcher"
import useStudioStore from "@/stores/studioStore"
import { toast } from "vue-sonner"
import { confirm } from "@/utils/helpers"
import { useStudioCompletions } from "@/utils/useStudioCompletions"

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
	fields: ["name", "source", "script", "immediate", "parent"],
	orderBy: "modified desc",
	pageLength: 50,
	auto: true,
})

const showWatcherDialog = ref(false)
const pageWatcher = ref<StudioPageWatcher>({
	source: "",
	script: "",
	immediate: false,
	parent: "",
	name: "",
})
const store = useStudioStore()

const getWatcherMenu = (watcher: StudioPageWatcher) => {
	return [
		{
			label: "Edit",
			icon: "edit",
			onClick: async () => {
				pageWatcher.value = { ...watcher }
				showWatcherDialog.value = true
			},
		},
		{
			label: "Delete",
			icon: "trash",
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
		})
		.then(async () => {
			// setValue didn't update the list, so reloading explicitly
			await studioPageWatchers.reload()
			showWatcherDialog.value = false
		})
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
