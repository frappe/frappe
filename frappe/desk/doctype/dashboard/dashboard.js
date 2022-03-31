// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Dashboard', {
	refresh: function (frm) {
		frm.trigger('get_global_filters');
		frm.add_custom_button(__("Show Dashboard"),
			() => frappe.set_route('dashboard-view', frm.doc.name)
		);

		if (!frappe.boot.developer_mode && frm.doc.is_standard) {
			frm.disable_form();
		}

		frm.set_query("chart", "charts", function () {
			return {
				filters: {
					is_public: 1,
				}
			};
		});

		frm.set_query("card", "cards", function () {
			return {
				filters: {
					is_public: 1,
				}
			};
		});
	},

	setup: function (frm) {
		frm.set_query("chart", "global_filters", function (doc, cdt, cdn) {
			var d = locals[cdt][cdn];
			let filter = frm.global_filters.find(filter => filter.label == d.filter)
			return {
				filters: {
					"name": ['in', filter.charts]
				}
			};
		});
	},

	get_global_filters: function (frm) {
		let charts = frm.doc.charts;
		frm.global_filters = [];
		if (charts[0].chart) {
			charts.map(({ chart }) => {
				frappe.model.with_doc('Dashboard Chart', chart, function () {
					let chart_doc = frappe.model.get_doc('Dashboard Chart', chart);
					frappe.dashboard_utils.get_filters_for_chart_type(chart_doc).then(filters => {
						if (filters) {
							if (frm.global_filters.length == 0) {
								frm.global_filters = filters.map(obj => ({ ...obj }));
								frm.global_filters.map(filter => { filter.count = 0; filter.charts = [] })
							}

							filters.map(function (filter) {
								let exist = frm.global_filters.find(el => el.fieldname == filter.fieldname);
								let match = false;
								//check if the filter has same options and get data function
								if (exist) {
									if (exist.get_data && filter.get_data) {
										if (exist.get_data == filter.get_data) {
											match = true;
										}
									}
									if (exist.options && filter.options) {
										if (exist.options == filter.options || exist.options.length == filter.options.length) {
											match = true;
										}
									}
								}

								if (exist && match) {
									if (exist.charts.includes(chart)) return;
									exist.charts.push(chart)
									exist.count++
								}
								else {
									filter.count = 1;
									filter.charts = [chart]
									frm.global_filters.push({ ...filter })
								}
							})
							frm.trigger("set_global_filters");
						}
					})
				})
			})
		}
	},

	set_global_filters: function (frm) {
		var df_filter = frappe.meta.get_docfield("Dashboard Global Filters", "filter", cur_frm.doc.name);
		df_filter.options = [];
		frm.global_filters.map((filter) => {
			if (filter.count >= 2) {
				df_filter.options.push(filter.label)
			}
		})
		frm.toggle_display('global_filters', df_filter.options.length > 0);
	},
});

frappe.ui.form.on("Dashboard Chart Link", {
	chart: function (frm, cdt, cdn) {
		if (locals[cdt][cdn].chart) frm.trigger("get_global_filters");
	},

	charts_remove: function (frm, cdt, cdn) {
		frm.trigger("get_global_filters");
	}
});

frappe.ui.form.on("Dashboard Global Filters", {
	filter: function (frm, cdt, cdn) {
		let doc = locals[cdt][cdn];
		let filter = frm.global_filters.find(filter => filter.label == doc.filter);

		frappe.model.set_value(cdt, cdn, "fieldtype", filter.fieldtype);
		frappe.model.set_value(cdt, cdn, "chart_filter_name", filter.fieldname);
		frappe.model.set_value(cdt, cdn, "fieldtype", filter.fieldtype)
		if (filter.options) frappe.model.set_value(cdt, cdn, "options", JSON.stringify(filter.options));
		if (filter.get_data) frappe.model.set_value(cdt, cdn, "get_data", filter.get_data);
	}
});
