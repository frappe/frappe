<template>
	<header
		class="sticky top-0 z-10 flex w-full flex-col items-center border-b border-gray-300 bg-white p-5 shadow-sm"
	>
		<div class="w-full">
			<div class="flex w-full items-center justify-center">
				<component
					v-if="!hideBackButton"
					:is="LucideChevronLeft"
					class="absolute left-4 h-6 w-6 cursor-pointer text-gray-600 hover:text-gray-900"
					@click="() => $router.back()"
				/>
				<div class="flex cursor-pointer items-center justify-center gap-2">
					<template v-if="!hideLogo">
						<div v-if="logoSVG" class="flex items-center gap-2">
							<span v-html="logoSVG" />
						</div>
						<AppLogo v-else class="h-6 w-6" />
					</template>
					<h1 v-if="title" class="text-xl font-semibold leading-5 text-gray-800">{{ title }}</h1>
				</div>

				<slot></slot>
			</div>
		</div>
	</header>
</template>

<script setup lang="ts">
import AppLogo from "../Icons/AppLogo.vue"
import LucideChevronLeft from "~icons/lucide/chevron-left"
import type { AppHeaderProps } from "@/types/studio_components/AppHeader"

defineProps<AppHeaderProps>()
</script>
