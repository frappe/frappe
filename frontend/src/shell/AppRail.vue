<!--
  The rail, shell-owned and always present. It draws the server-merged list it is handed and
  holds no permission logic; the renderers decide what every row does.
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
				:sections="sections"
			/>
		</ul>

		<!-- One group, so `mt-auto` sits in one place however many controls are on. -->
		<div class="mt-auto flex flex-col">
			<button
				v-if="arrangeable"
				class="rounded px-2 py-1 text-left text-xs text-ink-gray-5 hover:bg-surface-gray-2"
				@click="emit('arrange')"
			>
				Arrange
			</button>

			<button
				v-if="shareLink"
				class="rounded px-2 py-1 text-left text-xs text-ink-gray-5 hover:bg-surface-gray-2"
				@click="copyLink"
			>
				{{ copied ? "Link copied" : "Copy link" }}
			</button>

			<a
				href="/apps"
				class="rounded px-2 py-1 text-xs text-ink-gray-5 hover:bg-surface-gray-2"
			>
				All apps
			</a>
		</div>
	</nav>
</template>

<script setup lang="ts">
import { inject, onBeforeUnmount, ref } from "vue";
import { RouterLink } from "vue-router";
import type { Boot, NavigationItem } from "@/boot";
import NavigationRow from "@/navigation/NavigationRow.vue";
import type { SectionMemory } from "@/navigation/sectionMemory";
import { useItemTree } from "@/navigation/useItemTree";
import { useIconSlot } from "@/navigation/iconSlot";
import type { ItemContext } from "@/navigation/types";

// The shell decides `arrangeable` (off on the index), `current` (one row across rail and panel)
// and `shareLink` (it knows whether the panel needs naming); a context is composed once per list.
const props = defineProps<{
	items: NavigationItem[];
	context: ItemContext;
	current?: string;
	sections?: SectionMemory;
	arrangeable?: boolean;
	shareLink?: string;
}>();
const emit = defineEmits<{ arrange: [] }>();

const boot = inject<Boot>("boot")!;

// Confirmation in the button itself: there is no toast in the shell to borrow.
const copied = ref(false);
let clearCopied: ReturnType<typeof setTimeout> | undefined;

async function copyLink() {
	if (!props.shareLink) return;

	try {
		await navigator.clipboard.writeText(props.shareLink);
	} catch {
		// Denied, or an insecure origin with no `navigator.clipboard`. Nothing was copied, so claim nothing.
		return;
	}

	copied.value = true;
	clearTimeout(clearCopied);
	clearCopied = setTimeout(() => (copied.value = false), 1500);
}

onBeforeUnmount(() => clearTimeout(clearCopied));

// A `parent_key` cycle passes the server's orphan check; `useItemTree` breaks and reports it.
const tree = useItemTree(() => props.items, "the rail");

const reserve = useIconSlot(
	() => props.items,
	() => props.context
);
</script>
