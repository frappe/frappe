<!--
  A module's landing page, reachable only under a modular prefix. Permission-filtered, unlike the
  address space.
-->
<template>
	<div class="overflow-y-auto p-8">
		<h1 class="text-xl font-semibold">{{ title }}</h1>
		<p class="mt-1 text-sm text-ink-gray-6">
			<!-- "0 doctypes you can read" is a real answer, so it must not also be what a pending fetch looks like. -->
			<template v-if="loading">Loading…</template>
			<template v-else-if="failed"> Could not load this module's doctypes. </template>
			<template v-else>
				{{ entries.length }} doctype{{ entries.length === 1 ? "" : "s" }} you can read.
			</template>
		</p>

		<ul class="mt-6 grid max-w-2xl grid-cols-2 gap-2">
			<li v-for="entry in entries" :key="entry.doctype">
				<RouterLink
					:to="routeFor(entry.doctype)"
					class="block rounded border border-outline-gray-2 px-3 py-2 text-sm hover:bg-surface-gray-2"
				>
					{{ entry.doctype }}
				</RouterLink>
			</li>
		</ul>
	</div>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { RouterLink, useRoute } from "vue-router";
import type { Boot } from "@/boot";
import type { Addresses } from "@/addresses";
import { routeFor } from "@/router/routeFor";
import { useContents } from "@/contents";

const boot = inject<Boot>("boot")!;
const addresses = inject<Addresses>("addresses")!;
const route = useRoute();

const moduleSlug = computed(() => String(route.params.module ?? ""));
const { entries, loading, failed } = useContents(boot.app, moduleSlug);
// The slug is the address; the name is what a human reads.
const title = computed(() => addresses.moduleName(moduleSlug.value) ?? moduleSlug.value);
</script>
