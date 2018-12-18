frappe.pages['calendar'].on_page_load = function (wrapper){
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Calendar',
		single_column: false

	});

	frappe.require([
		'assets/frappe/js/lib/fullcalendar/fullcalendar.min.css',
		'assets/frappe/js/lib/fullcalendar/fullcalendar.min.js',
		'assets/frappe/js/lib/fullcalendar/locale-all.js'
	], function(){
		const me = this;
		this.$cal = page.body.find('div');

		const calendar_option = get_calendar_options(me);

		//showing calendar 
		this.$cal.fullCalendar(calendar_option);

		hide_show_weekends(calendar_option, page);
	});
}

frappe.pages['calendar'].on_page_show = (wrapper) => {
	this.$nav = wrapper.page.sidebar.html(`
			<ul class="module-sidebar-nav overlay-sidebar nav nav-pills nav-stacked"></ul>
			<div></div>
		`);

	this.$sidebar_list = wrapper.page.sidebar.find('ul');
	this.$cal = $("<div>").appendTo(wrapper.page.body);

	select_all(this.$sidebar_list, this.$cal);

	create_checkboxes(this.$sidebar_list, this.$cal);

	get_more_calendars(this.$sidebar_list, this.$cal, wrapper.page);
}

$('body').on('click', function (e){
	//popover hiddingon putside click.
	if ($(e.target).data('toggle') !== 'popover' &&
		$(e.target).parents('.popover.in').length === 0) {
		$('[data-toggle="popover"]').popover('hide');
	}
});

function get_system_datetime(date){
	date._offset = moment.user_utc_offset;
	return frappe.datetime.convert_to_system_tz(date);
}

function update_event(event, revertFunc){
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
		if (r["message"] == 0){
			frappe.msgprint("Unable to update the Event");
			revertFunc();
		}
	});
}

function create_event(start, end){
	//create event
	frappe.call({
		method: "frappe.core.page.calendar.calendar.get_field_map",
		type: "GET"
	}).then(r => {
		var x = r["message"];
		if ($('.cal:checked').length == 1){
			var event = frappe.model.get_new_doc($('.cal:checked')[0].value);
			event[x[$('.cal:checked')[0].value]["field_map"]["start"]] = get_system_datetime(start);
			event[x[$('.cal:checked')[0].value]["field_map"]["end"]] = get_system_datetime(end);
			frappe.set_route("Form", $('.cal:checked')[0].value, event.name);
		} else if ($('.cal:checked').length > 1){
			options = '';
			$('.cal:checked').each(function (){
				options += '\n' + $(this).attr('value');
			});

			//select doctype to create event
			frappe.prompt([{
				'fieldname': 'Doctype',
				'fieldtype': 'Select',
				'options': options,
				'label': 'Type',
				'reqd': 1
			}],
			function (values){
				var event = frappe.model.get_new_doc(values.Doctype);
				event[x[values.Doctype]["field_map"]["start"]] = get_system_datetime(start);
				event[x[values.Doctype]["field_map"]["end"]] = get_system_datetime(end);
				frappe.set_route("Form", values.Doctype, event.name);

			},
			'Select Document type',
			'Submit'
			);
		} else {
			frappe.msgprint("Select document type to create calendar event");
		}
	});
}

function set_css(cal){
	// flatify buttons
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
	$('<input type="checkbox">').appendTo(head_li).on("click", function(){
		if ($(this).prop("checked")){
			$('.checkbox > input').each(function (){
				$(this).prop("checked", true);
			});
			cal.fullCalendar("refetchEvents");
		} else {
			$('.checkbox > input').each(function (){
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
	});
}

function get_more_calendars(sidebar, cal, page){
	//dropdown for more calendars
	$("<span class='text-muted cursor-pointer'>" +
	"More Calendars<span class='caret'></span>" +
	"</span>").appendTo(page.sidebar.find('div')).on("click", function(){
	var span = $(this);
	return frappe.call({
		method: "frappe.core.page.calendar.calendar.get_all_calendars",
		type: "GET"
	}).then(r => {
		if ($(".checkbox.custom").length == 0) {
			for (doctype in r["message"]) {
				if ($.inArray(r["message"][doctype], frappe.boot.calendars) == -1) {
					$(`<li class="checkbox custom" style="padding-top: 0px">`);
					$('<input type="checkbox" class="cal" value="' + r["message"][doctype] + '">').appendTo(li).on("click", function() {
						cal.fullCalendar("refetchEvents");
					})
					$('<label>').html(r["message"][doctype]).appendTo(li);
					li.appendTo(sidebar);
				}
			}
			span.html("Less Calendars<span class='dropup'><span class='caret'></span></span>");
		} else {
			$(".checkbox.custom").remove();
			span.html("More Calendars<span class='caret '></span>");
			cal.fullCalendar("refetchEvents");
		}
	})
	});
}

function get_time_Html(event) {
	// creating time html
	if (event.allDay) {
		var timeHtml = "All Day";
	} else if (event.start.isSame(event.end, 'date', 'month', 'year')) {
		var timeHtml = event.start.format('LT') + " to " + event.end.format('LT');
	} else if (event.start.isSame(event.end, 'month', 'year')) {
		var timeHtml = event.start.format("MMMM, ") + event.start.format('D') + " to " + event.end.format('D');
	} else {
		var timeHtml = event.start.format('Do MMMM') + " to " + event.end.format('Do MMMM');
	}

	timing = "<div class='mt-5'>" +
		"<div class='text-muted col-sm-2' style='padding-right: 0; margin-top: 6px;'>" +
		"<i class='fa fa-clock-o' aria-hidden='true'></i>" +
		"</div> " +
		"<div class='col-sm-9' style='padding-left: 0; margin-top: 5px;'>" +
		timeHtml +
		"</div>" +
		"</div>";

	return timing;
}

function create_popover(event, jsEvent) {
	$(".popover.fade.bottom.in").remove();

	var descr = event.description;
	description = "<div class='mt-5'>" +
		"<div class='text-muted col-sm-2' style='padding-right: 0; margin-top: 6px; '>" +
		"<i class='fa fa-align-left' aria-hidden='true'></i>" +
		"</div> " +
		"<div class='col-sm-10' style='padding-left: 0; margin-top: 5px;'>" +
		descr +
		"</div>" +
		"</div>";

	//popover content
	var htmlContent = "<div class='row'>" +
		description +
		"</div>" +
		"<div class='row'>" +
		get_time_Html(event) +
		"</div>";


	$(jsEvent.target).attr("data-toggle", "popover");
	$(jsEvent.target).attr("data-placement", "bottom");
	$(jsEvent.target).attr("title", event.title);
	$(jsEvent.target).attr("data-container", "body");
	$(jsEvent.target).attr("data-trigger", "focus");
	$(jsEvent.target).attr("z-index", 2000);
	$(jsEvent.target).popover({
		html: true,
		content: htmlContent
	});
	$(jsEvent.target).popover("show");
	$(".popover.fade.bottom.in").css("min-width", "200px");
	$(".popover.fade.bottom.in").css("z-index", 2);


	$('.popover.fade.bottom.in').css('left', jsEvent.pageX - $(".popover.fade.bottom.in").width() / 2 + 'px');
	$('.popover.fade.bottom.in').css('top', jsEvent.pageY + 'px');

	//Edit buuton and its action
	$("<span ><button class='btn btn-default btn-sm btn-modal-close' style='margin-top:15px'>Edit</button></span>").on("click", function(){
		$(".popover.fade.bottom.in").remove();
		frappe.set_route("Form", event.doctype, event.id);
	}).appendTo($(".popover-content"));

}

function hide_show_weekends(calendar_option, page) {
	// button for hiding and showing the weekends days
	var btnTitle = (calendar_option.weekends) ? __('Hide Weekends') : __('Show Weekends');
	var btn = $(`<button class="btn btn-default btn-xs btn-weekend">${btnTitle}</button>`).on("click", function(){
		calendar_option.weekends = !calendar_option.weekends;
		var btnTitle = (calendar_option.weekends) ? __('Hide Weekends') : __('Show Weekends');
		$(".btn-weekend").html(btnTitle);
		localStorage.removeItem('cal_weekends');
		localStorage.setItem('cal_weekends', calendar_option.weekends);
		$cal.fullCalendar('option', 'weekends', calendar_option.weekends);

	});
	//creating footnote
	this.footnote_area = frappe.utils.set_footnote(this.footnote_area, page.body,
		__("Select or drag across time slots to create a new event."));
	this.footnote_area.css({
		"border-top": "0px"
	});
	this.footnote_area.append(btn);
}

function get_calendar_options(me){
	var calendar_option ={
		// header region which contains monlty, weekly and daily views 
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
		events: function (start, end, timezone, callback){
			var docinfo = [];
			$('.cal:checked').each(function (){
				docinfo.push($(this).attr('value'));
			});
			prepare_event(docinfo, get_system_datetime(start), get_system_datetime(end), callback);
		},
		//Drag event (to create new Event)modal fade in
		select: function (startDate, endDate, jsEvent, view){
			var interval = endDate - startDate;
			if (interval > 86400000){
				create_event(startDate, endDate);
			}
		},
		//Event click action 
		eventClick: function (event, jsEvent){
			//removing popover if present
			create_popover(event, jsEvent);
		},
		eventDrop: function (event, delta, revertFunc, jsEvent, ui, view){
			update_event(event, revertFunc);
		},
		eventResize: function (event, delta, revertFunc){
			update_event(event, revertFunc);
		},
		viewRender: function (view, element){
			$(".popover.fade.bottom.in").remove();
		},
		eventAfterAllRender: function (view, b, c){
			$(".fc-scroller").removeAttr("style");
			set_css(me.$cal);
		}
	}
	return calendar_option;
}

function prepare_event(docinfo, start_param, end_param, callback){
	return frappe.call({
		method: "frappe.core.page.calendar.calendar.get_master_calendar_events",
		type: "GET",
		args:{
			'doctypeinfo': docinfo,
			'start': start_param,
			'end': end_param
		}
	}).then(r => {
		var events = [];
		for (event in r["message"]){
			if ($('.cal:checked').length == 1){
				var heading = r["message"][event].title;
			} else{
				var heading = r["message"][event].doctype + ": " + r["message"][event].title;
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