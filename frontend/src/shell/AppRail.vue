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

  The renderers decide what every row does; this file never knows one kind from
  another. It used to render `DocType` and drop the other seven, which was #42228's
  skip-a-missing-renderer rule arrived at by accident: there were no renderers at all,
  so there was nothing to miss. There are eight now, each shipped the way an app would
  ship one — the type record plus `frontend/item.js` beside it — so the framework's own
  kinds and a contributed ninth reach this list through the same door (DP2, #42420). One
  of those kinds, `Sidebar`, is what makes a rail item LINKED; the panel it opens is the
  shell's, not the rail's, because a rail that owned it would own a surface that outlives
  any one of its rows (#42421).

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
			<NavigationRow
				v-for="node in tree"
				:key="node.item.key"
				:node="node"
				:context="context"
				:current="current"
				:reserve="reserve"
			/>
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
import { RouterLink } from "vue-router";
import type { Boot, NavigationItem } from "@/boot";
import NavigationRow from "@/navigation/NavigationRow.vue";
import { useItemTree } from "@/navigation/useItemTree";
import type { ItemContext } from "@/navigation/types";

// `arrangeable` is off on the index at `/apps`, which belongs to no app: there is no rail to
// arrange there and no address to name one by, since `boot.app` is null and `boot.navigation`
// is absent. The shell decides it, because the shell is what knows it is on the index.
//
// `context` and `current` arrive as props rather than being computed here, and that moved with
// the panel (#42421). The context is composed once per list and the panel draws the same rows
// off the same one; and exactly one row is current across the rail and the panel together, so
// neither surface can work it out alone.
const props = defineProps<{
	items: NavigationItem[];
	context: ItemContext;
	current?: string;
	arrangeable?: boolean;
}>();
const emit = defineEmits<{ arrange: [] }>();

const boot = inject<Boot>("boot")!;

// `parent_key` is the whole of hierarchy (#42227), and the server sends the tree flat. A
// cycle in it is broken and reported by `useItemTree`: every row in one has a parent that is
// present, so the server's orphan promotion passes it through, and rendering the tree would
// then simply omit the rows — a silent drop of authored navigation.
const tree = useItemTree(() => props.items, "the rail");

// Whether an unadorned row holds its icon slot open, decided for the whole container.
const reserve = computed(() => props.items.some((item) => item.icon));
</script>
