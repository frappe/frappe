<template>
	<div class="flex flex-col gap-2 overflow-hidden">
		<div class="m-1">
			<TextInput
				ref="searchInput"
				:placeholder="'Search articles...'"
				v-model="search"
				:debounce="300"
			>
				<template #prefix>
					<FeatherIcon name="search" class="h-4 text-ink-gray-5" />
				</template>
			</TextInput>
		</div>
		<div class="flex justify-between items-center text-base text-ink-gray-5 mx-2">
			<div>All articles</div>
			<Button variant="ghost" @click="openDocs">
				<FeatherIcon name="arrow-up-right" class="h-4 text-ink-gray-5" />
			</Button>
		</div>
		<div class="flex flex-col gap-1.5 overflow-y-auto">
			<div v-for="a in parsedArticles" :key="a.title" class="flex flex-col gap-1.5">
				<div
					class="flex items-center justify-between p-1.5 hover:bg-surface-gray-1 rounded cursor-pointer"
					@click="a.opened = !a.opened"
				>
					<div class="flex items-center gap-2">
						<FeatherIcon
							:name="a.opened ? 'chevron-down' : 'chevron-right'"
							class="h-4 text-ink-gray-5"
						/>
						<div class="text-base text-ink-gray-8">{{ a.title }}</div>
					</div>
				</div>
				<div v-show="a.opened" class="flex flex-col gap-1.5 ml-5">
					<div
						v-for="subArticle in a.subArticles"
						:key="subArticle.name"
						class="group flex items-center justify-between gap-2 p-1.5 hover:bg-surface-gray-1 rounded cursor-pointer"
						@click="() => openDoc(subArticle.name)"
					>
						<div class="flex items-center gap-2">
							<FeatherIcon name="file-text" class="h-4 text-ink-gray-5" />
							<div class="text-base text-ink-gray-8">
								{{ subArticle.title }}
							</div>
						</div>
						<FeatherIcon
							name="arrow-up-right"
							class="h-4 hidden group-hover:flex text-ink-gray-5"
						/>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>
<script setup lang="ts">
import { Button, FeatherIcon, TextInput } from "frappe-ui";
import { ref, computed, onMounted } from "vue";
import type { HelpArticle, HelpCenterProps } from "./types";

const props = withDefaults(defineProps<HelpCenterProps>(), {
	docsLink: "https://docs.frappe.io/crm",
});

// `el` is frappe-ui's current TextInput template-ref member. It is being
// renamed to `inputElement` in frappe-ui 1.0.0 (spec/imperative-api.md), so
// this line follows that rename when the peer range moves to 1.0.0.
const searchInput = ref<{ el?: HTMLInputElement } | null>(null);
const search = ref("");
const articles = defineModel<HelpArticle[]>();

const parsedArticles = computed(() => {
	if (!search.value) return articles.value;

	return articles.value?.filter((a) => {
		const filteredSubArticles = a.subArticles.filter((subArticle) => {
			return subArticle.title.toLowerCase().includes(search.value.toLowerCase());
		});

		return (
			a.title.toLowerCase().includes(search.value.toLowerCase()) ||
			filteredSubArticles.length > 0
		);
	});
});

function openDocs() {
	window.open(props.docsLink, "_blank");
}

function openDoc(name: string) {
	window.open(`${props.docsLink}/${name}`, "_blank");
}

onMounted(() => {
	searchInput.value?.el?.focus();
});
</script>
