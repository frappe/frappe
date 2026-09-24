<!--
  A module's landing page, reachable only under a modular prefix. Permission-filtered, unlike the
  address space.
-->
<template>
	<PageFrame :title="title">
		<!-- "0 doctypes you can read" is a real answer, so it must not also be what a pending fetch looks like.
		     The bar sits inline in a line of the same text size, so the count lands at the same height. -->
		<div v-if="loading" class="pt-5 text-sm">
			<Skeleton class="inline-block h-3 w-40 rounded-1 align-middle" />
		</div>
		<p v-else class="pt-5 text-sm text-ink-gray-6">
			<template v-if="failed"> Could not load this module's doctypes. </template>
			<template v-else>
				{{ entries.length }} doctype{{ entries.length === 1 ? "" : "s" }} you can read.
			</template>
		</p>

		<TileGridSkeleton v-if="loading" class="my-6" />
		<ul v-else class="my-6 grid max-w-2xl grid-cols-2 gap-2">
			<li v-for="entry in entries" :key="entry.doctype">
				<RouterLink
					:to="routeFor(entry.doctype)"
					class="block rounded-4 border border-outline-gray-2 px-3 py-2 text-sm hover:bg-surface-gray-2"
				>
					{{ entry.doctype }}
				</RouterLink>
			</li>
		</ul>
	</PageFrame>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { Skeleton } from "frappe-ui";
import type { Boot } from "@/boot";
import type { Addresses } from "@/addresses";
import { routeFor } from "@/router/routeFor";
import { useContents } from "@/contents";
import PageFrame from "@/shell/PageFrame.vue";
import TileGridSkeleton from "./TileGridSkeleton.vue";

const boot = inject<Boot>("boot")!;
const addresses = inject<Addresses>("addresses")!;
const route = useRoute();

const moduleSlug = computed(() => String(route.params.module ?? ""));
const { entries, loading, failed } = useContents(boot.app, moduleSlug);
// The slug is the address; the name is what a human reads.
const title = computed(() => addresses.moduleName(moduleSlug.value) ?? moduleSlug.value);
</script>
