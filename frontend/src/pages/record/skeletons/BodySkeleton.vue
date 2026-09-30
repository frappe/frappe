<!-- The body row before the record arrives: the built-in columns drawn by BodyColumns
     itself, so the panel takes the width the reader left it. -->
<template>
	<BodyColumns :items="columns" :user="user" data-record-body-skeleton>
		<template #form>
			<TabsSkeleton :feed="feed" />
		</template>
		<template #panel="{ collapsed }">
			<PanelSkeleton :collapsed="collapsed" />
		</template>
	</BodyColumns>
</template>

<script setup lang="ts">
import { BODY_BUILTINS } from "@/recordPage/body";
import BodyColumns from "../body/BodyColumns.vue";
import PanelSkeleton from "./PanelSkeleton.vue";
import TabsSkeleton from "./TabsSkeleton.vue";

/** `feed`: the page opens on a feed tab, so its placeholder is the feed's. */
defineProps<{ user: string; feed: boolean }>();

const columns = BODY_BUILTINS.map((item) => ({ ...item }));
</script>
