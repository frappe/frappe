import { createApp, ref, h } from "vue";
import OnboardingPanel from "./OnboardingPanel.vue";

class UserOnboarding {
	constructor({ title, steps, wrapper, header_icon }) {
		this.title = title;
		this.steps = steps;
		this.$wrapper = $(wrapper);
		this.header_icon = header_icon;
		this.init();
		this.hide_panel = false;
	}

	init() {
		addStyles();

		let title = this.title || __("Welcome to Frappe!");
		let onboarding_checklist = this.steps || [];
		let header_icon = this.header_icon;
		let me = this;

		const app = createApp({
			components: { OnboardingPanel },

			setup() {
				const showPanel = ref(true);
				const steps = ref(onboarding_checklist);
				return () =>
					h(OnboardingPanel, {
						modelValue: showPanel.value,
						title: title,
						steps: steps.value,
						minimizeIcon: frappe.utils.icon("minimize-2", "sm"),
						closeIcon: frappe.utils.icon("x", "sm"),
						headerIcon: header_icon,
						checklistIcon: frappe.utils.icon("circle-check", "sm"),
						completeChecklistIcon: frappe.utils.icon(
							"circle-check",
							"sm",
							"",
							"",
							"",
							"",
							"var(--green)"
						),
						"onUpdate:modelValue": (v) => {
							showPanel.value = v;
							me.hide_panel = !v;
						},
					});
			},
		});

		SetVueGlobals(app);
		app.mount(this.$wrapper.get(0));
	}
}

function addStyles() {
	if (document.getElementById("user-onboarding-styles")) return;

	const main_section = document.getElementsByClassName("main-section");

	if (main_section) {
		main_section[0].style.paddingBottom = "90px";
	}

	const style = document.createElement("style");
	style.id = "user-onboarding-styles";

	style.innerHTML = `

	.onb-panel {
		position: fixed;
		left: 236px;
		bottom: 24px;
		width: 310px;
		max-height: 80vh;
		background: #fff;
		border-radius: 8px;
		box-shadow: 0 12px 40px rgba(0,0,0,0.15);
		padding: 16px;
		z-index: 1000;
		display: flex;
		flex-direction: column;
	  }

	.onb-header-main {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.onb-header-actions button {
		border: none;
		background: transparent;
		cursor: pointer;
		margin-left: 2px;
	}

	.onb-step-left {
		display: flex;
		align-items: center;
		gap: 8px;
		flex: 1;
		min-width: 0;
	  }

	.onb-step-icon {
		margin-bottom: 2px;
		align-items: center;
	}

	.text-base {
		font-size: 14px;
		line-spacing: 1.15;
		letter-spacing: 0.02em;
		color: #050505;
	}

	.font-medium {
		font-weight: 600;
	}

	.onb-step-text {
		white-space: nowrap;
		margin-top: 2px;
		text-align: left;
		font-size: 14px;
	}

	.onb-skip {
		color: #6b7280;
		cursor: pointer;
		font-weight: 500;
	}

	.onb-skip:hover {
		color: #111827;
	}

	.onb-steps {
		margin-top: 16px;
		padding: 0px;
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: 4px;
		align-items: flex-start;
	}

	.onb-group {
		padding: 4px 8px;
		border-radius: 8px;
	}

	.onb-group:hover {
		background: #f5f5f5;
	}

	.onb-select-cursor {
		cursor: pointer;
	}

	.onb-show-on-hover {
		opacity: 0;
		visibility: hidden;
		transition: opacity 0.2s ease;
	}

	.onb-group:hover .onb-show-on-hover {
		opacity: 1;
		visibility: visible;
	}

	.onb-title {
		text-align: center;
		margin-top: 12px;
		margin-bottom: 5px;
	}

	.onb-title-icon {
		display: flex;
		justify-content: center;
		margin-bottom: 8px;
		height: 40px;
	}

	.onb-title-steps {
		color: #6b7280;
		font-size: 14px;
		margin-bottom: 8px;
	}

	.onb-progress-badge {
		background: #FDFAED;
		color: #DB7706;
		padding: 4px 10px;
		border-radius: 999px;
		font-size: 13px;
		font-weight: 500;
	}

	.onb-progress-badge-complete {
		background: #E4FAEB;
		color: #278F5E;
		padding: 4px 10px;
		border-radius: 999px;
		font-size: 13px;
		font-weight: 500;
	}

	.onb-progress-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin: 14px 0 8px;
	}

	.onb-progress-text {
		color: #6b7280;
		font-size: 14px;
	}

	[data-theme="dark"] .onb-panel {
		background-color: #232323;
		color: #e5e7eb;
		box-shadow: 0 12px 40px rgba(0,0,0,0.6);
	}

	[data-theme="dark"] .text-base {
		color: #e5e7eb;
	}

	[data-theme="dark"] .onb-skip {
		color: #9ca3af;
	}

	[data-theme="dark"] .onb-skip:hover {
		color: #f3f4f6;
	}

	[data-theme="dark"] .onb-title-steps,
	[data-theme="dark"] .onb-progress-text {
		color: #9ca3af;
	}

	[data-theme="dark"] .onb-group:hover {
		background: #1C1C1C;
		color: #f3f4f6;
	}

	[data-theme="dark"] .onb-progress-badge {
		background: rgba(245,158,11,0.15);
		color: #fbbf24;
	}

	[data-theme="dark"] .onb-progress-badge-complete {
		background: rgba(16,185,129,0.15);
		color: #34d399;
	}


	`;

	document.head.appendChild(style);
}

frappe.provide("frappe.ui");
frappe.ui.UserOnboarding = UserOnboarding;
export default UserOnboarding;
