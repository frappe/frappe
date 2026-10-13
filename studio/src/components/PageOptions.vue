<template>
	<div>
		<div class="flex flex-row flex-wrap gap-4">
			<PageMetaFields
				:appRoute="app?.route"
				:title="page.page_title || ''"
				:route="page.route"
				:allowGuest="Boolean(page.allow_guest)"
				@update:title="(value: string) => store.updateActivePage('page_title', value)"
				@update:route="(value: string) => store.updateActivePage('route', value)"
				@update:allowGuest="(value: boolean) => store.updateActivePage('allow_guest', value ? 1 : 0)"
			/>

			<!-- Dynamic Route Variables: design-time test values for params like /articles/:category -->
			<CollapsibleSection
				v-if="routeVariableNames.length"
				sectionName="Route Variables"
				class="mt-2 w-full [&>div>h3]:!text-base [&>div>h3]:!text-ink-gray-5"
			>
				<div v-for="name in routeVariableNames" :key="name" class="w-full">
					<Input
						:label="name.replace(/_/g, ' ')"
						type="text"
						variant="outline"
						class="w-full"
						:placeholder="`Test value for :${name}`"
						:modelValue="store.routeVariables[name] || ''"
						@update:modelValue="(val: string) => store.setRouteVariable(name, val)"
					/>
				</div>
			</CollapsibleSection>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import useStudioStore from "@/stores/studioStore"
import type { StudioPage } from "@/types/Studio/StudioPage"
import type { StudioApp } from "@/types/Studio/StudioApp"
import Input from "@/components/Input.vue"
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import PageMetaFields from "@/components/PageMetaFields.vue"
import { getRouteVariables } from "@/utils/helpers"

const store = useStudioStore()
const props = defineProps<{
	page: StudioPage
	app: StudioApp
}>()

const routeVariableNames = computed(() => getRouteVariables(props.page.route || ""))
</script>
