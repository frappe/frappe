<template>
	<List :columns="['minmax(0,1fr)', 'minmax(0,1fr)', '120px']" :row-height="44">
		<ListHeader>
			<ListHeaderCell>Title</ListHeaderCell>
			<ListHeaderCell>Route</ListHeaderCell>
			<ListHeaderCell class="justify-end">Guest Access</ListHeaderCell>
		</ListHeader>
		<ListRows :items="pages" v-slot="{ item: page }">
			<ListRow>
				<ListCell>
					<Input
						:modelValue="page.page_title"
						:hideClearButton="true"
						:aria-label="`Title of ${page.page_title}`"
						@update:modelValue="(value: string) => update(page, 'page_title', value)"
					/>
				</ListCell>
				<ListCell>
					<Input
						:modelValue="page.route"
						:hideClearButton="true"
						:aria-label="`Route of ${page.page_title}`"
						@update:modelValue="(value: string) => update(page, 'route', withLeadingSlash(value))"
					/>
				</ListCell>
				<ListCell class="justify-end">
					<Switch
						size="sm"
						:modelValue="allowsGuests(page)"
						:aria-label="`Allow guest access to ${page.page_title}`"
						@update:modelValue="(value: boolean) => update(page, 'allow_guest', value ? 1 : 0)"
					/>
				</ListCell>
			</ListRow>
		</ListRows>
	</List>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Switch, toast } from "frappe-ui"
import { List, ListCell, ListHeader, ListHeaderCell, ListRow, ListRows } from "frappe-ui/list"
import Input from "@/components/Input.vue"
import useStudioStore from "@/stores/studioStore"
import type { StudioPage } from "@/types/Studio/StudioPage"

const store = useStudioStore()
const pages = computed(() => Object.values(store.appPages))

function allowsGuests(page: StudioPage) {
	const isActive = store.activePage?.name === page.name
	return Boolean(isActive ? store.activePage?.allow_guest : page.allow_guest)
}

function update(page: StudioPage, field: "page_title" | "route" | "allow_guest", value: string | number) {
	store.updatePage(page, field, value).catch((error: any) => {
		toast.error(error?.messages?.join(", ") || error?.message || "Failed to update the page")
	})
}

function withLeadingSlash(route: string) {
	return route.startsWith("/") ? route : `/${route}`
}
</script>
