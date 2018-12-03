frappe.pages['calendar'].on_page_load = function(wrapper) {
	//debugger;
	
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Master Calendar',
		single_column: false
		
	});

	frappe.require(['assets/frappe/js/lib/fullcalendar/fullcalendar.min.css',
		'assets/frappe/js/lib/fullcalendar/fullcalendar.min.js'], function() {
			const me = this;
			this.$nav = page.sidebar.html(`<ul class="module-sidebar-nav overlay-sidebar nav nav-pills nav-stacked"></ul>`);
			this.$sidebar_list = page.sidebar.find('ul');
			// list of all standrd calendars
			$(`<li class="text-muted" style="padding-bottom: 10px">
				Standard Calendars:
				</li>`).appendTo(this.$sidebar_list);
			//fetching and creating checkboxes
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

			// list of custom calendar covered soon
			/*$(`<li class="text-muted">
				Custom Calendars:
				</li>`).appendTo(this.$sidebar_list);*/

		var calendar_opts = {
			//day click action
			dayClick: function(date) {
				alert(date);
			},

			//header region which contains monlty,weekly,and daily views 
			header: {
				left: 'title',
				right: 'prev,today,next,agendaDay,agendaWeek,month'
			},

			weekends: true,
			selectable: true,
			editable: true,
			selectable: true,
			forceEventDuration: true,
			nowIndicator: true,

			// for mapping events into calendar
			events: function(start, end, timezone, callback) {
				var docinfo = '';
				$('.module-sidebar-nav input:checked').each(function() {
					docinfo += $(this).attr('value')+',';
				});
				//methd for fetching the events.
				return frappe.call({
					method: "frappe.core.page.calendar.calendar.get_master_calendar_events",
					type: "GET",
					args : {
						'doctypeinfo': docinfo
					}
				}).then(r => {
					var events = [];
					console.log(r["message"])
					for (event in r["message"]){
						//after fetching pushing and maping events on calendar
						if($("input[value='"+r["message"][event].doctype+"']").prop("checked")){
							events.push({
								start: r["message"][event].start,
								end: r["message"][event].end,
								id: r["message"][event].id,
								title: r["message"][event].title,
								color: r["message"][event].color, 
								textColor: r["message"][event].textColor
							});
						}
					}
					callback(events)
				});
			},

			//Event click action 
			select: function(startDate, endDate, jsEvent, view) {
				alert(endDate);
				},
			//Drag event
			eventClick: function(event) {
				window.x = event;
				frappe.msgprint("<ul>"
						+ "<li>Name: "+event.id+"</li>"
						+ "<li>"+event.title+"</li>"
						+ "<li>Start: "+event.start._i+"</li>"
				+ "</ul>", 'Events Details');
			
			}
		}

		this.$cal = $("<div>").appendTo(page.body);
		
		this.$cal.fullCalendar( calendar_opts );
		// button for hiding and showing the weekends days
		var btnTitle = (calendar_opts.weekends) ? __('Hide Weekends') : __('Show Weekends');
		var btn = $(`<button class="btn btn-default btn-xs btn-weekend">${btnTitle}</button>`).on("click", function(){
			debugger;
			calendar_opts.weekends = !calendar_opts.weekends;
			var btnTitle = (calendar_opts.weekends) ? __('Hide Weekends') : __('Show Weekends');
			$(".btn-weekend").html(btnTitle);
			localStorage.removeItem('cal_weekends');
			localStorage.setItem('cal_weekends', calendar_opts.weekends);
			$cal.fullCalendar('option', 'weekends', calendar_opts.weekends);

		});

		this.footnote_area = frappe.utils.set_footnote(this.footnote_area, page.body,
			__("Select or drag across time slots to create a new event."));
		this.footnote_area.css({"border-top": "0px"});
		this.footnote_area.append(btn)

		frappe.require('assets/frappe/js/lib/fullcalendar/locale-all.js');
	});
}