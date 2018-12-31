frappe.pages['calendar'].on_page_load = function(wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Calendar',
		single_column: false

	});
};

frappe.pages['calendar'].on_page_show = (wrapper) => {
	var route = frappe.get_route();

	if (frappe.pages.calendar.loaded) {
		update_calendar(frappe.pages.calendar.page.sidebar, wrapper , route);
		return;
	}

	frappe.require([
		'assets/frappe/js/lib/fullcalendar/fullcalendar.min.css',
		'/assets/js/fullcalendar.js',
		'assets/frappe/js/lib/fullcalendar/locale-all.js'
	], function(){
		create_calendar(wrapper);
	});
};

$('body').on('click', function(e) {
	if ($(e.target).data('toggle') !== 'popover' &&
	$(e.target).parents('.popover.in').length === 0){
		$('[data-toggle="popover"]').popover('hide');
	}
});

function get_system_datetime(date) {
	date._offset = moment.user_utc_offset;
	return frappe.datetime.convert_to_system_tz(date);
}

function update_event(event, revertFunc) {
	frappe.call({
		method: "frappe.core.page.calendar.calendar.update_event",
		type: "POST",
		args: {
			'start': get_system_datetime(event.start),
			'end': get_system_datetime(event.end),
			'doctype': event.doctype,
			'name': event.id
		}
	}).then(r => {
		if (!r.message) {
			revertFunc();
			frappe.throw("Unable to update the Event");
		}
	});
}

function create_event(start, end) {
	const enabled_doctypes = get_checked_calendars();

	if (enabled_doctypes.length === 1) {
		const doctype = enabled_doctypes[0];
		create_new_event(doctype,start,end);
	} else if (enabled_doctypes.length > 1) {
		frappe.prompt([{
			'fieldname': 'doctype',
			'fieldtype': 'Select',
			'options': enabled_doctypes,
			'label': 'Type',
			'reqd': 1
		}],
		function({ doctype }) {
			create_new_event(doctype,start,end);
		},
		__('Select Document type'),
		__('Submit')
		);
	} else {
		frappe.msgprint("Select document type to create calendar event");
	}
}

function create_new_event(doctype,start,end) {
	get_field_map(doctype)
		.then(event_info => {
			var event = frappe.model.get_new_doc(doctype);
			event[event_info.field_map.start] = get_system_datetime(start);
			event[event_info.field_map.end] = get_system_datetime(end);
			frappe.set_route("Form", doctype, event.name);
		});
}

function get_field_map(doctype) {
	return new Promise(resolve => {
		frappe.call('frappe.core.page.calendar.calendar.get_field_map', { doctype })
			.then(r => resolve(r.message));
	});
}

function get_checked_calendars() {
	return Array.from($('.cal:checked').map((_, r) => r.value));
}

function set_css(cal){
	// flatify buttons
	cal.find("fc-right").addClass("float-right");
	cal.find("button.fc-state-default")
		.removeClass("fc-state-default")
		.addClass("btn btn-default");

	cal.find(".fc-button-group").addClass("btn-group");

	cal.find('.fc-prev-button span')
		.attr('class', '').addClass('fa fa-chevron-left');
	cal.find('.fc-next-button span')
		.attr('class', '').addClass('fa fa-chevron-right');

	var btn_group = cal.find(".fc-button-group");
	btn_group.find(".fc-state-active").addClass("active");

	btn_group.find(".btn").on("click", function(){
		btn_group.find(".btn").removeClass("active");
		$(this).addClass("active");
	});
}

function select_all(sidebar, cal){
	var head_li = $(`<li class="text-muted checkbox">`).appendTo(sidebar);
	$('<input type="checkbox" class="all">').appendTo(head_li).on("click", function(){
		if($(this).prop("checked")){
			$('.checkbox > input').each(function(){
				$(this).prop("checked", true);
			});
			cal.fullCalendar("refetchEvents");
		} else {
			$('.checkbox > input').each(function(){
				$(this).prop("checked", false);
			});
			cal.fullCalendar("refetchEvents");
		}
	});
	$('<label>').html("All").appendTo(head_li);
}

function create_checkboxes(sidebar, cal){
	//fetching and creating checkboxes
	var default_doctype = frappe.get_route();
	$.each(frappe.boot.calendars, function(i, doctype){
		if(frappe.model.can_read(doctype)){
			var li = $(`<li class="checkbox" style="padding-top: 0px">`);
			if (default_doctype[1] === doctype){
				$('<input type="checkbox" class="cal" checked value="' + doctype + '">').appendTo(li).on("click", function(){
					cal.fullCalendar("refetchEvents");
				});
			} else if (!default_doctype[1] && doctype === "Event"){
				$('<input type="checkbox" class="cal" checked value="' + doctype + '">').appendTo(li).on("click", function(){
					cal.fullCalendar("refetchEvents");
				});
			} else{
				$('<input type="checkbox" class="cal" value="' + doctype + '">').appendTo(li).on("click", function(){
					cal.fullCalendar("refetchEvents");
				});
			}
			$('<label>').html(doctype).appendTo(li);
			li.appendTo(sidebar);
		}
	});
	if($('.cal').length < 5){
		$('.all').parent().hide();
	}
}

function get_more_calendars(sidebar, cal, page){
	//dropdown for more calendars
	const more_calendar_text = __('More Calendars');
	$(`<span class='text-muted cursor-pointer'>
	${more_calendar_text}
	<span class='caret'></span>
	</span>`).appendTo(page.sidebar.find('div > div')).css("padding-left", "13px").on("click", function(){
		var span = $(this);
		return frappe.call({
			method: "frappe.core.page.calendar.calendar.get_all_calendars",
			type: "GET"
		}).then(r => {
			var custom_calendars = $(".checkbox.custom");
			if (custom_calendars.length == 0) {
				var doctype;
				for(doctype in r["message"]){
					if ($.inArray(r["message"][doctype], frappe.boot.calendars) == -1) {
						var li = $(`<li class="checkbox custom" style="padding-top: 0px">`);
						$('<input type="checkbox" class="cal more" value="' + r["message"][doctype] + '">').appendTo(li).on("click", function(){
							cal.fullCalendar("refetchEvents");
						});
						$('<label>').html(r["message"][doctype]).appendTo(li);
						li.appendTo(sidebar);
					}
					if($(".cal").length > 5){
						$('.all').parent().show();
					}
				}
				span.html("Less Calendars<span class='dropup'><span class='caret'></span></span>");
			} else {
				custom_calendars.remove();
				span.html("More Calendars<span class='caret '></span>");
				cal.fullCalendar("refetchEvents");
				if($('.cal').length < 5){
					$('.all').parent().hide();
				}
			}
		});
	});
}

function create_popover(event, jsEvent) {
	$(".popover.fade.bottom.in").remove();

	var htmlContent = "<div>" +
	"<h4>"+event.title+"</h4>" +
	get_time_Html(event)+
	get_description_html(event)+
	"</div>";

	get_popover_attr(jsEvent.target);

	$(jsEvent.target).popover({
		html: true,
		content: htmlContent
	});

	$(jsEvent.target).popover("show");

	set_popover_css(jsEvent);
	popover_edit_button(event);

}

function get_description_html(event){
	return "<div class='text-muted text-meduim'>"+
	event.description +
	"</div>";
}

function get_time_Html(event) {
	var timeHtml;
	if (event.allDay) {
		timeHtml = "All Day";
	} else if (event.start.isSame(event.end, 'date', 'month', 'year')) {
		timeHtml = event.start.format('LT') + " to " + event.end.format('LT');
	} else if (event.start.isSame(event.end, 'month', 'year')) {
		timeHtml = event.start.format("DD-MM-YYYY") + " to " + event.end.format('DD-MM-YYYY');
	} else {
		timeHtml = event.start.format('DD-MM-YYYY') + " to " + event.end.format('DD-MM-YYYY');
	}

	var timing = "<h6 class=''>" +
			timeHtml +
			"</h6>";
	return timing;
}

function get_popover_attr(e) {
	$(e).attr({
		"data-toggle": "popover",
		"data-placement": "bottom",
		"title": event.id,
		"data-container": "body",
		"data-animation": true,
		"data-trigger": "focus",
		"z-index": 2000
	});
}

function set_popover_css(e) {
	$(".popover.fade.bottom.in").css({
		"min-width": "100px",
		"padding": "15px",
		"z-index": 2,
		'left': e.pageX - $(".popover.fade.bottom.in").width() / 2 + 'px',
		'top': e.pageY + 'px'
	});

}

function popover_edit_button(event) {
	//Edit buuton and its action
	$("<div><span ><button class='btn btn-default btn-xs' style='margin-top:15px'>Edit</button></span></div>").on("click", function(){
		$(".popover.fade.bottom.in").remove();
		frappe.set_route("Form", event.doctype, event.id);
	}).appendTo($(".popover-content"));
}

function hide_show_weekends(calendar_option, page, $cal) {
	var btnTitle = (calendar_option.weekends) ? __('Hide Weekends') : __('Show Weekends');
	var btn = $(`<button class="btn btn-default btn-xs btn-weekend">${btnTitle}</button>`).on("click", function(){
		calendar_option.weekends = !calendar_option.weekends;
		var btnTitle = (calendar_option.weekends) ? __('Hide Weekends') : __('Show Weekends');
		$(".btn-weekend").html(btnTitle);
		localStorage.removeItem('cal_weekends');
		localStorage.setItem('cal_weekends', calendar_option.weekends);
		$cal.fullCalendar('option', 'weekends', calendar_option.weekends);
	});

	this.footnote_area = frappe.utils.set_footnote(this.footnote_area, page.body,
		__("Select or drag across time slots to create a new event."));
	this.footnote_area.css({
		"border-top": "0px"
	});
	this.footnote_area.append(btn);
}

function get_calendar_options() {
	var calendar_option ={
		header: {
			left: 'title',
			right: 'prev,today,next,agendaDay,agendaWeek,month'
		},
		weekends: true,
		selectable: true,
		editable: true,
		forceEventDuration: true,
		lazyFetching: true,
		nowIndicator: true,

		events: function(start, end, timezone, callback){
			var docinfo = get_checked_calendars();
			prepare_event(docinfo, get_system_datetime(start), get_system_datetime(end), callback);
		},

		select: function(startDate, endDate){
			var interval = endDate - startDate;
			if (interval > 86400000) {
				create_event(startDate, endDate);
			}
		},

		eventClick: function(event, jsEvent){
			create_popover(event, jsEvent);
		},
		eventDrop: function(event, delta, revertFunc){
			update_event(event, revertFunc);
		},
		eventResize: function(event, revertFunc){
			update_event(event, revertFunc);
		},
		viewRender: function(){
			$(".popover.fade.bottom.in").remove();
		},
		eventAfterAllRender: function(){
			$(".fc-scroller").removeAttr("style");
		}
	};
	return calendar_option;
}

function prepare_event(doctype_list, start, end, callback) {
	return frappe.call({
		method: "frappe.core.page.calendar.calendar.get_master_calendar_events",
		type: "GET",
		args: {
			doctype_list,
			start,
			end
		}
	}).then(r => {
		var events = [];
		var event;
		for(event in r["message"]){
			var heading;
			if (get_checked_calendars().length == 1){
				heading = r["message"][event].title;
			} else{
				heading = r["message"][event].doctype + ": " + r["message"][event].title;
			}
			//after fetching pushing and maping events on calendar
			if ($("input[value='" + r["message"][event].doctype + "']").prop("checked")){
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
		callback(events);
	});
}

function update_calendar(side,wrapper,route) {
	Object.values(side.find("ul > li > input:checked")).map((f)=>{
		if (f.value){
			side.find("ul > li > input[value = '"+f.value+"']").prop("checked",false);
		}
	});
	var cal = wrapper.page.body.find(".cal-div");
	if (route[1]){
		side.find("ul > li > input[value = '"+route[1]+"']").prop("checked",true);
		cal.fullCalendar("refetchEvents");
	}else{
		side.find("ul > li >input[value = 'Event']").prop("checked",true);
		cal.fullCalendar("refetchEvents");
	}

}

function create_calendar(wrapper) {
	frappe.pages.calendar.loaded = true;
	this.$nav = wrapper.page.sidebar.html(`<div class="module-sidebar-nav overlay-sidebar nav nav-pills nav-stacked">
			<ul></ul>
			<div></div>
			</div>
		`);
	this.$sidebar_list = wrapper.page.sidebar.find('div > ul').css('padding', 0);
	this.$cal = $("<div class='cal-div'>").appendTo(wrapper.page.body);


	select_all(this.$sidebar_list,this.$cal);
	create_checkboxes(this.$sidebar_list, this.$cal);
	get_more_calendars(this.$sidebar_list, this.$cal, wrapper.page);
	const calendar_option = get_calendar_options(this);

	this.$cal.fullCalendar(calendar_option);

	set_css(this.$cal);
	hide_show_weekends(calendar_option, wrapper.page);

}