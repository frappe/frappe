<!--
  The panel a linked rail item opens.

  The other half of charter point 1: a rail item is independent or LINKED, and this is
  what linked means on screen. It draws `Navigation Item` rows — the same rows, the same
  renderers and the same component as the rail, because they are two presentations of one
  model and never two models (#42227).

  NOTHING OPENS IT BY CLICKING. The address does. A rail item of type `Sidebar` resolves to
  the first destination inside its sidebar and carries the sidebar's scrubbed key alongside
  (`sidebar/frontend/item.js`), so following one is ordinary navigation and the panel that
  appears is the shell reading the new address back (charter point 7,
  `navigation/current.ts`). There is no selection stored anywhere, which is why pasting a
  URL into a fresh tab lands on the same shell as clicking to it.

  The empty panel does not exist. A sidebar that resolved to nothing is ABSENT from
  `boot.navigation.sidebars` rather than empty (#42356), its rail item then renders as an
  independent one, and with no rail item naming it there is no address that can open it
  (#42357). The `v-if` in the shell is the last of three fences, not the first.

  The title is the rail item's AUTHORED label, and an unlabelled item leaves the panel with
  no heading at all. The payload allows nothing else: `sidebars` is keyed by scrubbed address
  and carries rows rather than a record, so there is no `Sidebar` title to read — and
  `labelOf`'s fallbacks all end at `link_to`, which for this kind is the scrubbed address. A
  heading reading `module_def_accounts` is worse than none, and the rail item above the panel
  is highlighted either way.
-->
<template>
	<aside class="flex w-56 shrink-0 flex-col gap-1 border-r border-outline-gray-2 p-2">
		<p v-if="title" class="truncate px-2 py-1.5 text-sm font-medium text-ink-gray-8">
			{{ title }}
		</p>

		<ul class="overflow-y-auto">
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
	</aside>
</template>

<script setup lang="ts">
import type { NavigationItem } from "@/boot";
import NavigationRow from "@/navigation/NavigationRow.vue";
import { useItemTree } from "@/navigation/useItemTree";
import { useIconSlot } from "@/navigation/iconSlot";
import type { ItemContext } from "@/navigation/types";

// `address` is the scrubbed key, and it is a prop because it is also what the arrangement
// endpoints take for a `Sidebar` — they read the `(link_doctype, link_to)` pair back off the
// standard record, since unscrubbing is not a function (`arrangement.py`). So the panel is an
// arrangeable container on the same terms as the rail, with the same three endpoints.
const props = defineProps<{
	address: string;
	items: NavigationItem[];
	context: ItemContext;
	title?: string;
	current?: string;
	arrangeable?: boolean;
}>();
const emit = defineEmits<{ arrange: [] }>();

const tree = useItemTree(
	() => props.items,
	() => `the ${props.address} sidebar`
);

const reserve = useIconSlot(
	() => props.items,
	() => props.context
);
</script>
