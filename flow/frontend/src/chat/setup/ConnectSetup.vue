<template>
	<!-- shown once it knows what to offer, so no row arrives late and pushes the others down -->
	<div
		class="flex w-full flex-col text-left transition-opacity duration-200 ease-out"
		:class="[ready ? 'opacity-100' : 'opacity-0', !list && 'max-w-[360px]']"
	>
		<!-- each step carries its own width, so the one leaving keeps its shape while it fades and
		     never reflows into the next one's column.
		     A step forward slides in from the right, Back from the left. The old view fades out
		     fast so the column is empty for a blink, and nothing sits below it to jump -->
		<Transition
			mode="out-in"
			enter-active-class="transition duration-200 ease-out motion-reduce:transition-none"
			:enter-from-class="`opacity-0 ${forward ? 'translate-x-2' : '-translate-x-2'}`"
			leave-active-class="transition duration-75 ease-in motion-reduce:transition-none"
			leave-to-class="opacity-0"
		>
			<!-- in settings, every service as a tile; the page's heading asks the question -->
			<div v-if="!picked && list" key="list" class="flex w-full max-w-[560px] flex-col gap-5">
				<p v-if="unplaced" class="text-base font-medium text-ink-gray-8">
					Which service is this key for?
					<span class="ml-1 font-mono text-sm font-normal text-ink-gray-5">{{ mask(unplaced) }}</span>
				</p>
				<!-- tiles: a service is a mark to spot, not a line to read. One connected already is
				     ticked and can't be picked again; a new key for it is on the Models tab -->
				<div v-for="group in groups" :key="group.label" class="flex flex-col gap-2">
					<p class="text-sm text-ink-gray-7">{{ group.label }}</p>
					<div class="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
						<button
							v-for="choice in group.choices"
							:key="choice.id"
							type="button"
							:class="TILE"
							:disabled="Boolean(busy) || choice.done"
							:aria-label="choice.done ? `${choice.title}, connected` : undefined"
							@click="choice.run()"
						>
							<span class="flex w-full items-start justify-between gap-2">
								<span class="flex h-6 items-center">
									<span
										v-if="busy === choice.id"
										class="lucide-loader-circle size-4 animate-spin text-ink-gray-5"
										aria-hidden="true"
									/>
									<span v-else-if="choice.icon" :class="[choice.icon, 'size-5 text-ink-gray-7']" aria-hidden="true" />
									<ProviderIcon v-else :provider-id="choice.id" :size="24" bare />
								</span>
								<span :class="[BOX, choice.done ? 'bg-surface-gray-10' : 'border border-outline-gray-3']" aria-hidden="true">
									<span v-if="choice.done" class="lucide-check size-3 text-[color:var(--surface-base)]" />
								</span>
							</span>
							<span class="w-full truncate text-sm text-ink-gray-8">
								{{ choice.title }}
								<span class="text-ink-gray-5">{{ busy === choice.id ? "Connecting…" : choice.by }}</span>
							</span>
						</button>
					</div>
				</div>
				<p v-if="hint" class="text-sm text-ink-red-5">{{ hint }}</p>
				<Button v-if="unplaced" class="-ml-2 self-start" variant="ghost" label="Cancel" @click="unplaced = ''" />
			</div>

			<!-- one question, answered with a click -->
			<div v-else-if="!picked" key="choose" class="flex flex-col gap-3">
				<p class="text-base font-medium text-ink-gray-8">
					{{ unplaced ? "Which service is this key for?" : "Which AI should Flow use?" }}
					<span v-if="unplaced" class="ml-1 font-mono text-sm font-normal text-ink-gray-5">{{
						mask(unplaced)
					}}</span>
				</p>
				<div class="flex flex-col gap-1">
					<button
						v-for="choice in choices"
						:key="choice.id"
						type="button"
						:class="ROW"
						:disabled="Boolean(busy)"
						@click="choice.run()"
					>
						<span class="flex size-5 flex-none items-center justify-center">
							<ProviderIcon :provider-id="choice.id" :size="18" bare />
						</span>
						<span class="min-w-0 flex-1 text-base text-ink-gray-8">
							{{ choice.title }}
							<span class="text-ink-gray-5">{{ busy === choice.id ? "Connecting…" : choice.sub }}</span>
						</span>
						<span
							v-if="busy === choice.id"
							class="lucide-loader-circle size-4 flex-none animate-spin text-ink-gray-5"
							aria-hidden="true"
						/>
						<span v-else class="lucide-chevron-right size-4 flex-none text-ink-gray-4" aria-hidden="true" />
					</button>
				</div>
				<p v-if="hint" class="text-sm text-ink-red-5">{{ hint }}</p>
				<div class="-ml-2 flex items-center justify-between">
					<Dropdown :options="others" align="start">
						<Button variant="ghost" label="More services" icon-right="lucide-chevron-down" />
					</Dropdown>
					<Button v-if="unplaced" variant="ghost" label="Cancel" @click="unplaced = ''" />
				</div>
				<!-- for developers: a key already in hand, or anything Flow doesn't list -->
				<p v-if="!unplaced" class="mt-2 text-sm text-ink-gray-5">
					<span v-if="keyboard">Have a key? Press <kbd :class="KBD">{{ PASTE }}</kbd> · </span>
					<button type="button" :class="QUIET" @click="emit('manual')">Use your own server</button>
				</p>
			</div>

			<!-- the picked service: where its key lives, and one button to bring it in -->
			<div v-else :key="`connect-${picked.id}`" class="flex flex-col gap-5" :class="list && 'mx-auto w-full max-w-[320px] pt-[10vh]'">
				<Button
					v-if="showBack"
					class="-ml-2 self-start"
					variant="ghost"
					label="Back"
					icon-left="lucide-arrow-left"
					:disabled="Boolean(busy)"
					@click="back"
				/>
				<!-- in settings the page's heading names the service, so only the steps are here -->
				<div v-if="!list" class="flex flex-col gap-1.5">
					<div class="flex items-center gap-2.5">
						<ProviderIcon :provider-id="picked.id" :size="18" bare />
						<p class="text-base font-medium text-ink-gray-8">Connect {{ picked.name }}</p>
					</div>
					<p class="text-p-sm text-ink-gray-5">{{ billedBy(picked) }}</p>
				</div>

				<!-- two steps on a thread: each a dashed ring until it's done, then a tick -->
				<ol class="flex flex-col">
					<li class="flex min-h-8 items-center gap-3">
						<span
							class="size-5 flex-none"
							:class="opened ? 'lucide-circle-check text-ink-green-6' : 'lucide-circle-dashed text-ink-gray-6'"
							aria-hidden="true"
						/>
						<span class="min-w-0 flex-1 text-base font-medium text-ink-gray-8">Open the {{ picked.console }}</span>
						<Button variant="ghost" label="Open" icon-right="lucide-arrow-up-right" @click="openConsole" />
					</li>
					<li aria-hidden="true" class="ml-[9.5px] h-4 w-px bg-outline-gray-2" />
					<li class="flex min-h-8 items-center gap-3">
						<span class="lucide-circle-dashed size-5 flex-none text-ink-gray-6" aria-hidden="true" />
						<span class="text-base font-medium text-ink-gray-8">Add credit, then copy a new API key</span>
					</li>
				</ol>

				<!-- the key, masked: nothing to type, nothing to read back -->
				<div v-if="key" class="flex flex-col gap-1.5">
					<div class="flex items-center gap-2.5">
						<span class="lucide-key-round size-4 flex-none text-ink-gray-5" aria-hidden="true" />
						<code class="min-w-0 flex-1 truncate font-mono text-sm text-ink-gray-7">{{ mask(key) }}</code>
						<span v-if="busy" class="flex items-center gap-1.5 text-sm text-ink-gray-5">
							<span class="lucide-loader-circle size-3.5 animate-spin" aria-hidden="true" />
							Checking
						</span>
						<template v-else-if="error">
							<Button v-if="error.retry" variant="ghost" size="sm" label="Try again" @click="check(picked, key)" />
							<Button v-else variant="ghost" size="sm" label="Paste again" @click="pasteFromClipboard" />
						</template>
						<Button v-else variant="ghost" size="sm" icon="lucide-x" aria-label="Remove key" @click="clearKey" />
					</div>
					<p v-if="error" class="flex flex-wrap items-center gap-x-2 pl-[26px] text-sm">
						<span class="text-ink-red-5">{{ error.message }}</span>
						<a v-if="error.href" :href="error.href" target="_blank" rel="noopener" :class="LINK">
							{{ error.link }}
							<span class="lucide-arrow-up-right size-3" aria-hidden="true" />
						</a>
					</p>
				</div>

				<template v-else>
					<FormControl
						v-if="typing"
						type="password"
						placeholder="Paste or type the key"
						autofocus
						@keydown.enter="take($event.target.value)"
						@change="take($event.target.value)"
					/>
					<div v-else class="flex flex-col items-center gap-2.5 pt-1">
						<Button
							class="w-full"
							size="sm"
							:variant="opened ? 'solid' : 'subtle'"
							theme="gray"
							label="Paste key"
							icon-left="lucide-key-round"
							@click="pasteFromClipboard"
						/>
						<p class="flex items-center gap-2 text-base text-ink-gray-5">
							<template v-if="keyboard">
								<span>or press</span>
								<kbd :class="KBD">{{ PASTE }}</kbd>
								<span aria-hidden="true">·</span>
							</template>
							<button type="button" :class="QUIET" @click="typing = true">Type it instead</button>
						</p>
					</div>
					<p v-if="hint" class="-mt-2 text-center text-sm text-ink-gray-5">{{ hint }}</p>
				</template>
			</div>
		</Transition>
	</div>
</template>

<script setup>
import { computed, h, markRaw, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Button, Dropdown, FormControl } from "frappe-ui";
import ProviderIcon from "@flow/ui-core/components/ProviderIcon.vue";

import { call } from "../../api/frappe.js";
import { OTHERS, PRODUCTS, billedBy, detectService, looksLikeKey, mask, serviceFor } from "./services.js";

// First run as choices, not fields. One question, answered with a click: which AI do you use?
// A key is never typed: it comes off the clipboard, by the button or by Mod+V anywhere on the
// page, and shows masked while the server checks it with the service. Once it works the
// models are saved and the chat opens; `manual` asks for the providers' settings. Given a
// `service`, it starts on that one (a new key for it), and Back is `cancel`. A page with a Back
// of its own passes `showBack: false` and calls `back()` from it. Settings pass `list`: every
// service in one list, without those `connected` already.
const props = defineProps({
	service: { type: String, default: null },
	showBack: { type: Boolean, default: true },
	list: { type: Boolean, default: false },
	connected: { type: Array, default: () => [] },
});
// `picked` tells a page with its own heading which service the key step is for
const emit = defineEmits(["connected", "manual", "cancel", "picked"]);

const picked = ref(serviceFor(props.service)); // the service being connected
const key = ref(""); // the key off the clipboard
const unplaced = ref(""); // a pasted key whose service Flow couldn't tell
const opened = ref(false); // the console was opened, so pasting is the next step
const typing = ref(false); // the fallback field, for a clipboard Flow can't read
const hint = ref(""); // why the clipboard gave nothing
const busy = ref(""); // the service being checked
const error = ref(null);
const ollama = ref([]); // the models of an Ollama running beside the site
const ready = ref(false); // asked the server what it can offer
// which way the views slide: into a service, or Back out of it
const forward = ref(true);
watch(picked, (now, was) => (forward.value = Boolean(now) && !was));
watch(picked, (now) => emit("picked", now), { immediate: true });

const PASTE = /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘V" : "Ctrl V";
// the shortcut is offered where there is a keyboard to press it, however narrow the frame (the
// launcher's panel is a phone's width on a desktop)
const keyboard = window.matchMedia("(pointer: fine)").matches;
const OLLAMA = { id: "ollama", name: "Ollama" };

// a service connected already is not offered again (Ollama is saved under LiteLLM's chat name)
const taken = computed(() => new Set(props.connected.map((id) => (id === "ollama_chat" ? "ollama" : id))));
const open = (services) => services.filter((service) => !taken.value.has(service.id));

// what Flow offers, in the order a first-timer should consider it; a key in hand needs a
// service that takes keys
const choices = computed(() => [
	...(ollama.value.length && !unplaced.value && !taken.value.has("ollama")
		? [
				{
					id: "ollama",
					title: "Ollama",
					sub: "On this server. No key needed.",
					maker: "On this server",
					run: () => check(OLLAMA, null),
				},
			]
		: []),
	...open(PRODUCTS).map((service) => ({
		id: service.id,
		title: service.name,
		sub: `by ${service.maker}`,
		maker: service.maker,
		run: () => pick(service),
	})),
]);
// settings' tiles: every service, the ones connected already ticked (one per service, so a
// server of one's own is ticked once it's set up)
const tile = (service) => ({
	id: service.id,
	title: service.name,
	by: service.maker === service.name ? "" : `by ${service.maker}`,
	done: taken.value.has(service.id),
	run: () => pick(service),
});
const groups = computed(() => {
	const all = [
		{
			label: "Popular",
			choices: [
				...(ollama.value.length && !unplaced.value
					? [
							{
								id: "ollama",
								title: "Ollama",
								by: "on this server",
								done: taken.value.has("ollama"),
								run: () => check(OLLAMA, null),
							},
						]
					: []),
				...PRODUCTS.map(tile),
			],
		},
		{ label: "Other services", choices: OTHERS.map(tile) },
		{
			label: "Your own",
			choices: unplaced.value
				? []
				: [
						{
							id: "server",
							icon: "lucide-server",
							title: "Custom server",
							by: "",
							done: taken.value.has("custom_openai"),
							run: () => emit("manual"),
						},
					],
		},
	];
	// what's connected comes first, so the page opens on what Flow already has
	const inUse = all.flatMap((group) => group.choices.filter((choice) => choice.done));
	return [
		{ label: "In use", choices: inUse },
		...all.map((group) => ({ ...group, choices: group.choices.filter((choice) => !choice.done) })),
	].filter((group) => group.choices.length);
});
// a menu icon can be a component, so each service keeps its logo there too
const iconOf = (id) => markRaw({ render: () => h(ProviderIcon, { providerId: id, size: 16, bare: true }) });
const others = computed(() => [
	...open(OTHERS).map((service) => ({ label: service.name, icon: iconOf(service.id), onClick: () => pick(service) })),
	...(unplaced.value
		? []
		: [{ label: "My own server or gateway", icon: "lucide-server", onClick: () => emit("manual") }]),
]);

function pick(service) {
	picked.value = service;
	error.value = null;
	hint.value = "";
	// the key that asked which service it was for goes straight to that service
	if (unplaced.value) {
		key.value = unplaced.value;
		unplaced.value = "";
		check(service, key.value);
	}
}

// out of the picked service to the choices; from the choices, or a service given, out of setup
function back() {
	if (busy.value) return;
	if (props.service || !picked.value) return emit("cancel");
	picked.value = null;
	key.value = "";
	opened.value = false;
	typing.value = false;
	hint.value = "";
	error.value = null;
}

function openConsole() {
	opened.value = true;
	window.open(picked.value.keys, "_blank", "noopener");
}

// Taking a key, wherever it came from. A key that names its own service is connected to that
// one, even if another was picked: nobody should be told they pasted the wrong key
function take(text) {
	const value = (text ?? "").trim();
	if (!looksLikeKey(value)) return false;
	const named = detectService(value);
	error.value = null;
	hint.value = "";
	if (named) picked.value = named;
	else if (!picked.value) {
		unplaced.value = value;
		return true;
	}
	key.value = value;
	typing.value = false;
	check(picked.value, value);
	return true;
}

// The button. A browser may refuse the clipboard (a framed page without the permission, or a
// declined prompt): then the field, the one place a key is typed
async function pasteFromClipboard() {
	key.value = "";
	error.value = null;
	let text;
	try {
		text = await navigator.clipboard.readText();
	} catch {
		typing.value = true;
		return;
	}
	if (!take(text)) hint.value = `No key on the clipboard. Copy it in the ${picked.value.console} first.`;
}

// Mod+V anywhere: the shortcut a developer reaches for first
function onPaste(event) {
	if (busy.value || event.target?.closest?.("input, textarea, [contenteditable]")) return;
	if (take(event.clipboardData?.getData("text"))) event.preventDefault();
}

// the server asks the service, saves the provider and its models when the key works, and says
// why when it doesn't
async function check(service, apiKey) {
	busy.value = service.id;
	error.value = null;
	try {
		const result = await call("frappe.flow.api.setup.connect", { provider: service.id, api_key: apiKey });
		if (result.ok) return emit("connected", { service, models: result.models });
		error.value = refusal(service, result);
	} catch (failure) {
		error.value = { message: failure.message, retry: true };
	} finally {
		busy.value = "";
	}
	// keyless (Ollama) has no key line to show it on
	if (!apiKey && error.value) hint.value = error.value.message;
}

function refusal(service, { reason, message }) {
	if (reason === "wrong_key") return { message, href: service.keys, link: "Create a new one" };
	if (reason === "no_credit")
		return { message, href: service.billing ?? service.keys, link: "Add credit", retry: true };
	return { message, retry: true };
}

function clearKey() {
	key.value = "";
	error.value = null;
}

onMounted(async () => {
	document.addEventListener("paste", onPaste);
	try {
		ollama.value = (await call("frappe.flow.api.setup.setup_options")).ollama ?? [];
	} catch {
		// the listed services are offer enough
	}
	ready.value = true;
});
onBeforeUnmount(() => document.removeEventListener("paste", onPaste));
defineExpose({ back });

// no boxes: rows are a hover fill, steps a number, the key a line of its own
const ROW =
	"-mx-2 flex items-center gap-3 rounded-5 px-2 py-2.5 text-left transition-colors hover:bg-surface-gray-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3 disabled:cursor-default";
// settings' services: a soft fill, no border, the mark first and a box that ticks once connected
const TILE =
	"flex flex-col items-start gap-3 rounded-6 bg-surface-gray-2 p-3 text-left transition-colors enabled:hover:bg-surface-gray-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3 disabled:cursor-default";
const BOX = "flex size-[18px] flex-none items-center justify-center rounded-2";
const LINK =
	"inline-flex w-fit items-center gap-1 text-ink-gray-8 underline decoration-outline-gray-3 underline-offset-4 hover:decoration-outline-gray-6";
const QUIET =
	"text-ink-gray-7 underline decoration-outline-gray-3 underline-offset-4 hover:decoration-outline-gray-6";
const KBD = "rounded-4 bg-surface-gray-2 px-1.5 py-0.5 font-sans text-sm text-ink-gray-7";
</script>
