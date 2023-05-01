<script setup>
import { VueFlow } from "@vue-flow/core";
import { Background } from "@vue-flow/background";
import { useStore } from "./store";

let store = useStore();
</script>

<template>
	<div class="workflow-container">
		<VueFlow v-model="store.workflow.elements">
			<Background pattern-color="#aaa" gap="10" />
		</VueFlow>
	</div>
</template>

<style lang="scss" scoped>
@import "@vue-flow/core/dist/style.css";
@import "@vue-flow/core/dist/theme-default.css";

.workflow-container {
	width: 100%;
	height: calc(100vh - var(--navbar-height) - var(--page-head-height) - 65px);
	border-radius: var(--border-radius-lg);
	border: 1px solid var(--border-color);
	background-color: var(--fg-color);
}
</style>
