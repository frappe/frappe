frappe.pages['calendar'].on_page_load = function(wrapper) {
	//debugger;
	
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Master Calendar',
		single_column: false
		
	});
	frappe.require(['assets/frappe/js/lib/fullcalendar/fullcalendar.min.css',
		'assets/frappe/js/lib/fullcalendar/fullcalendar.min.js'], function() {
			const me = this
			window.x = me
			this.$nav = page.sidebar.html(`<ul class="module-sidebar-nav overlay-sidebar nav nav-pills nav-stacked"></ul>`);
			this.$sidebar_list = page.sidebar.find('ul');
			$(`<li class="text-muted" style="padding-bottom: 10px">
				Default Calendars:
				</li>`).appendTo(this.$sidebar_list);
			$.each(frappe.boot.calendars, function(i, doctype) {
				if(frappe.model.can_read(doctype)) {
					var li = $(`<li class="checkbox" style="padding-top: 0px">`);
					if(doctype == "Event"){
						
						var check = $('<input type="checkbox" checked value="'+doctype+'">').appendTo(li).on("click",function(){
							me.$cal.fullCalendar("refetchEvents")
						});
					}
					else{
					var check = $('<input type="checkbox" value="'+doctype+'">').appendTo(li).on("click",function(){
						me.$cal.fullCalendar("refetchEvents")
					
					});}
					var label = $('<label>').html(doctype).appendTo(li);
					li.appendTo(me.$sidebar_list);
					
				}
			});

			$(`<li class="text-muted">
				Custom Calendars:
				</li>`).appendTo(this.$sidebar_list);
		var calendar_opts = {
			dayClick: function(date) {
				alert(date);
			},
			header: {
				left: 'title',
				right: 'prev,today,next,agendaDay,agendaWeek,month'
			},
			weekends: true,
			events: function(start, end, timezone, callback) {
				var docinfo = "Event,Task,Sales Order,Holiday List"
				return frappe.call({
					method: "frappe.core.page.calendar.calendar.get_master_calendar_events",
					type: "GET",
					args : {
						'doctypeinfo': docinfo
					}
				}).then(r => {
					var events = [];
					for (event in r["message"]){
						if($("input[value='"+r["message"][event].title+"']").prop("checked")){
							events.push({
								start: r["message"][event].start,
								end: r["message"][event].end,
								title: r["message"][event].title,
								color: r["message"][event].color // will be parsed
							});
						}
					}
					callback(events)
				});

			},
			eventClick: function(event) {
				console.log("Hello")
			
			}

		}


		this.$cal = $("<div>").appendTo(page.body);
		
		this.$cal.fullCalendar( calendar_opts );

		var btnTitle = (calendar_opts.weekends) ? __('Hide Weekends') : __('Show Weekends');
		var btn = $(`<button class="btn btn-default btn-xs btn-weekend">${btnTitle}</button>`).on("click", function(){
			debugger;
			calendar_opts.weekends = !calendar_opts.weekends;
			var btnTitle = (calendar_opts.weekends) ? __('Hide Weekends') : __('Show Weekends');
			$(".btn-weekend").html(btnTitle);
			localStorage.removeItem('cal_weekends');
			localStorage.setItem('cal_weekends', calendar_opts.weekends);
			$cal.fullCalendar('option', 'weekends', calendar_opts.weekends);

			console.log(calendar_opts)

		});


		this.footnote_area = frappe.utils.set_footnote(this.footnote_area, page.body,
			__("Select or drag across time slots to create a new event."));
		this.footnote_area.css({"border-top": "0px"});
		this.footnote_area.append(btn)

		

		//setup_view_mode_button(defaults);
		
		frappe.require('assets/frappe/js/lib/fullcalendar/locale-all.js');


	});

	/*const setup_view_mode_button = function(defaults) {
		var me = this;
		$(me.footnote_area).find('.btn-weekend').detach();
		let btnTitle = (defaults.weekends) ? __('Hide Weekends') : __('Show Weekends');
		const btn = `<button class="btn btn-default btn-xs btn-weekend">${btnTitle}</button>`;
		me.footnote_area.append(page.body);
	};*/
}