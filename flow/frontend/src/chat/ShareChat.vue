<template>
	<Dialog v-model:open="open" :title="heading">
		<div class="mb-5 flex flex-col items-start border-b border-outline-gray-1 pb-5">
			<h4 class="mb-2 text-xs text-ink-gray-5">General access</h4>
			<Select
				:model-value="access"
				:options="ACCESS"
				variant="outline"
				@update:model-value="setAccess"
			/>
		</div>
		<h4 class="mb-2 text-xs text-ink-gray-5">Members</h4>
		<!-- a phone's field waits for a tap, rather than raise the keyboard over the dialog -->
		<FormControl
			v-model:query="query"
			type="combobox"
			variant="outline"
			placeholder="Add people…"
			:autofocus="!layout.phone"
			:options="options"
			:filterable="false"
			:loading="searching"
			:model-value="null"
			@update:model-value="add"
		>
			<!-- a box to type names into, not a select: no chevron (an empty slot would show it) -->
			<template #suffix><span /></template>
			<template #item-prefix="{ item }">
				<Avatar :image="item.image" :label="item.label" size="sm" />
			</template>
		</FormControl>
		<ul class="mt-5 flex max-h-64 flex-col gap-3 overflow-y-auto">
			<li v-for="user in members" :key="user.name" class="flex items-center gap-2.5">
				<Avatar :image="user.user_image" :label="nameOf(user)" size="xl" />
				<div class="min-w-0 flex-1">
					<p class="truncate text-sm font-medium text-ink-gray-9">{{ nameOf(user) }}</p>
					<p
						v-if="nameOf(user) !== user.name"
						class="mt-1 truncate text-2xs text-ink-gray-5"
					>
						{{ user.name }}
					</p>
				</div>
				<span v-if="user.name === me.name" class="flex-none text-sm text-ink-gray-5">
					Owner (you)
				</span>
				<button
					v-else
					class="flow-icon-btn"
					:title="`Remove ${nameOf(user)}'s access`"
					@click="remove(user.name)"
				>
					<FeatherIcon name="x" class="h-3.5 w-3.5" />
				</button>
			</li>
			<li v-if="loading"><LoadingState class="py-1 text-xs text-ink-gray-5" /></li>
		</ul>
		<div class="mt-5 flex justify-end">
			<CopyButton
				:text="link"
				icon="link"
				title="Copy link"
				class="flex h-7 items-center gap-1.5 rounded-4 border border-outline-gray-2 bg-surface-base px-2 text-base text-ink-gray-8 hover:border-outline-gray-3 active:bg-surface-gray-4"
			>
				<template #default="{ copied }">{{ copied ? "Copied" : "Copy link" }}</template>
			</CopyButton>
		</div>
	</Dialog>
</template>

<script setup>
import { computed, inject, nextTick, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Avatar, Dialog, FormControl, Select, toast } from "frappe-ui";
import CopyButton from "@flow/ui-core/components/CopyButton.vue";
import FeatherIcon from "@flow/ui-core/components/FeatherIcon.vue";
import LoadingState from "@flow/ui-core/components/LoadingState.vue";
import { useDebouncedValue } from "@flow/ui-core/debounce.js";
import { layout } from "@flow/ui-core/layout.js";

// The Share dialog, which the chat's owner opens from its menu: whoever is added may
// view the chat, never write to it, since its tools run as the owner.
const flow = inject("flow");
const page = inject("flowPage");
const open = ref(false);
const viewers = ref([]);
const loading = ref(false);
const query = ref("");
const debouncedQuery = useDebouncedValue(query, 300);
const found = ref([]);
const searching = ref(false);

const sid = computed(() => flow.state.sessionId);
const router = useRouter();
// the chat's own address, which opens only for its owner and the people it is shared with
const link = computed(() => new URL(router.resolve(`/s/${sid.value}`).href, location.origin).href);
const heading = computed(() => {
	const title = flow.state.session?.title;
	return title ? `Sharing "${title}"` : "Share chat";
});
// who else may view: the people added, or every Flow user
const ACCESS = [
	{ value: "Restricted", label: "Only people you add", icon: "lucide-lock" },
	{ value: "Everyone", label: "Every Flow user", icon: "lucide-users" },
];
const access = computed(() => page.state.generalAccess?.[sid.value] ?? "Restricted");
// the owner first, then whoever may view
const me = computed(() => page.state.boot.user ?? {});
const members = computed(() => [
	me.value,
	...viewers.value.filter((user) => user.name !== me.value.name),
]);
// the people found who are not on the list yet
const options = computed(() =>
	found.value
		.filter((user) => !members.value.some((member) => member.name === user.name))
		.map((user) => ({
			value: user.name,
			label: nameOf(user),
			description: user.full_name ? user.name : undefined,
			image: user.user_image,
		}))
);

function nameOf(user) {
	return user.full_name || user.name;
}

let chat = null; // the chat the dialog opened for
let asked = 0; // member lists asked for
let shown = 0; // the one on show: an older reply never replaces it

// a fresh start each time: the chat may have changed since the last opening
async function show() {
	chat = sid.value;
	shown = asked;
	query.value = "";
	viewers.value = [];
	loading.value = true;
	const loaded = update(() => flow.client.shares(chat)).then(() => (loading.value = false));
	// open with the members in, so the dialog keeps its size; a slow list opens it anyway
	await Promise.race([loaded, new Promise((resolve) => setTimeout(resolve, 300))]);
	if (chat === sid.value) open.value = true;
}

defineExpose({ show });

// another chat opening closes the dialog, so it never acts on the wrong one
watch(sid, () => (open.value = false));

// only the newest search lands
watch([open, debouncedQuery], async ([isOpen, text], _, onCleanup) => {
	if (!isOpen) return;
	let stale = false;
	onCleanup(() => (stale = true));
	searching.value = true;
	const users = await attempt(() => flow.client.findUsers(text));
	if (stale) return;
	found.value = users ?? [];
	searching.value = false;
});

async function add(user) {
	if (!user) return;
	// the combobox writes the pick's name into the box after this; empty it for the next
	await nextTick();
	query.value = "";
	await update(() => flow.client.share(chat, user));
}

async function remove(user) {
	await update(() => flow.client.unshare(chat, user));
}

async function setAccess(value) {
	if (value === access.value) return;
	const id = chat; // the reply is this chat's, even if another one opens meanwhile
	const set = await attempt(() => flow.client.setGeneralAccess(id, value));
	if (set) page.state.generalAccess[id] = set;
}

// every request returns the whole list; it lands only if newer than the one on show
async function update(work) {
	const request = ++asked;
	const list = await attempt(work);
	if (list && request > shown) {
		shown = request;
		viewers.value = list;
	}
}

async function attempt(work) {
	try {
		return await work();
	} catch (error) {
		toast.error(error?.message ?? "Request failed");
		return null;
	}
}
</script>
