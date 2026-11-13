<!-- The header's crumbs, in frappe-ui Breadcrumbs' markup, ending in the layout menu's crumb. -->
<template>
	<nav
		class="flex min-w-0 items-center whitespace-nowrap leading-tighter"
		:aria-label="__('Breadcrumbs')"
		data-crumbs
	>
		<template v-for="crumb in crumbs" :key="crumb.label">
			<component
				:is="crumb.route ? RouterLink : 'button'"
				v-bind="crumb.route ? { to: crumb.route } : { type: 'button' }"
				class="flex shrink-0 items-center rounded-4 px-0.5 py-1 text-lg-medium leading-tighter text-ink-gray-5 hover:text-ink-gray-7"
				@click="crumb.onClick?.()"
			>
				{{ crumb.label }}
			</component>
			<span class="mx-0.5 text-base text-ink-gray-4" aria-hidden="true">/</span>
		</template>
		<LayoutMenu v-if="canvas" :canvas="canvas" />
	</nav>
</template>

<script lang="ts">
import type { RouteLocationRaw } from "vue-router";

export interface Crumb {
	label: string;
	route?: RouteLocationRaw;
	onClick?: () => void;
}
</script>

<script setup lang="ts">
import { RouterLink } from "vue-router";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import LayoutMenu from "./LayoutMenu.vue";

defineProps<{ crumbs: Crumb[]; canvas: DesignCanvas | null }>();
</script>
