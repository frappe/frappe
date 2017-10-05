// special features for offline link field
frappe.ui.form.ControlOfflineLink = frappe.ui.form.ControlLink.extend({
	search_in_cache: function(doctype, search_value) {
		frappe.offline_mode = true;
		if (frappe.offline_data && frappe.offline_data[doctype]) {
			const cache_data = frappe.offline_data[doctype];
			let results = [];

			if(search_value && search_value != '') {
				results =  $.grep(cache_data, (data) => {
					if ( (data.value.toLowerCase().includes(search_value)) 
						|| (data.description.toLowerCase().includes(search_value)) ) {
							return data;
					}
				});
			} else {
				results = cache_data.slice(0, 20);
			}

			this.update_awesomplete_list(doctype, search_value, results);
		}
	},
	set_selected_value: function() {
		var me = this;
		if(me.selected) {
			me.selected = false;
			return;
		}
		var value = me.get_input_value();
		if (value!==me.last_value && !frappe.offline_mode) {
			me.parse_validate_and_set_in_model(value);
		} else {
			return frappe.run_serially([
				() => me.set_model_value(value),
				() => {
					me.set_mandatory && me.set_mandatory(value);

					if(me.df.change || me.df.onchange) {
						// onchange event specified in df
						return (me.df.change || me.df.onchange).apply(me);
					}
				}
			]);
		}
	}
});
