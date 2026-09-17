<template>
	<Teleport to="body">
		<div class="pfb-compare" tabindex="-1" ref="root">
			<div class="pfb-compare-bar">
				<Segmented
					:model-value="mode"
					:options="[
						{ value: 'changes', label: __('Changes') },
						{ value: 'saved', label: __('Saved') },
						{ value: 'draft', label: __('Draft') },
					]"
					@update:model-value="(v) => (mode = v)"
				/>
				<span class="pfb-compare-hint">{{ hint }}</span>
				<button
					class="es-button"
					data-variant="ghost"
					data-icon-button="true"
					:title="__('Close')"
					@click="$emit('close')"
					v-html="frappe.utils.icon('x', 'sm')"
				></button>
			</div>

			<div v-if="!docname" class="pfb-compare-empty">
				{{ __("Pick a record in the toolbar above to compare it.") }}
			</div>
			<div v-else class="pfb-compare-body">
				<div class="pfb-compare-stage">
					<div v-if="note" class="pfb-compare-empty">{{ note }}</div>
					<div v-else-if="mode !== 'saved' && !html" class="pfb-compare-empty">
						<span class="pfb-compare-spinner" aria-hidden="true"></span>
					</div>
					<iframe
						v-else-if="mode === 'saved'"
						class="pfb-compare-frame"
						:src="saved_url"
						@load="(e) => inject(e.target, HIDE_BANNER)"
					></iframe>
					<iframe
						v-else
						ref="frame"
						class="pfb-compare-frame"
						:srcdoc="html"
						@load="mark_frame"
					></iframe>
				</div>

				<div v-if="mode === 'changes'" class="pfb-compare-list">
					<div class="pfb-compare-list-title">{{ __("Changes") }}</div>
					<div v-if="!entries.length" class="pfb-compare-list-empty">
						{{ __("This draft matches the saved version.") }}
					</div>
					<template v-for="group in groups" :key="group.title">
						<div v-if="group.items.length" class="pfb-compare-group">
							{{ group.title }}
						</div>
						<button
							v-for="item in group.items"
							:key="item.id"
							class="pfb-compare-item"
							:class="{ 'pfb-compare-item--static': !item.selector }"
							@click="item.selector && jump(item)"
						>
							<span
								class="es-badge"
								:data-theme="KIND_THEME[item.kind]"
								data-size="sm"
							>
								{{ KIND_LABEL[item.kind] }}
							</span>
							<span class="pfb-compare-item-body">
								<span class="pfb-compare-item-label">{{ item.label }}</span>
								<span
									v-for="n in item.notes"
									:key="n"
									class="pfb-compare-item-note"
									>{{ n }}</span
								>
							</span>
						</button>
					</template>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useStore } from "../stores";
import Segmented from "./inspector/Segmented.vue";
import { describe_draft_changes } from "../composables/useDraftDiff";

const emit = defineEmits(["close"]);
let { print_format, store } = useStore();

const root = ref(null);
const frame = ref(null);
const mode = ref("changes");
const html = ref("");
const note = ref("");
const entries = ref([]);

const KIND_LABEL = {
	added: __("Added"),
	removed: __("Removed"),
	changed: __("Changed"),
	moved: __("Moved"),
};
const KIND_THEME = { added: "green", removed: "red", changed: "amber", moved: "gray" };
const HIDE_BANNER = ".action-banner { display: none !important; }";
const MARK_CSS = `
[data-pfb-diff] { position: relative; outline-offset: 2px; }
[data-pfb-diff]::before { content: attr(data-pfb-diff-label); position: absolute; right: 0; bottom: 100%; margin-bottom: 2px; padding: 0 5px; font: 600 9px/1.6 sans-serif; color: #fff; border-radius: 3px; }
[data-pfb-diff="added"] { outline: 2px solid #16a34a; background: #ecfdf3; }
[data-pfb-diff="added"]::before { background: #16a34a; }
[data-pfb-diff="removed"] { outline: 2px dashed #dc2626; background: #fef2f2; text-decoration: line-through; opacity: 0.75; }
[data-pfb-diff="removed"]::before { background: #dc2626; text-decoration: none; }
[data-pfb-diff="changed"] { outline: 2px solid #f59e0b; background: #fff7d6; }
[data-pfb-diff="changed"]::before { background: #f59e0b; }
[data-pfb-diff="moved"] { outline: 2px dashed #6b7280; }
[data-pfb-diff="moved"]::before { background: #6b7280; }
.pfb-diff-flash { box-shadow: 0 0 0 6px rgba(245, 158, 11, 0.35); transition: box-shadow 0.6s; }
${HIDE_BANNER}`;

let docname = computed(() => store.value.preview_doc_name);
let doctype = computed(() => print_format.value.doc_type);
let saved_url = computed(
	() =>
		"/printview?" +
		new URLSearchParams({
			doctype: doctype.value,
			name: docname.value,
			format: print_format.value.name,
		})
);
let hint = computed(() => {
	if (mode.value === "saved") return __("What the format prints today.");
	if (mode.value === "draft") return __("Your draft as it would print.");
	return __("Your draft with every change marked. Removed items are shown where they were.");
});
let groups = computed(() => [
	{ title: __("Settings"), items: entries.value.filter((e) => e.group === "settings") },
	{ title: __("Sections"), items: entries.value.filter((e) => e.group === "sections") },
	{ title: __("Fields"), items: entries.value.filter((e) => e.group === "fields") },
]);

function inject(target, css) {
	const doc = target?.contentDocument;
	if (!doc?.head) return;
	const style = doc.createElement("style");
	style.textContent = css;
	doc.head.appendChild(style);
}

function find(item) {
	const doc = frame.value?.contentDocument;
	if (!doc) return null;
	const matches = doc.querySelectorAll(item.selector);
	return matches[item.occurrence || 0] || null;
}

function mark_frame() {
	inject(frame.value, mode.value === "changes" ? MARK_CSS : HIDE_BANNER);
	if (mode.value !== "changes") return;
	for (const item of entries.value) {
		const el = item.selector && find(item);
		if (!el) continue;
		el.setAttribute("data-pfb-diff", item.kind);
		el.setAttribute("data-pfb-diff-label", KIND_LABEL[item.kind]);
		el.title = item.notes.join("\n");
	}
}

function jump(item) {
	const el = find(item);
	if (!el) return;
	el.scrollIntoView({ block: "center", behavior: "smooth" });
	el.classList.add("pfb-diff-flash");
	setTimeout(() => el.classList.remove("pfb-diff-flash"), 900);
}

async function load() {
	html.value = "";
	note.value = "";
	const draft = store.value.get_preview_format_doc();
	const saved = store.value.saved_format || {};
	const diff = describe_draft_changes(saved, draft);
	entries.value = [
		...diff.settings.map((s, i) => ({
			id: `s${i}`,
			group: "settings",
			kind: "changed",
			label: s.label,
			notes: [s.note],
		})),
		...diff.sections.map((s) => ({
			id: `sec${s.index}`,
			group: "sections",
			kind: s.kind,
			label: s.label,
			notes: s.notes,
			selector: `[data-section="${s.index}"]`,
		})),
		...diff.fields.map((f, i) => ({
			id: `f${i}`,
			group: "fields",
			kind: f.kind,
			label: f.label,
			notes: f.notes,
			selector: `[data-fieldname="${f.fieldname}"]`,
			occurrence: f.occurrence,
		})),
	];
	const doc =
		mode.value === "changes" ? { ...draft, format_data: JSON.stringify(diff.merged) } : draft;
	try {
		const args = { print_format: doc, doctype: doctype.value, name: docname.value };
		if (store.value.letterhead) args.letterhead = store.value.letterhead.name;
		html.value = await frappe.xcall(
			"frappe.utils.print_format_generator.render_builder_preview",
			args
		);
	} catch (e) {
		note.value = e.message || __("Could not render the draft");
	}
}

function on_keydown(e) {
	if (e.key === "Escape" && !window.cur_dialog?.display) emit("close");
}

watch([docname, mode], () => mode.value !== "saved" && load());
onMounted(() => {
	root.value?.focus();
	load();
	window.addEventListener("keydown", on_keydown);
});
onUnmounted(() => window.removeEventListener("keydown", on_keydown));
</script>

<style scoped>
.pfb-compare {
	position: fixed;
	inset: 0;
	z-index: 1035;
	display: flex;
	flex-direction: column;
	gap: 8px;
	padding: 10px 12px 12px;
	background: rgba(0, 0, 0, 0.75);
	outline: none;
}

.pfb-compare-bar {
	flex-shrink: 0;
	display: flex;
	align-items: center;
	gap: 12px;
	color: var(--white);
}

.pfb-compare-bar .es-button {
	margin-left: auto;
	color: var(--white);
}

.pfb-compare-bar .es-button:hover,
.pfb-compare-bar .es-button:active {
	background: rgba(255, 255, 255, 0.18);
}

.pfb-compare-hint {
	font-size: var(--text-sm);
	opacity: 0.8;
}

.pfb-compare-body {
	flex: 1;
	min-height: 0;
	display: flex;
	gap: 12px;
}

.pfb-compare-stage {
	flex: 1;
	min-width: 0;
	display: flex;
	flex-direction: column;
}

.pfb-compare-frame {
	flex: 1;
	width: 100%;
	min-height: 0;
	border: none;
	border-radius: var(--radius-lg, 8px);
	background: var(--fg-color);
}

.pfb-compare-empty {
	flex: 1;
	display: flex;
	align-items: center;
	justify-content: center;
	background: var(--fg-color);
	border-radius: var(--radius-lg, 8px);
	font-size: var(--text-sm);
	color: var(--text-color);
}

.pfb-compare-list {
	width: 300px;
	flex-shrink: 0;
	overflow-y: auto;
	padding: 10px 12px;
	background: var(--fg-color);
	border-radius: var(--radius-lg, 8px);
}

.pfb-compare-list-title {
	font-size: var(--text-base);
	font-weight: var(--weight-semibold);
	margin-bottom: 6px;
}

.pfb-compare-list-empty {
	font-size: var(--text-sm);
	color: var(--text-muted);
}

.pfb-compare-group {
	margin: 10px 0 4px;
	font-size: var(--text-tiny);
	font-weight: var(--weight-semibold);
	text-transform: uppercase;
	letter-spacing: 0.02em;
	color: var(--text-muted);
}

.pfb-compare-item {
	display: flex;
	align-items: flex-start;
	gap: 8px;
	width: 100%;
	padding: 6px;
	border: none;
	border-radius: var(--radius);
	background: transparent;
	text-align: left;
	cursor: pointer;
}

.pfb-compare-item:hover {
	background: var(--gray-100);
}

.pfb-compare-item--static {
	cursor: default;
}

.pfb-compare-item .es-badge {
	flex-shrink: 0;
	margin-top: 1px;
}

.pfb-compare-item-body {
	min-width: 0;
	display: flex;
	flex-direction: column;
	gap: 2px;
}

.pfb-compare-item-label {
	font-size: var(--text-sm);
	font-weight: var(--weight-medium);
}

.pfb-compare-item-note {
	font-size: var(--text-xs);
	color: var(--text-muted);
	overflow-wrap: anywhere;
}

.pfb-compare-spinner {
	width: 20px;
	height: 20px;
	border: 2px solid var(--gray-300);
	border-top-color: var(--gray-600);
	border-radius: 50%;
	animation: pfb-compare-spin 0.7s linear infinite;
}

@keyframes pfb-compare-spin {
	to {
		transform: rotate(360deg);
	}
}
</style>
