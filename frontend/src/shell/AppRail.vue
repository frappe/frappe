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

  The list arrives as a PROP rather than off `boot`, which is what lets it change without a
  reload: a save returns the whole `{rail, sidebars}` and the shell swaps it in, so the rail
  re-renders from the same server-resolved list it always renders from and never restacks a
  layer of its own (#42232).
-->
<template>
	<nav class="flex w-52 shrink-0 flex-col gap-1 border-r border-outline-gray-2 p-2">
		<RouterLink
			:to="{ name: 'home' }"
			class="rounded px-2 py-1.5 text-sm font-medium hover:bg-surface-gray-2"
		>
			{{ boot.app ?? "Apps" }}
		</RouterLink>

		<ul class="mt-2 overflow-y-auto">
			<RailItem v-for="node in tree" :key="node.item.key" :node="node" :context="context" />
		</ul>

		<button
			v-if="arrangeable"
			class="mt-auto rounded px-2 py-1 text-left text-xs text-ink-gray-5 hover:bg-surface-gray-2"
			@click="emit('arrange')"
		>
			Arrange
		</button>

		<a
			href="/apps"
			:class="arrangeable ? '' : 'mt-auto'"
			class="rounded px-2 py-1 text-xs text-ink-gray-5 hover:bg-surface-gray-2"
		>
			All apps
		</a>
	</nav>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { RouterLink, useRouter } from "vue-router";
import type { Addresses } from "@/addresses";
import type { Boot, NavigationItem } from "@/boot";
import { itemContext } from "@/navigation/context";
import { buildTree } from "@/navigation/tree";
import RailItem from "./RailItem.vue";

// `arrangeable` is off on the index at `/apps`, which belongs to no app: there is no rail to
// arrange there and no address to name one by, since `boot.app` is null and `boot.navigation`
// is absent. The shell decides it, because the shell is what knows it is on the index.
const props = defineProps<{
	items: NavigationItem[];
	sidebars?: Record<string, NavigationItem[]>;
	arrangeable?: boolean;
}>();
const emit = defineEmits<{ arrange: [] }>();

const boot = inject<Boot>("boot")!;
const addresses = inject<Addresses>("addresses")!;
const router = useRouter();

// The renderers decide what every row does; this file no longer knows one kind from
// another. It used to render `DocType` and drop the other seven, which was #42228's
// skip-a-missing-renderer rule arrived at by accident: there were no renderers at all, so
// there was nothing to miss. There are eight now, each shipped the way an app would ship
// one — the type record plus `frontend/item.js` beside it — so the framework's own kinds
// and a contributed ninth reach this list through the same door (DP2, #42420).
const context = computed(() =>
	itemContext(boot, addresses, router, props.items, props.sidebars ?? {})
);

// `parent_key` is the whole of hierarchy (#42227), and the server sends the tree flat. A
// cycle in it is broken here and reported: every row in one has a parent that is present,
// so the server's orphan promotion passes it through, and rendering the tree would then
// simply omit the rows — a silent drop of authored navigation.
const reportedCycles = new Set<string>();
const tree = computed(() =>
	buildTree(props.items, (key) => {
		// Once per key per page session. `buildTree` is pure and recomputes whenever the list
		// changes, which is what a save does — and a rail that is wrong stays wrong, so the
		// line would repeat on every save without saying anything new.
		if (reportedCycles.has(key)) return;
		reportedCycles.add(key);
		console.error(
			`[frappe] navigation item '${key}' is its own ancestor; it is drawn at the top level.`
		);
	})
);
</script>
