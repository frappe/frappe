<template>
	<Dialog v-model:open="open" title="Edit Page" size="md">
		<template #default>
			<PageMetaFields
				:appRoute="store.activeApp?.route"
				v-model:title="title"
				v-model:route="route"
				v-model:allowGuest="allowGuest"
			/>
		</template>
		<template #actions>
			<div class="flex flex-col gap-2">
				<ErrorMessage :message="error" />
				<Button variant="solid" label="Save" class="w-full" :loading="saving" @click="save" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue"
import { Button, Dialog, ErrorMessage, toast } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import PageMetaFields from "@/components/PageMetaFields.vue"
import type { StudioPage } from "@/types/Studio/StudioPage"

const props = defineProps<{ page: StudioPage | null }>()
const open = defineModel<boolean>("open", { required: true })

const store = useStudioStore()
const title = ref("")
const route = ref("")
const allowGuest = ref(false)
const error = ref("")
const saving = ref(false)

watch(open, (isOpen) => {
	if (!isOpen || !props.page) return
	title.value = props.page.page_title || ""
	route.value = props.page.route
	allowGuest.value = store.pageAllowsGuests(props.page)
	error.value = ""
})

async function save() {
	const page = props.page!
	if (!title.value.trim()) {
		error.value = "Title is required"
		return
	}
	saving.value = true
	error.value = ""
	try {
		const changes = changedFields(page)
		if (Object.keys(changes).length) {
			await store.updatePage(store.appPages[page.name] || page, changes)
			toast.success("Page updated")
		}
		open.value = false
	} catch (saveError: any) {
		error.value = saveError?.messages?.join(", ") || saveError?.message || "Failed to update the page"
	} finally {
		saving.value = false
	}
}

function changedFields(page: StudioPage) {
	const changes: Partial<StudioPage> = {}
	const pageTitle = title.value.trim()
	if (pageTitle !== (page.page_title || "")) changes.page_title = pageTitle
	if (route.value !== page.route) changes.route = route.value
	if (allowGuest.value !== store.pageAllowsGuests(page)) changes.allow_guest = allowGuest.value ? 1 : 0
	return changes
}
</script>
