<template>
	<div>
		<div class="flex flex-row flex-wrap gap-4">
			<Input
				label="App Title"
				type="text"
				variant="outline"
				class="w-full"
				:modelValue="page.page_title"
				@update:modelValue="(val: string) => store.updateActivePage('page_title', val)"
			/>

			<div class="flex w-full flex-col gap-1">
				<label class="block text-xs text-gray-600">App Route</label>
				<div class="relative flex items-stretch">
					<Input
						type="text"
						variant="outline"
						class="w-full [&>div>input]:pl-[100px]"
						@input="(val: string) => (page.route = val)"
						:modelValue="pageRoute"
						:hideClearButton="true"
						@update:modelValue="(val: string) => store.updateActivePage('route', `studio-app/${val}`)"
					/>

					<!-- App Route Prefix -->
					<div
						class="absolute bottom-[1px] left-[1px] flex items-center rounded-l-[0.4rem] bg-gray-100 text-gray-700"
					>
						<span class="flex h-[1.6rem] items-center text-nowrap px-2 py-0 text-base"> studio-app/ </span>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import useStore from "@/store"
import { StudioPage } from "@/types"
import Input from "@/components/Input.vue"

const store = useStore()
const props = defineProps<{
	page: StudioPage
}>()

const pageRoute = computed(() => {
	return props.page.route.replace("studio-app/", "")
})
</script>
