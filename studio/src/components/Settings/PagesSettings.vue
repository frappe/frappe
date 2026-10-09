<template>
	<ListView
		class="!w-auto"
		:columns="columns"
		:rows="rows"
		row-key="name"
		:options="{ selectable: false, showTooltip: false, emptyState: { title: 'No pages yet' } }"
	>
		<template #cell="{ column, row, item }">
			<div v-if="column.key === 'allow_guest'" class="flex justify-end" @click.stop>
				<Switch
					size="sm"
					:modelValue="item"
					:aria-label="`Allow guest access to ${row.page_title}`"
					@update:modelValue="(value: boolean) => setGuestAccess(row.name, value)"
				/>
			</div>
			<span v-else class="truncate text-base" :title="item">{{ item }}</span>
		</template>
	</ListView>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Switch } from "frappe-ui"
import { ListView } from "frappe-ui/experimental"
import useStudioStore from "@/stores/studioStore"
import type { StudioPage } from "@/types/Studio/StudioPage"

const store = useStudioStore()

const columns = [
	{ label: "Title", key: "page_title", width: "40%" },
	{ label: "Route", key: "route", width: "40%" },
	{ label: "Guest Access", key: "allow_guest", align: "right" },
]

const rows = computed(() =>
	Object.values(store.appPages).map((page) => ({
		name: page.name,
		page_title: page.page_title,
		route: page.route,
		allow_guest: allowsGuests(page),
	})),
)

function allowsGuests(page: StudioPage) {
	const isActive = store.activePage?.name === page.name
	return Boolean(isActive ? store.activePage?.allow_guest : page.allow_guest)
}

function setGuestAccess(pageName: string, allow: boolean) {
	store.updatePage(store.appPages[pageName], "allow_guest", allow ? 1 : 0)
}
</script>
