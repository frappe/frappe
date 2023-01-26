$(document).on("startup", async () => {
	if (!frappe.boot.setup_complete || !frappe.user.has_role("System Manager")) {
		return;
	}

	const expiry = frappe.boot.subscription_expiry;

	if (expiry) {
		let diff_days =
			frappe.datetime.get_day_diff(cstr(expiry), frappe.datetime.get_today()) - 1;

		let subscription_string = __(
			`Your subscription will end in ${cstr(diff_days).bold()} ${
				diff_days > 1 ? "days" : "day"
			}. After that your site will be suspended.`
		);

		let $bar = $(`
		<div
			class="position-fixed top-100 start-20 translate-middle shadow sm:rounded-lg py-2"
			style="left: 10%; bottom:20px; width:80%; margin: auto; text-align: center; border-radius: 10px; background-color: rgb(240 249 255); z-index: 1"
		>
			<div
				style="display: flex; align-items: center; justify-content: space-between; text-align: center;"
				class="text-muted"
			>
					<p style="float: left; margin: auto; font-size: 17px">${subscription_string}</p>
					<div style="display: flex; align-items: center; justify-content: space-between">
					<button
						type="button"
						class="button-renew px-4 py-2 border border-transparent text-white hover:bg-indigo-700 focus:outline-none focus:ring-offset-2 focus:ring-indigo-500"
						style="background-color: #0089FF; border-radius: 5px; margin-right: 10px; height: fit-content;"
					>
					Subscribe
					</button>
					<a
						type="button"
						class="dismiss-upgrade text-muted" data-dismiss="modal" aria-hidden="true" style="font-size:30px; margin-bottom: 5px; margin-right: 10px"
					>
					\u00d7
					</a>
				</div>
			</div>
		</div>
		`);

		$("footer").append($bar);

		$bar.find(".dismiss-upgrade").on("click", () => {
			$bar.remove();
		});

		$bar.find(".button-renew").on("click", () => {
			redirectToUrl();
		});
	}
});

function redirectToUrl() {
	frappe.call({
		method: "frappe.utils.subscription.remote_login",
		callback: (url) => {
			if (url.message !== false) {
				window.open(url.message, "_blank");
			} else {
				frappe.msgprint({
					title: __("Message"),
					indicator: "orange",
					message: __("No active subscriptions found."),
				});
			}
		},
	});
}

$.extend(frappe.ui.toolbar, {
	redirectToUrl() {
		redirectToUrl();
	},
});
