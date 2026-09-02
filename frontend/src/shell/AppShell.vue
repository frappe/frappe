<!--
  The shell's own surface.

  The line the contribution contract draws: the shell owns everything that must look
  the same in every app; an app contributes only INSIDE a routed view. There is no
  contributeSidebarItem, no contributeCommand, no shell-level hook of any kind
  (#42072).

  Both halves go to the rail, and that is why they are one prop pair rather than two
  components: a rail item of type `Sidebar` is what makes an item LINKED (#42227), and it
  resolves its own destination out of the sidebar it opens — so the rail cannot draw the
  rail without holding the sidebars too. The panel that shows one is #42421's.

  Navigation lives here, one level above the rail, because it is not the rail's. A save
  returns the WHOLE `{rail, sidebars}` for the prefix and the client swaps it in wholesale
  (#42363) — so hiding a rail item of type `Sidebar` changes which sidebars are reachable, and
  the one place that knows about both is this one. `boot.navigation` is kept in step for anything
  that reads boot directly; the reactive copy is what renders.
-->
<template>
	<div class="flex h-screen w-screen bg-surface-white text-ink-gray-9">
		<AppRail
			:items="navigation.rail"
			:sidebars="navigation.sidebars"
			:arrangeable="!!boot.app"
			@arrange="arranging = true"
		/>
		<main class="flex min-w-0 flex-1 flex-col">
			<RouterView />
		</main>
		<ArrangementEditor
			v-if="arranging && boot.app"
			container="Rail"
			:address="boot.app"
			title="Arrange this rail"
			@saved="replace"
			@close="arranging = false"
		/>
	</div>
</template>

<script setup lang="ts">
import { inject, ref } from "vue";
import { RouterView } from "vue-router";
import type { Boot, Navigation } from "@/boot";
import AppRail from "./AppRail.vue";
import ArrangementEditor from "./ArrangementEditor.vue";

const boot = inject<Boot>("boot")!;

const arranging = ref(false);
const navigation = ref<Navigation>(boot.navigation ?? { rail: [], sidebars: {} });

function replace(next: Navigation) {
	navigation.value = next;
	boot.navigation = next;
}
</script>
