<!--
  The rail. Shell-owned, and it never disappears.

  It shows the doctypes the user can read at this prefix -- permission, not
  declaration. A per-app `rail_doctypes` hook was rejected as strictly narrower than
  what already exists, moving a runtime user choice to a build-time author guess
  (#42102).
-->
<template>
	<nav class="flex w-52 shrink-0 flex-col gap-1 border-r border-outline-gray-2 p-2">
		<RouterLink
			:to="{ name: 'home' }"
			class="rounded px-2 py-1.5 text-sm font-medium hover:bg-surface-gray-2"
		>
			{{ boot.app ? title : "Apps" }}
		</RouterLink>

		<div class="mt-2 overflow-y-auto">
			<RouterLink
				v-for="slug in slugs"
				:key="slug"
				:to="`/${slug}`"
				class="block truncate rounded px-2 py-1 text-sm text-ink-gray-7 hover:bg-surface-gray-2"
			>
				{{ boot.doctype_slugs[slug] }}
			</RouterLink>
		</div>

		<a
			href="/apps"
			class="mt-auto rounded px-2 py-1 text-xs text-ink-gray-5 hover:bg-surface-gray-2"
		>
			All apps
		</a>
	</nav>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { RouterLink } from "vue-router";
import type { Boot } from "@/boot";

const boot = inject<Boot>("boot")!;
const title = computed(() => boot.app ?? "Apps");
const slugs = computed(() => Object.keys(boot.doctype_slugs ?? {}).sort());
</script>
