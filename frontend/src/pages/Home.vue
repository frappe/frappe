<!--
  Three things behind one route: the index at `/apps`, an app's home, and a modular app's module list.
-->
<template>
	<PageFrame :title="boot.app ?? 'Apps'" :state="state">
		<div v-if="boot.app" class="py-5">
			<p class="text-sm text-ink-gray-6">
				Served by the framework shell at <code>{{ boot.shell_base }}</code
				>.
			</p>

			<TileGridSkeleton v-if="loading" class="mt-6" />

			<ul v-else-if="modular" class="mt-6 grid max-w-2xl grid-cols-2 gap-2">
				<li v-for="module in modules" :key="module.slug">
					<RouterLink
						:to="routeForModule(module.slug)"
						class="block rounded-4 border border-outline-gray-2 px-3 py-2 text-sm hover:bg-surface-gray-2"
					>
						{{ module.name }}
					</RouterLink>
				</li>
			</ul>

			<ul v-else class="mt-6 grid max-w-2xl grid-cols-2 gap-2">
				<li v-for="entry in entries" :key="entry.doctype">
					<RouterLink
						:to="routeFor(entry.doctype)"
						class="block rounded-4 border border-outline-gray-2 px-3 py-2 text-sm hover:bg-surface-gray-2"
					>
						{{ entry.doctype }}
					</RouterLink>
				</li>
			</ul>
		</div>

		<div v-else class="py-5">
			<ul class="grid max-w-2xl grid-cols-2 gap-2">
				<li v-for="app in boot.apps ?? []" :key="app.app">
					<!-- A real navigation, not a `router.push`: crossing a prefix needs a boot re-fetch. -->
					<a
						:href="app.route"
						class="flex items-center gap-2 rounded-4 border border-outline-gray-2 px-3 py-2 text-sm hover:bg-surface-gray-2"
					>
						<img v-if="app.logo" :src="app.logo" class="size-5" alt="" />
						<span>{{ app.title }}</span>
						<code class="ml-auto text-xs text-ink-gray-5">{{ app.route }}</code>
					</a>
				</li>
			</ul>
		</div>
	</PageFrame>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { RouterLink } from "vue-router";
import type { Boot } from "@/boot";
import type { Addresses } from "@/addresses";
import { routeFor, routeForModule, isModular } from "@/router/routeFor";
import { useContents } from "@/contents";
import PageFrame from "@/shell/PageFrame.vue";
import { failedState, type PageStateValue } from "@/shell/pageState";
import TileGridSkeleton from "./TileGridSkeleton.vue";

const boot = inject<Boot>("boot")!;
const addresses = inject<Addresses>("addresses")!;

const modular = computed(() => isModular(boot));
const { entries, loading, error, reload } = useContents(boot.app);

const state = computed((): PageStateValue | null => {
	if (error.value) return failedState(error.value, reload);
	if (boot.app && !loading.value && !entries.value.length) return { name: "empty" };
	return null;
});

// Derived from what the reader can read: an empty module is a tile that leads nowhere.
const modules = computed(() => {
	const seen = new Map<string, string>();
	for (const entry of entries.value) {
		if (entry.module && !seen.has(entry.module)) {
			seen.set(entry.module, addresses.moduleName(entry.module) ?? entry.module);
		}
	}
	return [...seen]
		.map(([slug, name]) => ({ slug, name }))
		.sort((a, b) => a.name.localeCompare(b.name));
});
</script>
