frappe.pages['calendar'].on_page_load = function(wrapper) {
	
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Master Calendar',
		single_column: false
		
	});

	frappe.require(['assets/frappe/js/lib/fullcalendar/fullcalendar.min.css',
		'assets/frappe/js/lib/bootstrap.min.js',
		'assets/frappe/js/lib/fullcalendar/fullcalendar.min.js'], function() {
			const me = this;
			window.x = page
			window.this = this
			this.$nav = page.sidebar.html(`<ul class="module-sidebar-nav overlay-sidebar nav nav-pills nav-stacked"></ul><div></div>`);
			this.$sidebar_list = page.sidebar.find('ul');
			// list of all standrd calendars
			var head_li = $(`<li class="text-muted checkbox">`).appendTo(this.$sidebar_list);
			var check = $('<input type="checkbox">').appendTo(head_li).on("click",function(){
				if($(this).prop("checked")){
					$('.checkbox > input').each(function() {
						$(this).prop("checked", true);
					});
					me.$cal.fullCalendar("refetchEvents");
				}
				else{
					$('.checkbox > input').each(function() {
						$(this).prop("checked", false);
					});
					me.$cal.fullCalendar("refetchEvents");
				}
			});
			var label = $('<label>').html("Standard Calendars").appendTo(head_li);

			//window.x = this.$more = page.sidebar.find("div");
			
			/*select all button
			var li=$("<li>").appendTo(this.$sidebar_list);
			var div=$("<div class ='row'>").appendTo(li)
			
			$("<div class='col-sm-6'><button class='btn btn-default btn-xs' >Select All</button></div>").on("click",function(){
				$('.checkbox > input').each(function() {
					$(this).prop("checked", true);
					me.$cal.fullCalendar("refetchEvents");
				});
			}).appendTo(div);
			
			//Unselct all btn
			$("<div class='col-sm-6'><button class='btn btn-default btn-xs' >Unselect All</button></div>").on("click",function(){
				$('.checkbox > input').each(function() {
					$(this).prop("checked", false);
					me.$cal.fullCalendar("refetchEvents");
				});
			}).appendTo(div)*/
			
			//fetching and creating checkboxes
			$.each(frappe.boot.calendars, function(i, doctype) {
				var li = $(`<li class="checkbox" style="padding-top: 0px">`);
				if(doctype == "Event"){
					
					var check = $('<input type="checkbox" class="cal" checked value="'+doctype+'">').appendTo(li).on("click",function(){
						me.$cal.fullCalendar("refetchEvents")
					});
				}
				else{
					var check = $('<input type="checkbox" class="cal" value="'+doctype+'">').appendTo(li).on("click",function(){
						me.$cal.fullCalendar("refetchEvents")
						
					});}
					var label = $('<label>').html(doctype).appendTo(li);
					li.appendTo(me.$sidebar_list);
				});

				//dropdown for more calendars
				var caret=$(
					"<span class='text-muted cursor-pointer'>"+
						"More Calendars<span class='caret'></span>"+
					"</span>").appendTo(page.sidebar.find('div')).on("click",function(){
					span = $(this)
					return frappe.call({
						method: "frappe.core.page.calendar.calendar.get_all_calendars",
						type: "GET"
					}).then(r => {
						if($(".checkbox.custom").length == 0){
							for (doctype in r["message"]){
								if ($.inArray(r["message"][doctype],frappe.boot.calendars) == -1){
									var li = $(`<li class="checkbox custom" style="padding-top: 0px">`);
									var check = $('<input type="checkbox" class="cal" value="'+r["message"][doctype]+'">').appendTo(li).on("click",function(){
										me.$cal.fullCalendar("refetchEvents")
									})
									var label = $('<label>').html(r["message"][doctype]).appendTo(li);
									li.appendTo(me.$sidebar_list);
								}
							}
							span.html("Less Calendars<span class='caret caret-up'></span>");
						}
						else{
							$(".checkbox.custom").remove()
							span.html("More Calendars<span class='caret '></span>")
							me.$cal.fullCalendar("refetchEvents")
						}
				})
			});
				
				var calendar_opts = {

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
				start_param = get_system_datetime(start);
				end_param = get_system_datetime(end)
				var docinfo = [];
				$('.cal:checked').each(function() {
					docinfo.push($(this).attr('value'));
				});

				//methd for fetching the events.
				return frappe.call({
					method: "frappe.core.page.calendar.calendar.get_master_calendar_events",
					type: "GET",
					args : {
						'doctypeinfo': docinfo,
						'start' : start_param,
						'end': end_param
					}
				}).then(r => {
					var events = [];
					for (event in r["message"]){
						if ($('.cal:checked').length == 1){
							var heading = r["message"][event].title
						}
						else{
							var heading = r["message"][event].doctype+": "+r["message"][event].title
						}
						//after fetching pushing and maping events on calendar
						if($("input[value='"+r["message"][event].doctype+"']").prop("checked")){
							events.push({
								start: r["message"][event].start,
								end: r["message"][event].end,
								id: r["message"][event].id,
								title: heading,
								doctype: r["message"][event].doctype,
								color: r["message"][event].color, 
								textColor: r["message"][event].textColor,
								description: r["message"][event].description
							});
						}
					}
					callback(events)
				});
			},

			//Drag event (to create new Event)modal fade in
			select: function(startDate, endDate, jsEvent, view) {
				var checkboxes = $('.module-sidebar-nav input:checked');
				var interval = endDate-startDate;

				//identifying single day event
				if(interval > 86400000){
					if (checkboxes.length == 1){
						frappe.new_doc(checkboxes[0].value);
					}
					else if (checkboxes.length > 1){
						options = '';
						$('.module-sidebar-nav input:checked').each(function() {
							options += '\n'+$(this).attr('value');
						});
						
						//select doctype to create event
						frappe.prompt([
							{'fieldname': 'Doctype', 'fieldtype': 'Select', 'options': options,'label': 'Doctype', 'reqd': 1}  
						],
						function(values){
							frappe.new_doc(values.Doctype);
							
						},
						'Select Doctype',
						'Submit'
						)
			
					}
					else{
						frappe.msgprint("Select doctype to create calendar event")
					}
				}
			},

			//Event click action 
			eventClick: function(event,jsEvent) {
				//removing popover if present
				$(".popover.fade.bottom.in").remove();

				var t = $(jsEvent.target)
				// creating time html
				if(event.allDay){
					var timeHtml = "All Day"
				}
				else if(event.start.isSame(event.end, 'date', 'month', 'year')) {
					var timeHtml = event.start.format('LT')+" to "+event.end.format('LT')
				}
				else if(event.start.isSame(event.end, 'month', 'year')){
					var timeHtml = event.start.format("MMMM, ") + event.start.format('D')+" to "+ event.end.format('D')
				}
				else {
					var timeHtml = event.start.format('Do MMMM')+" to "+ event.end.format('Do MMMM')
				}

				timing = "<div class='mt-5'>" +
							"<div class='text-muted col-sm-2' style='padding-right: 0; margin-top: 6px;'>"+
								"<i class='fa fa-clock-o' aria-hidden='true'></i>"+
							"</div> "+
							"<div class='col-sm-9' style='padding-left: 0; margin-top: 5px;'>" + 
								timeHtml + 
							"</div>"+
						"</div>"

				var descr = event.description
				description = "<div class='mt-5'>"+
								"<div class='text-muted col-sm-2' style='padding-right: 0; margin-top: 6px; '>"+
									"<i class='fa fa-align-left' aria-hidden='true'></i>"+
								"</div> "+
								"<div class='col-sm-10' style='padding-left: 0; margin-top: 5px;'>" + 
									descr + 
								"</div>"+
							"</div>"

				//popover content
				var htmlContent = "<div class='row'>" +
									description +
								"</div>"+
								"<div class='row'>"+
									timing +
								"</div>"


				t.attr("data-toggle", "popover")
				t.attr("data-placement", "bottom")
				t.attr("title", event.title)
				t.attr("data-container", "body")
				t.attr("data-trigger", "focus")
				t.attr("z-index", 2000)
				t.popover({
					html: true,
					content: htmlContent
				}
				);
				t.popover("show");
				$(".popover.fade.bottom.in").css("min-width", "200px")

				//Edit buuton and its action
				$("<span ><button class='btn btn-default btn-sm btn-modal-close' style='margin-top:15px'>Edit</button></span>").on("click",function(){
					$(".popover.fade.bottom.in").remove();
					frappe.set_route("Form", event.doctype, event.id);
				}).appendTo($(".popover-content"));
			
			},
			eventDrop: function( event, delta, revertFunc, jsEvent, ui, view ) {
				update_event(event,revertFunc)
			 },
			 eventResize: function(event, delta, revertFunc) {
				update_event(event,revertFunc)
			},
			
		}

		//showing calendar 
		this.$cal = $("<div>").appendTo(page.body);
		this.$cal.fullCalendar( calendar_opts );

		// button for hiding and showing the weekends days
		var btnTitle = (calendar_opts.weekends) ? __('Hide Weekends') : __('Show Weekends');
		var btn = $(`<button class="btn btn-default btn-xs btn-weekend">${btnTitle}</button>`).on("click", function(){
			calendar_opts.weekends = !calendar_opts.weekends;
			var btnTitle = (calendar_opts.weekends) ? __('Hide Weekends') : __('Show Weekends');
			$(".btn-weekend").html(btnTitle);
			localStorage.removeItem('cal_weekends');
			localStorage.setItem('cal_weekends', calendar_opts.weekends);
			$cal.fullCalendar('option', 'weekends', calendar_opts.weekends);

		});
		//creating footnote
		this.footnote_area = frappe.utils.set_footnote(this.footnote_area, page.body,
			__("Select or drag across time slots to create a new event."));
		this.footnote_area.css({"border-top": "0px"});
		this.footnote_area.append(btn)

		frappe.require('assets/frappe/js/lib/fullcalendar/locale-all.js');
	});

	$('body').on('click', function (e) {
		//popover hiddingon putside click.
		if ($(e.target).data('toggle') !== 'popover'
			&& $(e.target).parents('.popover.in').length === 0) { 
			$('[data-toggle="popover"]').popover('hide');
		}
	});

	 function get_system_datetime(date) {
		date._offset = moment.user_utc_offset;
		return d= frappe.datetime.convert_to_system_tz(date);
	}
	
	function update_event(event){
		start = get_system_datetime(event.start)
		end = get_system_datetime(event.end)
		frappe.call({
			method: "frappe.core.page.calendar.calendar.update_event",
			type: "POST",
			args : {
				'start' : start,
				'end': end,
				'doctype': event.doctype,
				'name': event.id
			}
		}).then(r => {
			if(r["message"] == 0){
				frappe.msgprint("Unable to update the Event")
				revertFunc();
			}
		});
	}
	
}