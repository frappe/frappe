<!--
  Three things behind one route: the index at `/apps`, an app's home, and a modular app's module list.
-->
<template>
	<div class="overflow-y-auto p-8">
		<template v-if="boot.app">
			<h1 class="text-xl font-semibold">{{ boot.app }}</h1>
			<p class="mt-1 text-sm text-ink-gray-6">
				Served by the framework shell at <code>{{ boot.shell_base }}</code
				>.
			</p>

			<!-- An empty grid and one that failed to load must not look the same. -->
			<p v-if="failed" class="mt-6 text-sm text-ink-gray-6">
				Could not load this app's navigation.
			</p>

			<ul v-else-if="modular" class="mt-6 grid max-w-2xl grid-cols-2 gap-2">
				<li v-for="module in modules" :key="module.slug">
					<RouterLink
						:to="routeForModule(module.slug)"
						class="block rounded border border-outline-gray-2 px-3 py-2 text-sm hover:bg-surface-gray-2"
					>
						{{ module.name }}
					</RouterLink>
				</li>
			</ul>

			<ul v-else class="mt-6 grid max-w-2xl grid-cols-2 gap-2">
				<li v-for="entry in entries" :key="entry.doctype">
					<RouterLink
						:to="routeFor(entry.doctype)"
						class="block rounded border border-outline-gray-2 px-3 py-2 text-sm hover:bg-surface-gray-2"
					>
						{{ entry.doctype }}
					</RouterLink>
				</li>
			</ul>
		</template>

		<template v-else>
			<h1 class="text-xl font-semibold">Apps</h1>
			<ul class="mt-6 grid max-w-2xl grid-cols-2 gap-2">
				<li v-for="app in boot.apps ?? []" :key="app.app">
					<!-- A real navigation, not a `router.push`: crossing a prefix needs a boot re-fetch. -->
					<a
						:href="app.route"
						class="flex items-center gap-2 rounded border border-outline-gray-2 px-3 py-2 text-sm hover:bg-surface-gray-2"
					>
						<img v-if="app.logo" :src="app.logo" class="size-5" alt="" />
						<span>{{ app.title }}</span>
						<code class="ml-auto text-xs text-ink-gray-5">{{ app.route }}</code>
					</a>
				</li>
			</ul>
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { RouterLink } from "vue-router";
import type { Boot } from "@/boot";
import type { Addresses } from "@/addresses";
import { routeFor, routeForModule, isModular } from "@/router/routeFor";
import { useContents } from "@/contents";

const boot = inject<Boot>("boot")!;
const addresses = inject<Addresses>("addresses")!;

const modular = computed(() => isModular(boot));
const { entries, failed } = useContents(boot.app);

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
