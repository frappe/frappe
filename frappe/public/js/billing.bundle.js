let frappeCloudBaseEndpoint = "https://frappecloud.com";
let isFCUser = false;

$(document).ready(function () {
	const site_info = frappe.boot.site_info;
	if (site_info) {
		const trial_end_date = new Date(site_info.trial_end_date);
		frappeCloudBaseEndpoint = site_info.base_url;
		isFCUser = site_info.is_fc_user;

		const today = new Date();
		const diffTime = trial_end_date - today;
		const trial_end_days = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
		const trial_end_string =
			trial_end_days > 1 ? `${trial_end_days} days` : `${trial_end_days} day`;

		const banner_message = isFCUser
			? "Please upgrade for uninterrupted services"
			: "Please contact your system administrator to upgrade your plan.";
		let card_args = {
			title: `Your trial ends in ${trial_end_string}`,
			message: banner_message,
			outline: true,
			close_button: true,
			popper: true,
			primary_button_alignment: "right",
			dismiss_key: `${frappe.boot.site_info.name}_trial_card_time`,
			dismiss_it_for: "day",
		};
		let visiblity_condition =
			frappe.boot.is_fc_site &&
			!!frappe.boot.setup_complete &&
			!frappe.is_mobile() &&
			frappe.user.has_role("System Manager");
		if (visiblity_condition && isFCUser) {
			if (site_info.trial_end_date && trial_end_date > new Date()) {
				addChatBubble();
				toggleChatBubble(true);
			}
		}
		if (isFCUser) {
			$.extend(card_args, {
				primary_action_label: "Upgrade",
				primary_action_suffix_icon: "square-arrow-out-up-right",
				styles: {
					"sidebar-card-button-bg-color": "var(--surface-gray-2)",
					"sidebar-card-button-color": "var(--ink-gray-7)",
					"sidebar-card-button-outline": "var(--ink-gray-7)",
				},
				primary_action: () => {
					openFrappeCloudDashboard();
				},
			});
		}
		$(document).on("desktop_screen", function (event, data) {
			if (visiblity_condition) {
				if (site_info.trial_end_date && trial_end_date > new Date()) {
					card_args.parent = $(".icons-container").first();
					let banner_card = new frappe.ui.SidebarCard(card_args);
				}
				addManageBillingDropdown(data.desktop);

				$(".login-to-fc, .upgrade-plan-button").on("click", function () {
					openFrappeCloudDashboard();
				});
			}
		});
	}
});

function setErrorMessage(message) {
	$("#fc-login-error").text(message);
}

function addManageBillingDropdown(desktop) {
	desktop.add_menu_item({
		label: __("Manage Billing"),
		icon: "receipt-text",
		condition: function () {
			return frappe.boot.is_fc_site;
		},
		onClick: function () {
			return openFrappeCloudDashboard();
		},
	});
}
function openFrappeCloudDashboard() {
	window.open(
		`${frappeCloudBaseEndpoint}/dashboard/sites/${frappe.boot.site_info.name}`,
		"_blank"
	);
}

function addChatBubble() {
	const all_apps = frappe.utils.get_installed_apps();
	const desk_apps = ["erpnext", "hrms"];

	const apps_allowed = desk_apps.some((app) => all_apps.includes(app));
	if (apps_allowed) {
		let chat_banner = document.createElement("script");
		chat_banner.setAttribute("id", "chat_widget_trigger");
		chat_banner.innerHTML =
			'window.chatwootSettings = {"position":"right","launcherTitle":"Chat with us", darkMode: "auto"}; (function(d,t){var BASE_URL="https://chat.frappe.cloud";var g=d.createElement(t),s=d.getElementsByTagName(t)[0];g.src=BASE_URL+"/packs/js/sdk.js";g.async=true;s.parentNode.insertBefore(g,s);g.onload=function(){window.chatwootSDK.run({websiteToken:"LdmfJzftdJGEcFjoTqk8CrSq",baseUrl:BASE_URL})}})(document,"script");';
		document.body.append(chat_banner);
		const root = document.documentElement;
		root.style.setProperty("--s-700", "var(--gray-500)");

		// Add padding to the main section to avoid overlapping with the chat bubble
		const main_section = document.getElementsByClassName("main-section");

		if (main_section) {
			main_section[0].style.paddingBottom = "90px";
		}
	}
}

function toggleChatBubble(toggle) {
	if (toggle) {
		$(".woot-widget-holder").show();
		$("#cw-bubble-holder").show();
	} else {
		$(".woot-widget-holder").hide();
		$("#cw-bubble-holder").hide();
	}
}
