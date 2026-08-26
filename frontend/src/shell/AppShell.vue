<!--
  The shell's own surface.

  The line the contribution contract draws: the shell owns everything that must look
  the same in every app; an app contributes only INSIDE a routed view. There is no
  contributeSidebarItem, no contributeCommand, no shell-level hook of any kind
  (#42072).
-->
<template>
	<div class="flex h-screen w-screen bg-surface-white text-ink-gray-9">
		<AppRail />
		<main class="flex min-w-0 flex-1 flex-col">
			<RouterView />
		</main>
	</div>
</template>

<script setup lang="ts">
import { RouterView } from "vue-router";
import AppRail from "./AppRail.vue";
</script>
