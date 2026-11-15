<script setup>
import { computed } from "vue";
import { useWidget } from "@framework/ui/widget";
import OnboardingTile from "../../page/workspace_view/tiles/OnboardingTile.vue";

const { config, data, refresh } = useWidget();

const tile = computed(() => ({ name: config.value.onboarding, ...data.value }));
</script>

<template>
	<OnboardingTile :widget="tile" @changed="refresh" />
</template>
