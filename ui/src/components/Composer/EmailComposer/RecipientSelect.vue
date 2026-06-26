<template>
	<!--
		Recipient entry, modelled on Frappe Mail's: selected recipients show as
		removable chips (avatar + name), with an inline input for typing. The
		host's `search` (if any) feeds a dropdown of matches (avatar + name +
		email) on focus and as the user types; a valid typed address can always
		be added as-is, and a pasted list of addresses becomes chips at once.

		Deliberately hand-rolled rather than frappe-ui's Combobox: this is a
		multi-recipient field (Combobox is single-select), and as a library
		component it runs against three apps' differing frappe-ui versions — so
		owning the render keeps names/avatars showing identically everywhere.
	-->
	<div class="relative w-full">
		<div class="flex w-full flex-wrap items-center gap-1" @click="focusInput">
			<span
				v-for="recipient in displayedRecipients"
				:key="recipient.email"
				class="flex items-center gap-1 rounded bg-surface-gray-3 py-0.5 pe-1 ps-1 text-p-sm text-ink-gray-8"
			>
				<Avatar
					size="xs"
					:image="recipient.image"
					:label="recipient.label || recipient.email"
				/>
				{{ recipient.label || recipient.email }}
				<button
					class="grid size-4 place-items-center rounded-sm text-ink-gray-5 hover:bg-surface-gray-4"
					@click.stop="removeRecipient(recipient)"
				>
					<FeatherIcon name="x" class="size-3" />
				</button>
			</span>

			<input
				ref="inputRef"
				v-model="query"
				type="text"
				class="h-7 min-w-[6rem] flex-1 border-0 bg-transparent p-0 text-base text-ink-gray-8 placeholder-ink-gray-4 focus:ring-0"
				:placeholder="model.length ? '' : placeholder"
				autocomplete="off"
				@focus="openDropdown"
				@input="onInput"
				@keydown.down.prevent="moveActive(1)"
				@keydown.up.prevent="moveActive(-1)"
				@keydown.enter.prevent="onEnter"
				@keydown.esc="isOpen = false"
				@keydown.delete="onBackspace"
				@paste="onPaste"
				@blur="isOpen = false"
			/>
		</div>

		<div
			v-if="isOpen && (loading || options.length || query.trim())"
			class="absolute z-10 mt-1 w-full overflow-hidden rounded-lg border border-outline-gray-1 bg-surface-white py-1 shadow-2xl"
		>
			<div v-if="loading && !options.length" class="px-3 py-1.5 text-p-sm text-ink-gray-4">
				Searching…
			</div>
			<ul v-else-if="options.length" class="max-h-[12rem] overflow-y-auto px-1.5">
				<li
					v-for="(option, index) in options"
					:key="option.recipient.email"
					class="flex cursor-pointer items-center gap-2 rounded px-2 py-1"
					:class="
						index === activeIndex ? 'bg-surface-gray-2' : 'hover:bg-surface-gray-2'
					"
					@mousedown.prevent="selectOption(option)"
					@mousemove="activeIndex = index"
				>
					<Avatar
						size="lg"
						:image="option.recipient.image"
						:label="option.recipient.label || option.recipient.email"
					/>
					<div class="flex min-w-0 flex-col">
						<span class="truncate text-base text-ink-gray-8">
							{{ optionTitle(option) }}
						</span>
						<span
							v-if="optionSubtitle(option)"
							class="truncate text-p-sm text-ink-gray-5"
						>
							{{ optionSubtitle(option) }}
						</span>
					</div>
				</li>
			</ul>
			<div v-else class="px-3 py-1.5 text-p-sm text-ink-gray-4">No matches</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Avatar, FeatherIcon } from "frappe-ui";
import type { Recipient, RecipientSearch } from "../types";

const props = defineProps<{ placeholder?: string; search?: RecipientSearch }>();
const model = defineModel<Recipient[]>({ default: () => [] });

interface Option {
	recipient: Recipient;
	/** A creatable row for a valid address the user typed (not from the directory). */
	create?: boolean;
}

const inputRef = ref<HTMLInputElement | null>(null);
const query = ref("");
const isOpen = ref(false);
const loading = ref(false);
const searchResults = ref<Recipient[]>([]);
const activeIndex = ref(-1);

// Minimal, permissive email check — good enough to gate creation without
// pulling in a validation dependency.
function isValidEmail(value: string) {
	return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

// Tiny debounce so we don't hit the host's search on every keystroke. (The
// library carries no @vueuse dependency, so we inline it.)
function debounce<T extends (...args: never[]) => void>(fn: T, delay: number) {
	let timer: ReturnType<typeof setTimeout> | undefined;
	return (...args: Parameters<T>) => {
		clearTimeout(timer);
		timer = setTimeout(() => fn(...args), delay);
	};
}

// Drop stale responses so an earlier-but-slower request can't overwrite the
// latest results.
let requestId = 0;
async function runSearch(text: string) {
	if (!props.search) return;
	const id = ++requestId;
	loading.value = true;
	try {
		const results = await props.search(text);
		if (id === requestId) searchResults.value = results;
	} finally {
		if (id === requestId) loading.value = false;
	}
}

const debouncedSearch = debounce(runSearch, 250);

function focusInput() {
	inputRef.value?.focus();
}

function openDropdown() {
	isOpen.value = true;
	activeIndex.value = -1;
	// Seed the directory once on focus so names show before the user types.
	if (props.search && !searchResults.value.length) runSearch("");
}

function onInput() {
	isOpen.value = true;
	activeIndex.value = -1;
	debouncedSearch(query.value);
}

// Selected recipients as chips, de-duplicated by email. Vue's keyed reconciler
// corrupts its block tree on duplicate `:key`s (null-vnode crashes on patch and
// unmount), and seeded recipients can repeat an address — so the render list is
// always unique.
const displayedRecipients = computed(() => dedupeByEmail(model.value));

// The dropdown excludes already-selected recipients and likewise de-duplicates
// by email (contact data can repeat an address) so every row key is unique. A
// valid, new typed address rides on top as a creatable row.
const options = computed<Option[]>(() => {
	const seen = new Set(model.value.map((recipient) => recipient.email));
	const matches: Option[] = [];
	for (const recipient of searchResults.value) {
		if (seen.has(recipient.email)) continue;
		seen.add(recipient.email);
		matches.push({ recipient });
	}
	const typed = query.value.trim();
	if (typed && isValidEmail(typed) && !seen.has(typed)) {
		return [{ recipient: { email: typed }, create: true }, ...matches];
	}
	return matches;
});

function dedupeByEmail(recipients: Recipient[]) {
	const seen = new Set<string>();
	const unique: Recipient[] = [];
	for (const recipient of recipients) {
		if (seen.has(recipient.email)) continue;
		seen.add(recipient.email);
		unique.push(recipient);
	}
	return unique;
}

// Row text as plain strings (no `<template v-if>` fragments in the list — those
// trip Vue's block patcher with a null next-sibling on update).
function optionTitle(option: Option) {
	if (option.create) return `Add “${option.recipient.email}”`;
	return option.recipient.label || option.recipient.email;
}

function optionSubtitle(option: Option) {
	return !option.create && option.recipient.label ? option.recipient.email : "";
}

function moveActive(delta: number) {
	if (!options.value.length) return;
	isOpen.value = true;
	const next = activeIndex.value + delta;
	activeIndex.value = (next + options.value.length) % options.value.length;
}

function onEnter() {
	const active = activeIndex.value >= 0 ? options.value[activeIndex.value] : null;
	if (active) selectOption(active);
	else addTyped();
}

function selectOption(option: Option) {
	addRecipient(option.recipient);
}

function addRecipient(recipient: Recipient) {
	if (!model.value.some((existing) => existing.email === recipient.email)) {
		model.value = [...model.value, recipient];
	}
	query.value = "";
	searchResults.value = [];
	activeIndex.value = -1;
	focusInput();
}

function addTyped() {
	const typed = query.value.trim();
	if (isValidEmail(typed)) addRecipient({ email: typed });
}

// Paste a list of addresses (comma / newline / semicolon separated) as chips.
function onPaste(event: ClipboardEvent) {
	const text = event.clipboardData?.getData("text") ?? "";
	if (!text) return;
	const selected = new Set(model.value.map((recipient) => recipient.email));
	const emails = text
		.split(/[\n,;]+/)
		.map((value) => value.trim())
		.filter((value) => isValidEmail(value) && !selected.has(value));
	if (!emails.length) return;
	event.preventDefault();
	model.value = [...model.value, ...emails.map((email) => ({ email }))];
	query.value = "";
}

function removeRecipient(recipient: Recipient) {
	model.value = model.value.filter((item) => item.email !== recipient.email);
}

function onBackspace() {
	if (query.value || !model.value.length) return;
	model.value = model.value.slice(0, -1);
}
</script>
