let frappeCloudBaseEndpoint = "https://frappecloud.com";
let isFCUser = false;

$(document).ready(function () {
	if (
		frappe.boot.is_fc_site &&
		!!frappe.boot.setup_complete &&
		!frappe.is_mobile() &&
		frappe.user.has_role("System Manager")
	) {
		frappe.call({
			method: "frappe.integrations.frappe_providers.frappecloud_billing.current_site_info",
			callback: (r) => {
				if (!r?.message) return;

				const response = r.message;
				const trial_end_date = new Date(response.trial_end_date);
				frappeCloudBaseEndpoint = response.base_url;
				isFCUser = response.is_fc_user;

				if (response.trial_end_date && trial_end_date > new Date()) {
					$(".layout-main-section").before(
						generateTrialSubscriptionBanner(response.trial_end_date)
					);
				}
				addManageBillingDropdown();

				$(".login-to-fc, .upgrade-plan-button").on("click", function () {
					openFrappeCloudDashboard();
				});
			},
		});
	}
});

function setErrorMessage(message) {
	$("#fc-login-error").text(message);
}

function addManageBillingDropdown() {
	$(".dropdown-navbar-user .dropdown-menu .dropdown-divider").before(
		`<button class="dropdown-item login-to-fc" target="_blank">Manage Billing</button>`
	);
}

function openFrappeCloudDashboard() {
	window.open(`${frappeCloudBaseEndpoint}/dashboard/sites/${frappe.boot.sitename}`, "_blank");
}

function generateTrialSubscriptionBanner(trialEndDate) {
	const trial_end_date = new Date(trialEndDate);
	const today = new Date();
	const diffTime = trial_end_date - today;
	const trial_end_days = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
	const trial_end_string =
		trial_end_days > 1 ? `${trial_end_days} days` : `${trial_end_days} day`;

	return $(`
			<style>
				.trial-banner {
					display: flex;
					justify-content: space-between;
					align-items: center;
					background-color: var(--subtle-accent);
					border-radius: var(--border-radius-md);
				}
				.trial-banner > div {
					display: flex;
					gap: 8px;
				}
				.trial-banner .info-icon {
					margin: auto 0;
				}
				.trial-banner > div > div {
					display: flex;
					flex-direction: column;
					justify-content: center;
				}
				.trial-banner .title {
					font-size: var(--text-base);
					font-weight: var(--weight-semibold);
				}
				.trial-banner .description {
					font-size: var(--text-sm);
					color: var(--text-muted);
				}
				.trial-banner .upgrade-plan-button {
					height: fit-content;
					background-color: var(--fg-color);
					border: 1px solid var(--gray-300);
					color: var(--gray-800);
					border-radius: var(--border-radius);
				}
				.trial-banner .upgrade-plan-button:hover {
					border-color: var(--gray-400);
				}
			</style>
			<div class="trial-banner px-3 py-2 m-2 mt-4">
				<div>
					<svg class="info-icon" width="18" height="18" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
						<g clip-path="url(#clip0_3360_13841)">
							<path fill-rule="evenodd" clip-rule="evenodd" d="M8 14.25C11.4518 14.25 14.25 11.4518 14.25 8C14.25 4.54822 11.4518 1.75 8 1.75C4.54822 1.75 1.75 4.54822 1.75 8C1.75 11.4518 4.54822 14.25 8 14.25ZM8 15.25C12.0041 15.25 15.25 12.0041 15.25 8C15.25 3.99594 12.0041 0.75 8 0.75C3.99594 0.75 0.75 3.99594 0.75 8C0.75 12.0041 3.99594 15.25 8 15.25ZM8 5.75C8.48325 5.75 8.875 5.35825 8.875 4.875C8.875 4.39175 8.48325 4 8 4C7.51675 4 7.125 4.39175 7.125 4.875C7.125 5.35825 7.51675 5.75 8 5.75ZM8.5 7.43555C8.5 7.1594 8.27614 6.93555 8 6.93555C7.72386 6.93555 7.5 7.1594 7.5 7.43555V11.143C7.5 11.4191 7.72386 11.643 8 11.643C8.27614 11.643 8.5 11.4191 8.5 11.143V7.43555Z" fill="#171717"/>
						</g>
						<defs>
							<clipPath id="clip0_3360_13841">
								<rect width="16" height="16" fill="white"/>
							</clipPath>
						</defs>
					</svg>
					<div>
						<span class="title">
							Your trial ends in ${trial_end_string}.
						</span>
						<span class="description">
							${
								isFCUser
									? "Please upgrade for uninterrupted services"
									: "Please contact your system administrator to upgrade your plan."
							}
						</span>
					</div>
				</div>
				${
					isFCUser
						? `<button type="button"
					class="upgrade-plan-button px-2 py-1"
				>
					<svg width="17" height="16" viewBox="0 0 17 16" fill="none" xmlns="http://www.w3.org/2000/svg">
						<path fill-rule="evenodd" clip-rule="evenodd" d="M6.2641 1C5.5758 1 4.97583 1.46845 4.80889 2.1362L3.57555 7.06953C3.33887 8.01625 4.05491 8.93333 5.03077 8.93333H7.50682L6.72168 14.4293C6.68838 14.6624 6.82229 14.8872 7.04319 14.9689C7.26408 15.0507 7.51204 14.9671 7.63849 14.7684L13.2161 6.00354C13.6398 5.33782 13.1616 4.46667 12.3725 4.46667H9.59038L10.3017 1.62127C10.3391 1.4719 10.3055 1.31365 10.2108 1.19229C10.116 1.07094 9.97063 1 9.81666 1H6.2641ZM5.77903 2.37873C5.83468 2.15615 6.03467 2 6.2641 2H9.17627L8.46492 4.8454C8.42758 4.99477 8.46114 5.15302 8.55589 5.27437C8.65064 5.39573 8.79602 5.46667 8.94999 5.46667H12.3725L8.0395 12.2757L8.5783 8.50404C8.5988 8.36056 8.55602 8.21523 8.46105 8.10573C8.36608 7.99623 8.22827 7.93333 8.08332 7.93333H5.03077C4.70548 7.93333 4.4668 7.62764 4.5457 7.31207L5.77903 2.37873Z" fill="currentColor"/>
					</svg>
					${__("Upgrade plan")}
				</button>`
						: ""
				}
			</div>
`);
}
