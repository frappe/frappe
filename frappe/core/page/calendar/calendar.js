frappe.pages['calendar'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Master Calendar',
		single_column: true
		
	});
	frappe.require('assets/frappe/js/lib/fullcalendar/fullcalendar.min.css');
	frappe.require('assets/frappe/js/lib/fullcalendar/fullcalendar.min.js', function (){
		this.$cal = $("<div>").appendTo(page.body);
		this.$cal.fullCalendar( {
			dayClick: function(date) {
				alert(date);
			},
			events: function(start, end, timezone) {
				return frappe.call({
					method: "frappe.desk.doctype.event.event.get_events",
					type: "GET",
					args : {
						start: "2018-10-28 00:00:00",
						end: "2018-12-09 00:00:00",
					}
				}).then(r => {
					console.log(r.message);
					var events = r.message ;
				});
			}
		}
		);
	});
	frappe.require('assets/frappe/js/lib/fullcalendar/locale-all.js');

}