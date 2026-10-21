<template>
	<header class="flex h-11 flex-none items-center gap-2 px-3">
		<template v-if="!flow.state.sidebarOpen">
			<button class="flow-icon-btn" title="Show sidebar" @click="flow.setSidebarOpen(true)">
				<FeatherIcon name="sidebar" class="h-3.5 w-3.5" />
			</button>
			<button class="flow-icon-btn max-md:hidden" title="New chat" @click="router.push('/')">
				<FeatherIcon name="plus" class="h-3.5 w-3.5" />
			</button>
		</template>
		<!-- a record leads with the way back to its list, a list with its page's icon -->
		<button
			v-if="list"
			class="flow-icon-btn"
			:title="`Back to ${list.label.toLowerCase()}`"
			@click="emit('back')"
		>
			<FeatherIcon name="arrow-left" class="h-4 w-4" />
		</button>
		<!-- where the page sits: a record follows its list, which it links to. A narrow frame's bar
		     keeps the record's name alone, for the room its actions leave -->
		<nav class="flex min-w-0 items-center gap-2 text-sm" aria-label="Breadcrumb">
			<span
				v-if="!list"
				:class="icon"
				class="size-4 flex-none text-ink-gray-5"
				aria-hidden="true"
			/>
			<RouterLink
				v-if="list"
				:to="list.to"
				class="flex-none rounded-4 text-ink-gray-5 hover:text-ink-gray-8 max-md:hidden"
				>{{ list.label }}</RouterLink
			>
			<span v-if="list" aria-hidden="true" class="flex-none text-ink-gray-3 max-md:hidden"
				>/</span
			>
			<h1 class="min-w-0 truncate font-medium text-ink-gray-9">{{ title }}</h1>
		</nav>
		<span class="min-w-2 flex-1" />
		<div class="flex flex-none items-center gap-2"><slot name="actions" /></div>
	</header>
</template>

<script setup>
import { inject } from "vue";
import { useRouter } from "vue-router";
import FeatherIcon from "@flow/ui-core/components/FeatherIcon.vue";

// A page's bar, where a chat has its header: the way to the sidebar while it is hidden, where
// the page sits, and its actions at the end.
defineProps({
	icon: { type: String, required: true }, // a lucide-* class
	title: { type: String, required: true },
	list: { type: Object, default: null }, // { to, label }: the list a record belongs to
});
const emit = defineEmits(["back"]); // the back button, on a record's page
const flow = inject("flow");
const router = useRouter();
</script>
