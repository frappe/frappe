<script setup>
import { ref, computed } from "vue";

const props = defineProps({
	modelValue: {
		type: Boolean,
		default: true,
	},
	title: {
		type: String,
		default: "Welcome",
	},
	steps: {
		type: Array,
		default: () => [],
	},
	minimizeIcon: {
		type: String,
		default: "—",
	},
	closeIcon: {
		type: String,
		default: "✕",
	},
	headerIcon: {
		type: String,
		default: "👋",
	},
	checklistIcon: {
		type: String,
		default: "✔",
	},
	completeChecklistIcon: {
		type: String,
		default: "✔",
	},
});

const emit = defineEmits(["update:modelValue", "skip"]);

const collapsed = ref(false);

const visible = computed({
	get: () => props.modelValue,
	set: (val) => emit("update:modelValue", val),
});

let skippAll = false;

const completedCount = computed(
	() => props.steps.filter((step) => step.is_complete || step.is_skipped).length
);

const progress = computed(() => {
	if (!props.steps.length) return 0;
	return Math.round((completedCount.value / props.steps.length) * 100);
});

function close() {
	visible.value = false;
}

function toggleCollapse() {
	collapsed.value = !collapsed.value;
}

function skipAll(skips) {
	skips.forEach((step) => {
		if (!step.is_complete && !step.is_skipped) {
			markSkip(step);
		}
	});

	skippAll = true;
}

function resetAll(skips) {
	skips.forEach((step) => {
		if (!step.is_complete && step.is_skipped) {
			markReset(step);
		}
	});

	skippAll = false;
}

function handleAction(step) {
	if (step.route_options && typeof step.route_options === "string") {
		frappe.route_options = JSON.parse(step.route_options);
	}

	const actions = {
		"Create Entry": createEntry,
		"Show Form Tour": showFormTour,
		"Update Settings": updateSettings,
		"View Report": openReport,
		"Go to Page": goToPage,
		"View Docs": viewDocs,
	};

	if (step.action && actions[step.action]) {
		actions[step.action](step);
	} else if (step.route) {
		frappe.set_route(step.route);
	}
}

function viewDocs(step) {
	window.open(step.path, "_blank");
	markComplete(step);
}

function goToPage(step) {
	toggleCollapse();

	frappe.set_route(step.path).then(() => {
		markComplete(step);
	});
}

function openReport(step) {
	toggleCollapse();

	const route = frappe.utils.generate_route({
		name: step.reference_report,
		type: "report",
		is_query_report: step.report_type !== "Report Builder",
		doctype: step.report_reference_doctype,
	});

	frappe.set_route(route).then(() => {
		markComplete(step);
	});
}

function showFormTour(step) {
	let route = step.is_single
		? frappe.router.slug(step.reference_document)
		: `${frappe.router.slug(step.reference_document)}/new`;

	frappe.route_hooks = {};
	frappe.route_hooks.after_load = (frm) => {
		const tour_name = step.form_tour;
		on_finish = () => markComplete(step);

		frm.tour
			.init({ tour_name, on_finish: () => markComplete(step) })
			.then(() => frm.tour.start());
	};

	frappe.set_route(route);
}

function updateSettings(step) {
	frappe.route_hooks = {};
	frappe.route_hooks.after_load = (frm) => {
		frm.scroll_to_field(step.field);
		frm.doc.__unsaved = true;
	};

	frappe.route_hooks.after_save = (frm) => {
		const success = frm.doc[step.field] == step.value_to_validate;

		if (success) {
			markComplete(step);
		}
	};

	frappe.set_route("Form", step.reference_document);
	markComplete(step);
}

async function createEntry(step) {
	toggleCollapse();

	frappe.route_hooks = {};
	frappe.route_hooks.after_load = (frm) => {
		const tour_name = step.form_tour;
		if (tour_name) {
			on_finish = () => {
				console.log("Tour finished");
			};
			frm.tour.init({ tour_name, on_finish }).then(() => frm.tour.start());
		}
	};

	const callback = () => {
		markComplete(step);
	};

	frappe.route_hooks.after_save = callback;
	if (step.show_full_form) {
		frappe.set_route("Form", step.reference_document, "new");
	} else {
		frappe.new_doc(step.reference_document);
	}
}

function markComplete(step) {
	step.is_complete = true;

	frappe.call("frappe.desk.desktop.update_onboarding_step", {
		name: step.name,
		field: "is_complete",
		value: 1,
	});
}

function markSkip(step) {
	step.is_skipped = true;

	frappe.call("frappe.desk.desktop.update_onboarding_step", {
		name: step.name,
		field: "is_skipped",
		value: 1,
	});
}

function markReset(step) {
	step.is_skipped = false;

	frappe.call("frappe.desk.desktop.update_onboarding_step", {
		name: step.name,
		field: "is_skipped",
		value: 0,
	});
}
</script>

<template>
	<div v-if="visible" class="onb-panel">
		<!-- Header -->

		<div class="header onb-header-main">
			<div class="text-base font-medium">{{ __("Getting Started") }}</div>
			<div class="onb-header-actions">
				<button @click="toggleCollapse" v-html="minimizeIcon"></button>
				<button @click="close" v-html="closeIcon"></button>
			</div>
		</div>

		<div v-if="!collapsed" class="body">
			<div class="onb-title">
				<div class="onb-title-icon" v-html="headerIcon"></div>

				<div class="text-base font-medium">{{ title }}</div>

				<div class="onb-title-steps">
					{{ completedCount }}/{{ steps.length }} {{ __("steps completed") }}
				</div>
			</div>

			<div class="onb-progress-row">
				<div v-if="progress !== 100">
					<div class="onb-progress-badge">{{ progress }}% {{ __("completed") }}</div>
				</div>
				<div v-else>
					<div class="onb-progress-badge-complete">
						{{ progress }}% {{ __("completed") }}
					</div>
				</div>

				<div v-if="skippAll">
					<span class="onb-skip" @click="resetAll(steps)"> {{ __("Reset All") }}</span>
				</div>
				<div v-else>
					<span class="onb-skip" @click="skipAll(steps)">{{ __("Skip All") }}</span>
				</div>
			</div>

			<!-- Steps -->
			<div class="onb-steps flex flex-col gap-2.5 overflow-hidden">
				<div
					style="width: 100%"
					v-for="(step, i) in steps"
					:key="i"
					:class="{ is_complete: step.is_complete }"
				>
					<div
						class="onb-group w-full step-title flex items-center"
						style="align-items: center"
						:class="
							step.is_complete
								? 'text-extra-muted onb-select-cursor'
								: 'text-ink-gray-8 onb-select-cursor'
						"
					>
						<div class="onb-step-left" @click="handleAction(step)">
							<div class="onb-step-icon" v-if="step.is_complete">
								<div v-html="completeChecklistIcon"></div>
							</div>
							<div class="onb-step-icon" v-else>
								<div v-html="checklistIcon"></div>
							</div>

							<div v-if="!step.is_skipped">
								<span
									class="text-base onb-step-text"
									:class="step.is_complete ? 'text-extra-muted' : ''"
								>
									{{ __(step.action_label) }}
								</span>
							</div>
							<div v-else>
								<span
									class="text-base onb-step-text text-extra-muted"
									style="text-decoration-line: line-through"
								>
									{{ __(step.action_label) }}
								</span>
							</div>
						</div>

						<div v-if="!step.is_complete">
							<div v-if="!step.is_skipped">
								<div class="ml-auto onb-show-on-hover text-sm w-12 text-right">
									<span
										style="
											font-size: 12px;
											vertical-align: text-top;
											margin-right: 0px;
										"
										class="text-ink-gray-7"
										@click="markSkip(step)"
									>
										{{ __("Skip") }}
									</span>
								</div>
							</div>
							<div v-if="step.is_skipped">
								<div class="ml-auto onb-show-on-hover text-sm w-12 text-right">
									<span
										style="
											font-size: 12px;
											vertical-align: text-top;
											margin-right: 0px;
										"
										class="text-ink-gray-7"
										@click="markReset(step)"
									>
										{{ __("Reset") }}
									</span>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>
