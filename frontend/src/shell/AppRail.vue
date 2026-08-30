<!--
  The rail. Shell-owned, and it never disappears.

  It shows the doctypes of the app serving this prefix that the user can READ --
  permission, not declaration. A per-app `rail_doctypes` hook was rejected as strictly
  narrower than what already exists, moving a runtime user choice to a build-time
  author guess (#42102).

  It used to derive that list from `boot.doctype_slugs`, which was the ADDRESS space,
  so the comment above was false: it listed what was addressable, unfiltered. The
  address table is full-bench since #42210 -- 553 doctypes -- so deriving a rail from
  it is no longer merely wrong, it is unusable. It now reads `get_navigation`, which
  is per-app and filtered. See `navigation.ts` for what this is still NOT: the
  navigation model itself, which #42211 left unnamed.
-->
<template>
	<nav class="flex w-52 shrink-0 flex-col gap-1 border-r border-outline-gray-2 p-2">
		<RouterLink
			:to="{ name: 'home' }"
			class="rounded px-2 py-1.5 text-sm font-medium hover:bg-surface-gray-2"
		>
			{{ boot.app ?? "Apps" }}
		</RouterLink>

		<div class="mt-2 overflow-y-auto">
			<!-- An empty rail and a rail that failed to load look identical, and one of
					 them is a lie about the app. -->
			<p v-if="failed" class="px-2 py-1 text-sm text-ink-gray-5">
				Could not load navigation.
			</p>
			<RouterLink
				v-for="entry in entries"
				:key="entry.doctype"
				:to="routeFor(entry.doctype)"
				class="block truncate rounded px-2 py-1 text-sm text-ink-gray-7 hover:bg-surface-gray-2"
			>
				{{ entry.doctype }}
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
import { inject } from "vue";
import { RouterLink } from "vue-router";
import type { Boot } from "@/boot";
import { routeFor } from "@/router/routeFor";
import { useNavigation } from "@/navigation";

const boot = inject<Boot>("boot")!;
const { entries, failed } = useNavigation(boot.app);
</script>
