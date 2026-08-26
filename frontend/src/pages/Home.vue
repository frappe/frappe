<!--
  Two things behind one route, because `/apps` and `/apps/<prefix>` are the same
  document with different boots.

  At `/apps` this is the index: every app whose prefix passes `app_permission`,
  derived from the prefix registry and never from `add_to_apps_screen` -- which means
  tile *visibility*, strictly narrower than access. The index is not a member of its
  own list (#42124).
-->
<template>
	<div class="overflow-y-auto p-8">
		<template v-if="boot.app">
			<h1 class="text-xl font-semibold">{{ boot.app }}</h1>
			<p class="mt-1 text-sm text-ink-gray-6">
				Served by the framework shell at <code>{{ boot.shell_base }}</code
				>.
			</p>
			<ul class="mt-6 grid max-w-2xl grid-cols-2 gap-2">
				<li v-for="slug in slugs" :key="slug">
					<RouterLink
						:to="`/${slug}`"
						class="block rounded border border-outline-gray-2 px-3 py-2 text-sm hover:bg-surface-gray-2"
					>
						{{ boot.doctype_slugs[slug] }}
					</RouterLink>
				</li>
			</ul>
		</template>

		<template v-else>
			<h1 class="text-xl font-semibold">Apps</h1>
			<ul class="mt-6 grid max-w-2xl grid-cols-2 gap-2">
				<li v-for="app in boot.apps ?? []" :key="app.app">
					<!-- A real navigation, not a router.push: crossing a prefix needs a boot
               re-fetch, and the router's base is fixed at construction (#42102). -->
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

const boot = inject<Boot>("boot")!;
const slugs = computed(() => Object.keys(boot.doctype_slugs ?? {}).sort());
</script>
