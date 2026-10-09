<template>
	<div class="flex flex-col gap-3">
		<div class="flex flex-col gap-1">
			<span class="text-md-semibold text-ink-gray-9">Guest Access</span>
			<span class="text-p-sm text-ink-gray-6">Pages anyone can open without logging in</span>
		</div>
		<div class="flex flex-col divide-y divide-outline-gray-1">
			<div v-for="page in pages" :key="page.name" class="flex items-center justify-between gap-5 py-2.5">
				<div class="flex min-w-0 flex-col">
					<span class="truncate text-base text-ink-gray-8">{{ page.page_title }}</span>
					<span class="truncate text-p-sm text-ink-gray-5">{{ page.route }}</span>
				</div>
				<Switch
					size="sm"
					:modelValue="allowsGuests(page)"
					@update:modelValue="(value: boolean) => store.updatePage(page, 'allow_guest', value ? 1 : 0)"
				/>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Switch } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"
import type { StudioPage } from "@/types/Studio/StudioPage"

const store = useStudioStore()
const pages = computed(() => Object.values(store.appPages))

function allowsGuests(page: StudioPage) {
	const isActive = store.activePage?.name === page.name
	return Boolean(isActive ? store.activePage?.allow_guest : page.allow_guest)
}
</script>
