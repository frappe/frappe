<!--
  The index at `/apps`, which belongs to no app: one link per app the user can open.
-->
<template>
	<PageFrame title="Apps">
		<div class="py-5">
			<ul class="grid max-w-2xl grid-cols-2 gap-2">
				<li v-for="app in boot.apps ?? []" :key="app.app">
					<!-- A real navigation, not a `router.push`: crossing a prefix needs a boot re-fetch. -->
					<a
						:href="app.route"
						class="flex items-center gap-2 rounded-4 border border-outline-gray-2 px-3 py-2 text-sm hover:bg-surface-gray-2"
					>
						<img v-if="app.logo" :src="app.logo" class="size-5" alt="" />
						<span>{{ app.title }}</span>
						<code class="ml-auto text-xs text-ink-gray-5">{{ app.route }}</code>
					</a>
				</li>
			</ul>
		</div>
	</PageFrame>
</template>

<script setup lang="ts">
import { inject } from "vue";
import type { Boot } from "@/boot";
import PageFrame from "@/shell/PageFrame.vue";

const boot = inject<Boot>("boot")!;
</script>
