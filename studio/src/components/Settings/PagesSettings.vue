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
					<span class="truncate text-base text-ink-gray-8">{{ page.page_title }}</span>
				</ListCell>
				<ListCell>
					<span class="truncate text-base text-ink-gray-7">{{ page.route }}</span>
				</ListCell>
				<ListCell class="justify-end">
					<Switch
						size="sm"
						:modelValue="allowsGuests(page)"
						:aria-label="`Allow guest access to ${page.page_title}`"
						@update:modelValue="(value: boolean) => store.updatePage(page, 'allow_guest', value ? 1 : 0)"
					/>
				</ListCell>
			</ListRow>
		</ListRows>
	</List>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Switch } from "frappe-ui"
import { List, ListCell, ListHeader, ListHeaderCell, ListRow, ListRows } from "frappe-ui/list"
import useStudioStore from "@/stores/studioStore"
import type { StudioPage } from "@/types/Studio/StudioPage"

const store = useStudioStore()
const pages = computed(() => Object.values(store.appPages))

function allowsGuests(page: StudioPage) {
	const isActive = store.activePage?.name === page.name
	return Boolean(isActive ? store.activePage?.allow_guest : page.allow_guest)
}
</script>
