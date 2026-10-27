<script setup>
import { computed, inject, onMounted, reactive, ref, watch } from "vue";
import { Button, Progress } from "frappe-ui";
import { get_shell, import_records, run_action, update_step } from "./onboarding.js";

const props = defineProps({
	widget: { type: Object, required: true },
});

const frappe = window.frappe;
const __ = window.__;
const size = inject("tile_size", ref("Wide"));
const steps = ref(props.widget.steps.map((step) => ({ ...step })));

const is_done = (step) => step.is_complete || step.is_skipped;

// Optional steps show what else the module can do; progress counts the rest.
const required = computed(() => steps.value.filter((step) => !step.is_optional));
const optional = computed(() => steps.value.filter((step) => step.is_optional));
const counted = computed(() => (required.value.length ? required.value : steps.value));
const completed = computed(() => counted.value.filter((step) => step.is_complete).length);
const skipped = computed(
	() => counted.value.filter((step) => !step.is_complete && step.is_skipped).length
);
const all_done = computed(() => completed.value + skipped.value === counted.value.length);
const progress_label = computed(() =>
	skipped.value
		? __("{0} of {1} steps done, {2} skipped", [
				completed.value + skipped.value,
				counted.value.length,
				skipped.value,
		  ])
		: __("{0} of {1} steps done", [completed.value, counted.value.length])
);

const open = ref(next_step()?.name ?? null);
const open_step = computed(() => steps.value.find((step) => step.name === open.value));

// the next unfinished step after this one, required before optional
function next_step(after) {
	const start = after ? steps.value.indexOf(after) + 1 : 0;
	const ordered = [...steps.value.slice(start), ...steps.value.slice(0, start)];
	return (
		ordered.find((step) => !is_done(step) && !step.is_optional) ||
		ordered.find((step) => !is_done(step)) ||
		null
	);
}

watch(
	() => open_step.value && is_done(open_step.value),
	(done) => done && (open.value = next_step(open_step.value)?.name ?? null)
);

// At most five steps to do are on show. The rest, the finished ones and the optional ones fold
// into labelled rows, and a row holding the open step stays open.
const TODO_LIMIT = 5;
const folds = reactive({ more: false, done: false, optional: false });
const holds = (rows) => rows.some((step) => step.name === open.value);
const groups = computed(() => {
	const todo = required.value.filter((step) => !is_done(step));
	const finished = required.value.filter(is_done);
	const more = todo.slice(TODO_LIMIT);
	const list = [{ key: "todo", rows: todo.slice(0, TODO_LIMIT), open: true }];
	if (more.length) {
		list.push({
			key: "more",
			label: __("More steps: {0}", [more.length]),
			rows: more,
			open: folds.more || holds(more),
		});
	}
	if (finished.length) {
		const label = finished.some((step) => step.is_skipped)
			? __("Done or skipped: {0}", [finished.length])
			: __("Done: {0}", [finished.length]);
		list.push({ key: "done", label, rows: finished, open: folds.done || holds(finished) });
	}
	if (optional.value.length) {
		list.push({
			key: "optional",
			label: __("Optional steps: {0}", [optional.value.length]),
			rows: optional.value,
			open: folds.optional || all_done.value || holds(optional.value),
		});
	}
	return list;
});

function toggle_fold(group) {
	if (!group.open) return (folds[group.key] = true);
	folds[group.key] = false;
	if (holds(group.rows)) open.value = null;
}

function toggle(step) {
	open.value = open.value === step.name ? null : step.name;
}

function skip(step) {
	update_step(step, "is_skipped");
}

function unskip(step) {
	update_step(step, "is_skipped", 0);
}

function status(step) {
	if (step.is_complete)
		return { icon: "lucide-circle-check text-ink-green-5", label: __("Done") };
	if (step.is_skipped)
		return { icon: "lucide-circle-slash text-ink-gray-5", label: __("Skipped") };
	return { icon: "lucide-circle text-ink-gray-5", label: __("To do") };
}

function module_label(step) {
	const shell = frappe.boot.module_sidebars?.[get_shell(step.module)];
	return __(shell?.label || step.module);
}

function step_meta(step) {
	if (step.is_skipped) return __("Skipped");
	const [done, total] = step.module_progress || [];
	if (step.is_complete || total == null) return "";
	return size.value === "L"
		? `${done}/${total}`
		: __("{0} of {1} in {2}", [done, total, module_label(step)]);
}

// Most descriptions end with "See [Page](docs link)."; that becomes a button of its own.
function split_docs(markdown = "") {
	const match = markdown.match(/\s*See \[([^\]]+)\]\(([^)]+)\)\.?\s*$/);
	if (!match) return { text: markdown };
	return { text: markdown.slice(0, match.index), docs: { label: match[1], link: match[2] } };
}

// Collapsed and hidden are per person, kept in their user settings.
const SETTINGS = ["Module Onboarding", "onboarding_guide"];
const loaded = ref(false);
const collapsed = ref(false);
const hidden = ref(false);

onMounted(async () => {
	const settings = await frappe.model.user_settings.get(SETTINGS[0]).catch(() => ({}));
	frappe.model.user_settings[SETTINGS[0]] = settings;
	const mine = settings[SETTINGS[1]]?.[props.widget.name] || {};
	collapsed.value = !!mine.collapsed;
	hidden.value = !!mine.hidden;
	loaded.value = true;
});

function remember() {
	frappe.model.user_settings.save(...SETTINGS, {
		[props.widget.name]: { collapsed: +collapsed.value, hidden: +hidden.value },
	});
}

function toggle_collapsed() {
	collapsed.value = !collapsed.value;
	remember();
}

function hide() {
	hidden.value = true;
	remember();
}
</script>

<template>
	<section
		v-if="loaded && !hidden"
		class="rounded-4 border border-outline-gray-1 bg-surface-base dark:border-outline-gray-2"
	>
		<header class="flex items-start gap-3 px-4 pb-3 pt-3.5">
			<div class="min-w-0 flex-1">
				<h3 class="text-base-semibold text-ink-gray-9">
					{{ all_done ? __("You're set up") : widget.title }}
				</h3>
				<p class="mt-0.5 text-p-sm text-ink-gray-6">
					{{ all_done ? __("{0} is done.", [widget.title]) : progress_label }}
				</p>
			</div>
			<Button v-if="all_done" size="sm" variant="subtle" :label="__('Hide')" @click="hide" />
			<Button
				size="sm"
				variant="ghost"
				:icon="collapsed ? 'lucide-chevron-down' : 'lucide-chevron-up'"
				:label="collapsed ? __('Show steps') : __('Collapse')"
				:aria-expanded="!collapsed"
				@click="toggle_collapsed"
			/>
		</header>
		<div class="px-4 pb-3">
			<Progress
				size="sm"
				:value="((completed + skipped) / counted.length) * 100"
				:aria-label="`${widget.title}: ${progress_label}`"
			/>
		</div>

		<template v-if="!collapsed">
			<template v-for="group in groups" :key="group.key">
				<button
					v-if="group.label"
					type="button"
					class="flex h-8 w-full items-center gap-2 border-t border-outline-gray-1 px-4 text-start text-sm text-ink-gray-6 hover:bg-surface-gray-1"
					:aria-expanded="group.open"
					@click="toggle_fold(group)"
				>
					<span class="flex-1 tabular-nums">{{ group.label }}</span>
					<span
						class="size-4"
						:class="group.open ? 'lucide-chevron-up' : 'lucide-chevron-down'"
						aria-hidden="true"
					/>
				</button>
				<ul
					v-if="group.open && group.rows.length"
					class="divide-y divide-outline-gray-1 border-t border-outline-gray-1"
				>
					<li v-for="step in group.rows" :key="step.name">
						<button
							type="button"
							class="flex h-8 w-full items-center gap-3 px-4 text-start hover:bg-surface-gray-1"
							:aria-expanded="step.name === open"
							@click="toggle(step)"
						>
							<span
								:class="status(step).icon"
								class="size-4 shrink-0"
								role="img"
								:aria-label="status(step).label"
							/>
							<span
								class="min-w-0 flex-1 truncate text-base"
								:class="is_done(step) ? 'text-ink-gray-6' : 'text-ink-gray-8'"
							>
								{{ step.title }}
							</span>
							<span
								v-if="step_meta(step)"
								class="shrink-0 text-sm tabular-nums text-ink-gray-6"
							>
								{{ step_meta(step) }}
							</span>
							<span
								class="size-4 shrink-0 text-ink-gray-5"
								:class="
									step.name === open
										? 'lucide-chevron-up'
										: 'lucide-chevron-down'
								"
								aria-hidden="true"
							/>
						</button>
						<div
							v-if="step.name === open"
							class="bg-surface-gray-1 px-4 pb-4 pt-3 ps-11"
						>
							<div
								v-if="step.description"
								class="text-p-sm text-ink-gray-7"
								v-html="frappe.markdown(split_docs(step.description).text)"
							/>
							<p
								v-if="step.is_submittable && !step.is_complete"
								class="mt-1.5 text-p-xs text-ink-gray-6"
							>
								{{ __("Finishes when you submit one, not when you save it.") }}
							</p>
							<div class="mt-3 flex flex-wrap items-center gap-2">
								<Button
									:variant="step.is_complete ? 'subtle' : 'solid'"
									:label="
										step.is_complete
											? __('Open again')
											: step.action_label || step.title
									"
									@click="run_action(step)"
								/>
								<Button
									v-if="step.can_import && !step.is_complete"
									variant="subtle"
									icon-left="lucide-import"
									:label="__('Import')"
									@click="import_records(step)"
								/>
								<Button
									v-if="split_docs(step.description).docs"
									variant="ghost"
									icon-left="lucide-book-open"
									:label="split_docs(step.description).docs.label"
									:href="split_docs(step.description).docs.link"
									target="_blank"
								/>
								<span class="flex-1" />
								<Button
									v-if="step.is_skipped"
									variant="ghost"
									:label="__('Undo skip')"
									@click="unskip(step)"
								/>
								<Button
									v-else-if="!step.is_complete"
									variant="ghost"
									:label="__('Skip')"
									@click="skip(step)"
								/>
							</div>
						</div>
					</li>
				</ul>
			</template>
		</template>
	</section>
</template>
