// Copyright (c) 2022, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Error Log", {
	refresh: function (frm) {
		frm.disable_save();

		if (frm.doc.fingerprint) {
			frm.add_custom_button(__("Show Similar Errors"), function () {
				frappe.set_route("List", "Error Log", { fingerprint: frm.doc.fingerprint });
			});
			render_fingerprint_stats(frm);
		}

		if (frm.doc.reference_doctype && frm.doc.reference_name) {
			frm.add_custom_button(__("Open reference document"), function () {
				frappe.set_route("Form", frm.doc.reference_doctype, frm.doc.reference_name);
			});
		}
	},
});

function render_fingerprint_stats(frm) {
	const wrapper = frm.get_field("fingerprint_stats").$wrapper;
	wrapper.empty().append(`<div class="text-muted">${__("Loading error stats...")}</div>`);

	frappe.call({
		method: "frappe.core.doctype.error_log.error_log.get_fingerprint_stats",
		type: "GET",
		cache: true,
		args: { fingerprint: frm.doc.fingerprint },
		callback: function (r) {
			const stats = r.message;
			if (!stats || !stats.count) {
				wrapper.empty();
				return;
			}
			wrapper.empty().append(get_stats_html(stats));

			// Show similar errors on clicking the occurrences card
			wrapper.find("[data-action='show-similar']").on("click", () => {
				frappe.set_route("List", "Error Log", { fingerprint: frm.doc.fingerprint });
			});

			render_timeline_chart(wrapper.find(".fingerprint-timeline")[0], stats.timeline);
		},
	});
}

function get_stats_html(stats) {
	const number_card = (label, value, action = "") => `
		<div class="fingerprint-stat-card" ${action}>
			<div class="fingerprint-stat-label">${label}</div>
			<div class="fingerprint-stat-value">${value}</div>
		</div>`;

	return $(`
		<div class="fingerprint-stats">
			<div class="fingerprint-stat-cards">
				${number_card(
					__("Occurrences"),
					format_number(stats.count, null, 0),
					`data-action="show-similar" style="cursor: pointer;"`
				)}
				${number_card(__("First Seen"), frappe.datetime.comment_when(stats.first_seen))}
				${number_card(__("Last Seen"), frappe.datetime.comment_when(stats.last_seen))}
			</div>
			<div class="fingerprint-timeline-wrapper">
				<div class="fingerprint-stat-label">${__("Occurrences (last 30 days)")}</div>
				<div class="fingerprint-timeline"></div>
			</div>
		</div>
		<style>
			.fingerprint-stats { margin-bottom: var(--margin-md); }
			.fingerprint-stat-cards {
				display: flex; gap: var(--margin-sm); flex-wrap: wrap; margin-bottom: var(--margin-sm);
			}
			.fingerprint-stat-card {
				flex: 1; min-width: 120px; padding: var(--padding-md);
				background: var(--subtle-fg); border-radius: var(--radius-lg);
			}
			.fingerprint-stat-label {
				font-size: var(--text-sm); color: var(--text-muted); margin-bottom: 4px;
			}
			.fingerprint-stat-value { font-size: var(--text-xl); font-weight: 600; }
			.fingerprint-timeline-wrapper {
				padding: var(--padding-sm) var(--padding-md);
				background: var(--subtle-fg); border-radius: var(--radius-lg);
			}
		</style>
	`);
}

function render_timeline_chart(container, timeline) {
	if (!container) return;

	// Build a continuous daily series over the last 30 days so gaps show as zeros.
	const counts = {};
	for (const row of timeline || []) {
		counts[row.day] = row.count;
	}

	const labels = [];
	const values = [];
	const today = frappe.datetime.now_date();
	for (let i = 29; i >= 0; i--) {
		const day = frappe.datetime.add_days(today, -i);
		labels.push(frappe.datetime.str_to_user(day));
		values.push(counts[day] || 0);
	}

	new frappe.Chart(container, {
		type: "bar",
		height: 160,
		colors: ["#e24c4c"],
		axisOptions: { xIsSeries: true, xAxisMode: "tick" },
		data: {
			labels: labels,
			datasets: [{ name: __("Occurrences"), values: values }],
		},
	});
}
