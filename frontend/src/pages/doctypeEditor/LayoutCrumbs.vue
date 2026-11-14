<!-- The header's crumbs, in frappe-ui Breadcrumbs' markup, ending in the layout menu's crumb. -->
<template>
	<nav
		class="flex min-w-0 items-center overflow-hidden whitespace-nowrap leading-tighter"
		:aria-label="__('Breadcrumbs')"
		data-crumbs
	>
		<template v-for="(crumb, index) in crumbs" :key="index">
			<component
				:is="crumb.route ? RouterLink : 'button'"
				v-bind="crumb.route ? { to: crumb.route } : { type: 'button' }"
				class="flex items-center rounded-4 px-0.5 py-1 text-lg-medium leading-tighter"
				:class="[
					crumb.shrinks ? 'min-w-0' : 'shrink-0',
					draft && index === crumbs.length - 1
						? 'text-ink-gray-9'
						: 'text-ink-gray-5 hover:text-ink-gray-7',
				]"
				@click="crumb.onClick?.()"
			>
				<span class="truncate" :title="crumb.label">{{ crumb.label }}</span>
			</component>
			<span
				v-if="!draft || index < crumbs.length - 1"
				class="mx-0.5 text-base text-ink-gray-4"
				aria-hidden="true"
				>/</span
			>
		</template>
		<LayoutMenu v-if="canvas" :canvas="canvas" />
		<span
			v-else-if="!draft"
			class="px-0.5 py-1 text-lg-medium leading-tighter text-ink-gray-9"
			data-layout-crumb
			>{{ __("Details") }}</span
		>
	</nav>
</template>

<script lang="ts">
import type { RouteLocationRaw } from "vue-router";

export interface Crumb {
	label: string;
	route?: RouteLocationRaw;
	onClick?: () => void;
	/** The one crumb that gives way when the header is narrow. */
	shrinks?: boolean;
}
</script>

<script setup lang="ts">
import { RouterLink } from "vue-router";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import LayoutMenu from "./LayoutMenu.vue";

/** A draft has no saved layout to name. */
defineProps<{ crumbs: Crumb[]; canvas: DesignCanvas | null; draft?: boolean }>();
</script>
