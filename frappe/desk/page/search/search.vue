<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { TextInput } from "frappe-ui";
import { List, ListCell, ListRow, ListRows } from "frappe-ui/list";

defineProps({
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
const options = computed(() => results.value.slice(0, 99));
const input = ref(null);

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
			results.value = awesome_bar
				.deduplicate(results.value.concat(hook_results))
				.sort((a, b) => b.index - a.index);
		});
	}
}

// the modal's own debounce
watch(text, () => {
	clearTimeout(timer);
	timer = setTimeout(search, 50);
});

onMounted(() => {
	// A phone's page. A wider screen has the awesomebar modal, so it goes there instead,
	// and the route is replaced so Back does not land here again.
	if (!window.frappe.is_mobile()) {
		window.frappe.route_flags.replace_route = true;
		window.frappe.set_route("/desk");
		awesome_bar?.open();
		return;
	}

	emit("title", __("Search"));
	emit("actions", []);
	search();
	input.value?.querySelector("input")?.focus();
});

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
</script>

<template>
	<div class="h-full overflow-y-auto pb-10">
		<div ref="input" class="px-4 pt-3 pb-2">
			<TextInput
				v-model="text"
				:placeholder="__('Search or type a command')"
				:aria-label="__('Search')"
			>
				<template #prefix>
					<span class="lucide-search size-4 text-ink-gray-5" aria-hidden="true" />
				</template>
			</TextInput>
		</div>

		<p class="px-4 pt-2 pb-1 text-sm text-ink-gray-5">
			{{ text.trim().length > 1 ? __("Results") : __("Recent") }}
		</p>

		<!-- The modal's markup comes with the labels: the matched part in <mark>, which desk's
		     stylesheet colours and this shadow root never sees, and a <kbd> key hint. -->
		<div
			class="px-2 [&_kbd]:hidden [&_mark]:bg-transparent [&_mark]:font-semibold [&_mark]:text-ink-gray-9"
		>
			<List :row-height="52">
				<ListRows :items="options" :row-key="(_, index) => index" v-slot="{ item, value }">
					<ListRow
						:value="value"
						@click="(event) => awesome_bar.open_option(item, event)"
					>
						<ListCell>
							<span
								:class="icon(item)"
								class="size-5 text-ink-gray-6"
								aria-hidden="true"
							/>
						</ListCell>
						<ListCell>
							<!-- Labels carry the awesomebar's own markup (the matched part in bold),
							     escaped where it holds user input, as the modal renders them. -->
							<div class="min-w-0">
								<p
									class="truncate text-base text-ink-gray-8"
									v-html="__(item.label || item.value)"
								/>
								<p
									v-if="item.description && item.description !== item.value"
									class="truncate text-xs text-ink-gray-5"
									v-html="__(item.description)"
								/>
							</div>
						</ListCell>
					</ListRow>
				</ListRows>
			</List>

			<p v-if="!awesome_bar" class="py-14 text-center text-base text-ink-gray-6">
				{{ __("Search is turned off for you") }}
			</p>
			<p v-else-if="!options.length" class="py-14 text-center text-base text-ink-gray-6">
				{{
					text.trim()
						? __("Nothing matches {0}", [text.trim()])
						: __("Nothing recent yet")
				}}
			</p>
		</div>
	</div>
</template>
