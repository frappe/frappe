<template>
	<div>
	<List :columns="['minmax(0,1fr)', 'minmax(0,1fr)', '120px']" :row-height="44" class="[--list-row-padding-x:0.75rem]">
		<ListHeader>
			<ListHeaderCell>Title</ListHeaderCell>
			<ListHeaderCell>Route</ListHeaderCell>
			<ListHeaderCell class="justify-end">Guest Access</ListHeaderCell>
		</ListHeader>
		<ListRows :items="pages" v-slot="{ item: page }">
			<ListRow class="hover:bg-surface-gray-1 sm:rounded-[10px]">
				<button
					type="button"
					class="absolute inset-0 sm:rounded-[10px]"
					:aria-label="`Edit ${page.page_title}`"
					@click="editPage(page)"
				/>
				<ListCell>
					<span class="truncate text-base text-ink-gray-8">{{ page.page_title }}</span>
				</ListCell>
				<ListCell>
					<span class="truncate text-base text-ink-gray-6">{{ page.route }}</span>
				</ListCell>
				<ListCell class="justify-end">
					<Switch
						size="sm"
						class="relative"
						:modelValue="store.pageAllowsGuests(page)"
						:aria-label="`Allow guest access to ${page.page_title}`"
						@update:modelValue="(value: boolean) => setGuestAccess(page, value)"
					/>
				</ListCell>
			</ListRow>
		</ListRows>
	</List>
	<EditPageDialog v-model:open="showEditDialog" :page="selectedPage" />
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Switch, toast } from "frappe-ui"
import { List, ListCell, ListHeader, ListHeaderCell, ListRow, ListRows } from "frappe-ui/list"
import EditPageDialog from "@/components/Settings/EditPageDialog.vue"
import useStudioStore from "@/stores/studioStore"
import type { StudioPage } from "@/types/Studio/StudioPage"

const store = useStudioStore()
const pages = computed(() => Object.values(store.appPages))
const selectedPage = ref<StudioPage | null>(null)
const showEditDialog = ref(false)

function editPage(page: StudioPage) {
	selectedPage.value = page
	showEditDialog.value = true
}

function setGuestAccess(page: StudioPage, allow: boolean) {
	store.updatePage(page, "allow_guest", allow ? 1 : 0).catch((error: any) => {
		toast.error(error?.messages?.join(", ") || error?.message || "Failed to update the page")
	})
}
</script>
