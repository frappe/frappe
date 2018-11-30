frappe.pages['calendar'].on_page_load = function(wrapper) {
	
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Master Calendar',
		single_column: true
		
	});
	frappe.require('assets/frappe/js/lib/fullcalendar/fullcalendar.min.css');
	frappe.require('assets/frappe/js/lib/fullcalendar/fullcalendar.min.js', function (){
		var calendar_opts = {
			dayClick: function(date) {
				alert(date);
			},
			header: {
				left: 'title',
				right: 'prev,today,next,agendaDay,agendaWeek,month'
			},
			weekends: true,
			events: function(start, end, timezone) {
				var docinfo = "Event,Task,Sales Order,Holiday List"
				return frappe.call({
					method: "frappe.core.page.calendar.calendar.get_master_calendar_events",
					type: "GET",
					args : {
						'doctypeinfo': docinfo
					}
				}).then(r => {
					console.log(r);
				});
			}
			
		}
		var btnTitle = (calendar_opts.weekends) ? __('Hide Weekends') : __('Show Weekends');
		var btn = $(`<button class="btn btn-default btn-xs btn-weekend">${btnTitle}</button>`).on("click", function(){
			alert("Hello");
			calendar_opts.weekends = false;
			this.$cal.fullCalendar("destroy");
			this.$cal.fullCalendar(calendar_opts);
		});
		console.log(btn)
		this.$cal = $("<div>").appendTo(page.body);
		window.x = this.$cal;
		this.footnote_area = frappe.utils.set_footnote(this.footnote_area, page.body,
			__("Select or drag across time slots to create a new event."));
		this.footnote_area.css({"border-top": "0px"});
		this.footnote_area.append(btn)

		

		//setup_view_mode_button(defaults);
		

		this.$cal.fullCalendar( calendar_opts );

	});
	frappe.require('assets/frappe/js/lib/fullcalendar/locale-all.js');

	/*const setup_view_mode_button = function(defaults) {
		var me = this;
		$(me.footnote_area).find('.btn-weekend').detach();
		let btnTitle = (defaults.weekends) ? __('Hide Weekends') : __('Show Weekends');
		const btn = `<button class="btn btn-default btn-xs btn-weekend">${btnTitle}</button>`;
		me.footnote_area.append(page.body);
	};*/
}