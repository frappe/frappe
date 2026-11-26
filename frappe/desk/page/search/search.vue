<script setup>
import { computed, ref, watch } from "vue";
import { Search } from "@framework/ui/mobile";
import { on_phone_visit } from "./phone_page.js";

const props = defineProps({
	route: { type: Array, default: () => [] },
	query: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["title", "actions"]);

const __ = window.__;

// Desk's own awesomebar (Page.setup_awesomebar makes it, only while search is on). This page
// lists what its modal lists and opens a result the way the modal does, so the two cannot
// drift apart.
const awesome_bar = window.frappe.app.awesome_bar;

const text = ref("");
const results = ref([]);
// as many as the modal lists (its Awesomplete's maxItems); a two-letter query matches
// over a thousand, and a phone scrolling that many rows stutters
const options = computed(() =>
	results.value.slice(0, 99).map((option) => ({
		label: option.label || option.value,
		description: option.description !== option.value ? option.description : undefined,
		icon: icon(option),
		option,
	}))
);
const search_box = ref(null);

// A later search wins over the hook results of an earlier one still in flight.
let seq = 0;
let timer;

function search() {
	if (!awesome_bar) return;
	const txt = text.value.trim().replace(/\s\s+/g, " ");
	const at = ++seq;

	// recent pages include this one
	results.value = awesome_bar
		.get_options(txt)
		.filter((option) => !Array.isArray(option.route) || option.route[0] !== "search");

	if (txt.length > 1 && window.frappe.boot.has_awesomebar_search) {
		awesome_bar.get_hook_results(txt).then((hook_results) => {
			if (at !== seq || !hook_results.length) return;
			const from_hook = hook_results.map((option) => ({ ...option, from_hook: true }));
			results.value = awesome_bar.merge_hook_results(results.value, from_hook);
		});
	}
}

function open(item, event) {
	awesome_bar.open_option(item.option, event);
	text.value = "";
}

// the modal's own debounce
watch(text, () => {
	clearTimeout(timer);
	timer = setTimeout(search, 50);
});

on_phone_visit(
	props,
	["/desk"],
	() => {
		emit("title", __("Search"));
		emit("actions", []);
		search();
		search_box.value?.focus();
	},
	() => awesome_bar?.open()
);

// Written out whole, so Tailwind's scan finds every icon class.
const ICONS = {
	New: "lucide-plus",
	"In List": "lucide-list-filter",
	List: "lucide-list",
	Form: "lucide-file-text",
	Report: "lucide-chart-column",
	"query-report": "lucide-chart-column",
	Page: "lucide-file",
	Workspace: "lucide-layout-grid",
	Workspaces: "lucide-layout-grid",
	Dashboard: "lucide-gauge",
	Calendar: "lucide-calendar",
	Tree: "lucide-network",
	Layout: "lucide-panels-top-left",
	Executable: "lucide-zap",
	Search: "lucide-search",
};

function icon(option) {
	// a recent page's route is an array, a frequent one's a "List/Item" string
	const route = Array.isArray(option.route) ? option.route[0] : option.route?.split("/")[0];
	return ICONS[option.default] || ICONS[option.type] || ICONS[route] || "lucide-history";
}

// The awesome bar builds its own labels as HTML, already translated, with what the reader
// typed escaped and the match marked. A hook's results are an app's data, so they are text.
function content(option, text) {
	return option.from_hook ? { textContent: text } : { innerHTML: text };
}
</script>

<template>
	<Search
		ref="search_box"
		v-model:query="text"
		:results="options"
		:placeholder="__('Search or type a command')"
		@select="open"
	>
		<template #header>
			<p class="px-4 pt-2 pb-1 text-sm text-ink-gray-5">
				{{ text.trim().length > 1 ? __("Results") : __("Recent") }}
			</p>
		</template>

		<!-- The modal's markup comes with the labels: the matched part in <mark>, which desk's
		     stylesheet colours and this shadow root never sees, and a <kbd> key hint. -->
		<template #item-label="{ item }">
			<div
				class="min-w-0 [&_kbd]:hidden [&_mark]:bg-transparent [&_mark]:font-semibold [&_mark]:text-ink-gray-9"
			>
				<p
					class="truncate text-base text-ink-gray-8"
					v-bind="content(item.option, item.label)"
				/>
				<p
					v-if="item.description"
					class="truncate text-xs text-ink-gray-5"
					v-bind="content(item.option, item.description)"
				/>
			</div>
		</template>

		<template #empty>
			<p class="py-14 text-center text-base text-ink-gray-6">
				{{
					!awesome_bar
						? __("Search is turned off for you")
						: text.trim()
						? __("Nothing matches {0}", [text.trim()])
						: __("Nothing recent yet")
				}}
			</p>
		</template>
	</Search>
</template>
