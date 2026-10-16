<template>
	<div class="[&_[data-slot=description]]:text-ink-gray-5">
		<div class="flex flex-row flex-wrap gap-4">
			<PageMetaFields
				:appRoute="app?.route"
				:title="page.page_title || ''"
				:route="page.route"
				:allowGuest="Boolean(page.allow_guest)"
				@update:title="(value: string) => store.updateActivePage('page_title', value)"
				@update:route="(value: string) => store.updateActivePage('route', value)"
				@update:allowGuest="(value: boolean) => store.updateActivePage('allow_guest', value ? 1 : 0)"
			>
				<Code
					v-if="showTabTitle"
					:autofocus="!page.tab_title"
					v-model="tabTitle"
					label="Tab Title"
					isFormInput
					valueMode="text"
					:emitOnChange="true"
					:showLineNumbers="false"
					:lineWrapping="true"
					class="inline-expression"
					:placeholder="page.page_title"
					description="Defaults to the page title. Use {{ }} for dynamic data"
					:completions="dynamicValueCompletions"
					:overrideCompletions="true"
				/>
				<button
					v-else
					class="-mt-2 flex items-center gap-1 self-start text-sm text-ink-gray-5 hover:text-ink-gray-7"
					@click="showTabTitle = true"
				>
					<span class="lucide-plus h-3 w-3" />
					Use a different tab title
				</button>
			</PageMetaFields>

			<!-- Dynamic Route Variables: design-time test values for params like /articles/:category -->
			<CollapsibleSection
				v-if="routeVariableNames.length"
				sectionName="Route Variables"
				class="w-full [&>div>div]:!mb-0 [&>div>h3]:!text-sm [&>div>h3]:!text-ink-gray-7"
			>
				<div v-for="name in routeVariableNames" :key="name" class="w-full">
					<Input
						:label="name.replace(/_/g, ' ')"
						type="text"
						variant="outline"
						class="w-full"
						:hideClearButton="true"
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
import { computed, ref } from "vue"
import { watchDebounced } from "@vueuse/core"
import useStudioStore from "@/stores/studioStore"
import type { StudioPage } from "@/types/Studio/StudioPage"
import type { StudioApp } from "@/types/Studio/StudioApp"
import Input from "@/components/Input.vue"
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import PageMetaFields from "@/components/PageMetaFields.vue"
import Code from "@/components/Code.vue"
import { getRouteVariables } from "@/utils/helpers"
import { useDynamicValueCompletions } from "@/utils/completions/useStudioCompletions"

const store = useStudioStore()
const props = defineProps<{
	page: StudioPage
	app: StudioApp
}>()

const routeVariableNames = computed(() => getRouteVariables(props.page.route || ""))

const getDynamicValueCompletions = useDynamicValueCompletions()
const dynamicValueCompletions = getDynamicValueCompletions()
// saved while typing: closing the popover unmounts the editor before it blurs
const tabTitle = ref(props.page.tab_title || "")
const showTabTitle = ref(Boolean(props.page.tab_title))
const pageName = props.page.name
watchDebounced(
	tabTitle,
	(value) => {
		// a save that fires after another page opened must not land on it
		if (store.activePage?.name === pageName) store.updateActivePage("tab_title", value)
	},
	{ debounce: 500 },
)
</script>
