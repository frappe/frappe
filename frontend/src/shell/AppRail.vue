<!--
  The rail. Shell-owned, and it never disappears.

  It renders `boot.navigation.rail` — the app's own rows, the site's arrangement and
  this person's, already merged by the server (#42232). The browser never restacks
  those layers and holds no permission logic: an item that reached this list is one
  this person may be offered.

  Two data sources have gone before this one. It first derived from
  `boot.doctype_slugs`, which was the ADDRESS space, so "permission, not declaration"
  was false — it listed what was addressable, unfiltered. It then fetched the endpoint
  now called `get_contents`, which was per-app and filtered, and made the claim true.
  It is in boot for a reason neither of those had: a rail click must cost no request,
  which a fetched rail cannot promise. What an app CONTAINS is still fetched, by the app home
  and the module page that show it (`contents.ts`, #42357).

  There is no "could not load" state left. Navigation arrives with boot, and a boot
  that fails never mounts a shell for this to render in.

  An app that ships no rail rows still gets a rail: its own doctypes, permission-
  filtered, exactly the list this showed before. So the rail's appearance changes when
  an app ships rows and not when this lands (#42356).

  Some of these rows may belong to another app entirely — one that ships a `Rail`
  record naming this app in `extends`. Nothing here can tell, and nothing here should:
  the server merged them into the base before the layers went on, so they arrive as
  ordinary items in one ordered list (#42364).
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
			<component
				v-for="item in doctypeItems"
				:key="item.key"
				:is="item.url ? 'a' : RouterLink"
				:to="item.url ? undefined : routeFor(item.link_to!)"
				:href="item.url"
				class="block truncate rounded px-2 py-1 text-sm text-ink-gray-7 hover:bg-surface-gray-2"
			>
				<!-- An item nobody labelled falls back to its destination, which is what a
						 derived rail row is: an address and no authored presentation. -->
				{{ item.label ?? item.link_to }}
			</component>
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
import { routeFor } from "@/router/routeFor";

const boot = inject<Boot>("boot")!;

// `DocType` only, for now. A kind is two files — a type record and the JS that says
// what an item of that kind does on click (#42228) — and none of the other seven kinds
// has its half yet, so a row of one is a row this cannot render. Skipping it is what
// #42228 chose for a missing renderer, and no app ships such a row today: every rail on
// the branch is derived, and derivation produces `DocType` items and nothing else.
// Renderers, and a rail that draws sections and opens sidebars, are the walking
// skeleton's (#42233).
//
// A row carrying a `url` is rendered as a plain `<a>` above. That is a contributed item
// whose app said `switches_app`, and leaving a prefix is a full document load — a
// `RouterLink` would resolve it against this document's router, which cannot reach
// another prefix at all. A contributed item that does NOT switch is an ordinary
// `RouterLink` like any other, and needs nothing here: addresses are bench-wide, so a
// foreign doctype opens under the host's prefix (#42364).
const doctypeItems = computed(() =>
	(boot.navigation?.rail ?? []).filter((item) => item.item_type === "DocType" && item.link_to)
);
</script>
