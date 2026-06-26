<template>
	<div class="max-w-3xl p-6">
		<h3 class="mb-1 text-xl-semibold text-ink-gray-9">Composer</h3>
		<p class="mb-6 text-p-sm text-ink-gray-6">
			EmailComposer owns its window — it wraps itself in a
			<code>FloatingWindow</code>, so drive it with <code>v-model:mode</code> (docked /
			floating / minimized). CommentComposer is window-agnostic content the host drops into a
			<code>FloatingWindow</code> (or renders inline). Both are transport-agnostic, so here
			<code>onSubmit</code> just logs the payload.
		</p>

		<!-- ── Controls ──────────────────────────────────────────────────── -->
		<div class="mb-6 flex flex-wrap items-center gap-x-6 gap-y-3 rounded-lg border p-4">
			<div class="flex items-center gap-2">
				<span class="text-p-sm text-ink-gray-6">mode</span>
				<Select v-model="mode" :options="modeOptions" />
			</div>
			<div class="flex items-center gap-3">
				<span class="text-p-sm text-ink-gray-6">fields</span>
				<Checkbox v-model="fieldSubject" label="subject" />
				<Checkbox v-model="fieldCc" label="cc" />
				<Checkbox v-model="fieldBcc" label="bcc" />
			</div>
		</div>

		<!-- ── EmailComposer owns its window; CommentComposer is host-wrapped ─ -->
		<div class="mb-8 flex flex-wrap gap-8">
			<div>
				<div class="mb-2 text-sm-medium text-ink-gray-7">
					EmailComposer (owns its FloatingWindow — drive with v-model:mode)
				</div>
				<EmailComposer
					v-model:mode="mode"
					:fields="fields"
					v-model:recipients="recipients"
					:search-recipients="searchRecipients"
					:mentions="mentions"
					expandable
					storage-key="story:composer:email"
					placeholder="Write your reply…"
					:on-submit="(p) => log('email:submit', p)"
					@discard="log('email:discard')"
				/>
			</div>

			<div>
				<div class="mb-2 text-sm-medium text-ink-gray-7">
					MultiComposer (Via Email ▾ / Comment — channel: {{ channel }})
				</div>
				<MultiComposer
					v-model:channel="channel"
					:fields="fields"
					:search-recipients="searchRecipients"
					:mentions="mentions"
					expandable
					storage-key="story:composer:multi"
					placeholder="Write your reply…"
					:on-submit="(p) => log('multi:email', p)"
					:on-comment="(p) => log('multi:comment', p)"
					@discard="log('multi:discard')"
				/>
			</div>

			<div>
				<div class="mb-2 text-sm-medium text-ink-gray-7">
					CommentComposer in FloatingWindow
				</div>
				<FloatingWindow
					title="Comment"
					:minimizable="false"
					storage-key="story:composer:comment:window"
				>
					<CommentComposer
						storage-key="story:composer:comment"
						:mentions="mentions"
						placeholder="Type @ to mention a teammate…"
						:on-submit="(p) => log('comment:submit', p)"
						@discard="log('comment:discard')"
					/>
				</FloatingWindow>
			</div>
		</div>

		<!-- ── Fixed docked (expandable=false): no pop-out control ───────── -->
		<div class="mb-8">
			<div class="mb-2 text-sm-medium text-ink-gray-7">
				EmailComposer fixed-docked (<code>:expandable="false"</code>) — with a
				host-supplied From picker (#from) and <code>v-model:body</code>
			</div>
			<div class="rounded-md border border-outline-gray-2 bg-surface-base p-2">
				<EmailComposer
					:fields="fields"
					:expandable="false"
					v-model:body="draftBody"
					:signature="signature"
					placeholder="Write your reply…"
					:on-submit="(p) => log('inline:submit', p)"
				>
					<template #from>
						<div class="flex items-center gap-2 py-1.5">
							<span class="text-p-sm text-ink-gray-5">From</span>
							<Select v-model="fromEmail" :options="identities" />
						</div>
					</template>
				</EmailComposer>
			</div>
			<p class="mt-1 text-xs text-ink-gray-5">
				body length (v-model:body): {{ draftBody.length }}
			</p>
		</div>

		<!-- ── Event log ─────────────────────────────────────────────────── -->
		<div class="text-sm-medium text-ink-gray-7">Events</div>
		<pre
			class="mt-2 max-h-60 overflow-auto rounded-lg bg-surface-gray-2 p-3 text-xs text-ink-gray-8"
			>{{ events.length ? events.join("\n") : "—" }}</pre
		>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Checkbox, Select } from "frappe-ui";
import { FloatingWindow, type WindowMode } from "frappe-ui";
import { CommentComposer, EmailComposer, MultiComposer } from "../index";
import type {
	Channel,
	CommentPayload,
	EmailPayload,
	Field,
	Mention,
	Recipient,
	Recipients,
} from "../types";

const mode = ref<WindowMode>("docked");
const modeOptions: WindowMode[] = ["docked", "floating", "minimized"];

// MultiComposer's active channel, driven by its header dropdown.
const channel = ref<Channel>("email");

const fieldSubject = ref(true);
const fieldCc = ref(true);
const fieldBcc = ref(false);
const fields = computed<Field[]>(() =>
	(
		[
			["subject", fieldSubject.value],
			["cc", fieldCc.value],
			["bcc", fieldBcc.value],
		] as const
	)
		.filter(([, on]) => on)
		.map(([name]) => name)
);

// Recipients are host-owned via `v-model:recipients` — seed a reply and observe edits.
const recipients = ref<Recipients>({
	to: [{ email: "john@example.com", label: "John Doe" }],
	cc: [],
	bcc: [],
});

// Mentions are a host-supplied list; the editor filters them on @.
const mentions: Mention[] = [
	{ label: "John Doe", value: "john@example.com" },
	{ label: "Jane Smith", value: "jane@example.com" },
	{ label: "Sam Patel", value: "sam@example.com" },
];

// Recipient search is host-supplied: the composer calls it (debounced) as the
// user types To/Cc/Bcc. Here a mocked directory with fake latency stands in for
// a server endpoint; a real host would hit its contacts/users API.
const directory: Recipient[] = [
	{ label: "John Doe", email: "john@example.com" },
	{ label: "Jane Smith", email: "jane@example.com" },
	{ label: "Sam Patel", email: "sam@example.com" },
	{ label: "Riya Kapoor", email: "riya@example.com" },
	{ label: "Marco Silva", email: "marco@example.com" },
];
function searchRecipients(query: string): Promise<Recipient[]> {
	const text = query.trim().toLowerCase();
	const matches = text
		? directory.filter(
				(person) =>
					person.label!.toLowerCase().includes(text) ||
					person.email.toLowerCase().includes(text)
		  )
		: directory;
	return new Promise((resolve) => setTimeout(() => resolve(matches), 300));
}

const identities = ["support@example.com", "sales@example.com"];
const fromEmail = ref(identities[0]);
const draftBody = ref("");

// Host-owned signatures, swapped when the From identity changes — the composer
// inserts/swaps them without clobbering text the user has typed.
const signatures: Record<string, string> = {
	"support@example.com": "<p>— Support Team</p>",
	"sales@example.com": "<p>— Sales Team</p>",
};
const signature = computed(() => signatures[fromEmail.value]);

const events = ref<string[]>([]);
function log(name: string, payload?: EmailPayload | CommentPayload) {
	const time = new Date().toLocaleTimeString();
	events.value.unshift(`[${time}] ${name}${payload ? " " + JSON.stringify(payload) : ""}`);
}
</script>
