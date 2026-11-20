frappe.provide("frappe.ui.talk_to_us");

// Lazy-loaded from billing.bundle.js on first click, so the trial banner's dialog stays
// out of the desk bundle every user downloads.

const BUSINESS_TOOLS = [
	"",
	"Tally",
	"Odoo",
	"Zoho",
	"QuickBooks",
	"SAP",
	"Spreadsheets",
	"No system yet",
	"Other",
];
const TEAM_SIZES = ["", "1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"];
const DETAIL_FIELDS = ["company", "mobile_no", "note"];
const PREPARE_FIELDS = ["current_business_tool", "no_of_employees"];

frappe.ui.talk_to_us.show = function () {
	let requested = false;

	const stepper = new frappe.ui.Stepper({
		steps: [{ label: __("Your details") }, { label: __("Help us prepare") }],
		current: 0,
		compact: frappe.is_mobile(),
		is_locked: (index) => index === 1 && !requested,
	});

	const dialog = new frappe.ui.Dialog({
		title: __("Talk to us"),
		sheet_on_mobile: true,
		fields: [
			{ fieldtype: "HTML", fieldname: "stepper" },
			{ fieldtype: "HTML", fieldname: "thanks", hidden: 1 },
			{
				fieldtype: "Data",
				fieldname: "company",
				label: __("Company"),
				reqd: 1,
				default: frappe.boot.sysdefaults?.company,
			},
			{
				fieldtype: "Phone",
				fieldname: "mobile_no",
				label: __("Phone"),
				reqd: 1,
			},
			{
				fieldtype: "Small Text",
				fieldname: "note",
				label: __("Anything our consultant should know to help you better?"),
				placeholder: __(
					"e.g. what your business does, what you use today, what you want sorted before your trial ends"
				),
			},
			{
				fieldtype: "Select",
				fieldname: "current_business_tool",
				label: __("What do you run your business on today?"),
				options: BUSINESS_TOOLS.join("\n"),
				hidden: 1,
			},
			{
				fieldtype: "Select",
				fieldname: "no_of_employees",
				label: __("Team size"),
				options: TEAM_SIZES.join("\n"),
				hidden: 1,
			},
		],
		primary_action_label: __("Request a call"),
		primary_action_loading_label: __("Sending"),
		primary_action: (values) => request_call(values),
	});

	dialog.fields_dict.stepper.$wrapper.append(stepper.$el);

	function show_thanks(description) {
		dialog.fields_dict.thanks.$wrapper.empty().append(
			frappe.ui.empty_state({
				icon: "circle-check",
				title: __("Thank you for taking time to contact us"),
				description: description,
			})
		);
		dialog.set_df_property("thanks", "hidden", 0);
	}

	// the phone control carries its own country code, so the server is the only validator
	function request_call(values) {
		const request = {
			company: values.company,
			mobile_no: values.mobile_no,
			note: values.note,
		};

		return send(request).then(() => {
			requested = true;
			for (const fieldname of DETAIL_FIELDS) {
				dialog.set_df_property(fieldname, "reqd", 0);
				dialog.set_df_property(fieldname, "hidden", 1);
			}
			show_thanks(__("An expert will reach out to you shortly."));
			ask_to_prepare(request);
		});
	}

	function ask_to_prepare(request) {
		for (const fieldname of PREPARE_FIELDS) {
			dialog.set_df_property(fieldname, "hidden", 0);
		}
		stepper.set_current(1);

		dialog.set_primary_action(__("Save"), () => {
			const answers = {};
			for (const fieldname of PREPARE_FIELDS) {
				const value = dialog.get_value(fieldname);
				if (value) answers[fieldname] = value;
			}

			if (!Object.keys(answers).length) {
				return finish(__("An expert will reach out to you shortly."));
			}

			return send({ ...request, ...answers }).then(() =>
				finish(
					__(
						"Thanks, we have added this for your consultant. An expert will reach out to you shortly."
					)
				)
			);
		});
		dialog.set_secondary_action_label(__("Skip"));
		dialog.set_secondary_action(() => finish(__("An expert will reach out to you shortly.")));
	}

	function finish(description) {
		for (const fieldname of PREPARE_FIELDS) {
			dialog.set_df_property(fieldname, "hidden", 1);
		}
		dialog.set_df_property("stepper", "hidden", 1);
		show_thanks(description);
		dialog.get_secondary_btn().addClass("hide");
		dialog.set_primary_action(__("Close"), () => dialog.hide());
	}

	dialog.show();
	return dialog;
};

function send(request) {
	return frappe.xcall(
		"frappe.integrations.frappe_providers.frappecloud_billing.consulting_request",
		request
	);
}
