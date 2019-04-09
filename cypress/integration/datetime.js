/* Test date, time and datetime formats.
* 
* Date formats to test: yyyy-mm-dd, dd-mm-yyyy, dd/mm/yyyy, dd.mm.yyyy,
*   mm/dd/yyyy, mm-dd-yyyy.
* Time formats to test: HH:mm:ss, HH:mm
*/

var csrf_token = '';

const ui_test_doctype = `{"image_view":0,"allow_import":0,"creation":"2019-03-15 06:29:07.215072","track_changes":1,"modified":"2019-03-15 06:33:52.572221","sort_order":"ASC","owner":"Administrator","editable_grid":1,"in_create":0,"read_only":0,"document_type":"","hide_heading":0,"modified_by":"Administrator","track_views":0,"allow_rename":0,"custom":0,"max_attachments":0,"docstatus":0,"is_submittable":0,"sort_field":"modified","allow_copy":0,"engine":"InnoDB","allow_guest_to_view":0,"istable":0,"allow_events_in_timeline":0,"has_web_view":0,"show_name_in_global_search":0,"beta":0,"read_only_onload":0,"module":"Custom","doctype":"DocType","issingle":1,"name":"UI Test","idx":0,"hide_toolbar":0,"track_seen":0,"name_case":"","fields":[{"collapsible":0,"no_copy":0,"creation":"2019-03-15 06:29:07.215072","translatable":0,"reqd":0,"in_list_view":0,"in_standard_filter":0,"owner":"Administrator","ignore_xss_filter":0,"in_global_search":0,"read_only":0,"print_hide":0,"modified_by":"Administrator","fetch_if_empty":0,"ignore_user_permissions":0,"length":0,"label":"Date","print_hide_if_no_value":0,"allow_bulk_edit":0,"set_only_once":0,"docstatus":0,"hidden":0,"in_filter":0,"permlevel":0,"columns":0,"bold":0,"parent":"UI Test","search_index":0,"allow_on_submit":0,"precision":"","remember_last_selected_value":0,"doctype":"DocField","unique":0,"name":"d04eded683","idx":1,"allow_in_quick_entry":0,"modified":"2019-03-15 06:50:50.538464","parenttype":"DocType","fieldname":"date","fieldtype":"Date","report_hide":0,"parentfield":"fields"},{"collapsible":0,"no_copy":0,"creation":"2019-03-15 06:29:07.215072","translatable":0,"reqd":0,"in_list_view":0,"in_standard_filter":0,"owner":"Administrator","ignore_xss_filter":0,"in_global_search":0,"read_only":0,"print_hide":0,"modified_by":"Administrator","fetch_if_empty":0,"ignore_user_permissions":0,"length":0,"label":"Time","print_hide_if_no_value":0,"allow_bulk_edit":0,"set_only_once":0,"docstatus":0,"hidden":0,"in_filter":0,"permlevel":0,"columns":0,"bold":0,"parent":"UI Test","search_index":0,"allow_on_submit":0,"precision":"","remember_last_selected_value":0,"doctype":"DocField","unique":0,"name":"72dae03915","idx":2,"allow_in_quick_entry":0,"modified":"2019-03-15 06:50:50.538464","parenttype":"DocType","fieldname":"time","fieldtype":"Time","report_hide":0,"parentfield":"fields"},{"collapsible":0,"no_copy":0,"creation":"2019-03-15 06:29:07.215072","translatable":0,"reqd":0,"in_list_view":0,"in_standard_filter":0,"owner":"Administrator","ignore_xss_filter":0,"in_global_search":0,"read_only":0,"print_hide":0,"modified_by":"Administrator","fetch_if_empty":0,"ignore_user_permissions":0,"length":0,"label":"Datetime","print_hide_if_no_value":0,"allow_bulk_edit":0,"set_only_once":0,"docstatus":0,"hidden":0,"in_filter":0,"permlevel":0,"columns":0,"bold":0,"parent":"UI Test","search_index":0,"allow_on_submit":0,"precision":"","remember_last_selected_value":0,"doctype":"DocField","unique":0,"name":"a5e6ba2d2e","idx":3,"allow_in_quick_entry":0,"modified":"2019-03-15 06:50:50.538464","parenttype":"DocType","fieldname":"datetime","fieldtype":"Datetime","report_hide":0,"parentfield":"fields"}],"permissions":[{"creation":"2019-03-15 06:29:07.215072","share":1,"doctype":"DocPerm","owner":"Administrator","export":0,"cancel":0,"set_user_permissions":0,"modified_by":"Administrator","create":1,"submit":0,"write":1,"role":"System Manager","print":1,"docstatus":0,"permlevel":0,"parent":"UI Test","read":1,"import":0,"report":0,"name":"83b10b4cfe","idx":1,"amend":0,"modified":"2019-03-15 06:50:50.538464","email":1,"parenttype":"DocType","parentfield":"permissions","if_owner":0,"delete":1}],"quick_entry":1}`;

const std_date_format = 'yyyy-mm-dd';
const std_time_format = 'HH:mm:ss';
const test_date1 = '1966-02-06';
const test_date2 = '1987-12-27';

// Formats: local fmt of test_date1, local data to enter, std format of that
const date_formats = {
	'yyyy-mm-dd': ['yyyy-mm-dd', test_date1, '1966-02-06', '1987-12-27', test_date2],
	'dd-mm-yyyy': ['dd-mm-yyyy', test_date1, '06-02-1966', '27-12-1987', test_date2],
	'dd/mm/yyyy': ['dd/mm/yyyy', test_date1, '06/02/1966', '27/12/1987', test_date2],
	'dd.mm.yyyy': ['dd.mm.yyyy', test_date1, '06.02.1966', '27.12.1987', test_date2],
	'mm/dd/yyyy': ['mm/dd/yyyy', test_date1, '02/06/1966', '12/27/1987', test_date2],
	'mm-dd-yyyy': ['mm-dd-yyyy', test_date1, '02-06-1966', '12-27-1987', test_date2]
};
// Formats: local fmt of test_time1, local data to enter, std format of that
const time_formats = {
	'HH:mm:ss': ['HH:mm:ss', '01:23:45', '01:23:45', '23:59:58', '23:59:58'],
	'HH:mm:ss zeros': ['HH:mm:ss', '00:00:00', '00:00:00', '01:00:00', '01:00:00'],
	'HH:mm': ['HH:mm', '01:23:45', '01:23', '23:59', '23:59:00'],
	'HH:mm zeros': ['HH:mm', '00:00:00', '00:00', '01:00', '01:00:00']
};

let datetime_formats = [];
Object.keys(date_formats).forEach((date_format) => {
	Object.keys(time_formats).forEach((time_format) => {
		datetime_formats.push([date_format, time_format]);
	});
});

Cypress.Commands.add('get_csrf_token', () => {
// Obtain the CSRF token
	cy.request({
		method: 'GET',
		url: '/',
	}).then((response) => {
		let rx = /frappe.csrf_token = "(.*)"/;
		let arr = rx.exec(response.body);
		csrf_token = arr[1];
	});
});

Cypress.Commands.add('install_ui_test', () => {
// Add the UI Test single doctype to the database. Should either succeed
// with HTTP 200 or fail (already exists) with HTTP 409.
	cy.request({
		method: 'POST',
		url: '/api/resource/DocType',
		body: ui_test_doctype,
		headers: {
			'X-Frappe-CSRF-Token': csrf_token
		},
		failOnStatusCode: false
	}).then((response) => {
		cy.expect(response.status).be.oneOf([200, 409]);
	});
});

Cypress.Commands.add('update_datetime_formats', (date_format, time_format) => {
// Update the Date Format and Time Format in System Settings
	cy.request({
		method: 'PUT',
		url: '/api/resource/System Settings/System Settings',
		body: {
			date_format: date_format,
			time_format: time_format
		},
		headers: {
			'X-Frappe-CSRF-Token': csrf_token
		},
		failOnStatusCode: false
	}).then((response) => {
		cy.expect(response.status).to.eq(200);
	});
});

Cypress.Commands.add('update_test_data', (date, time, datetime) => {
// Update the date, time and datetime entries on UI Test
	cy.request({
		method: 'PUT',
		url: '/api/resource/UI%20Test/UI%20Test',
		body: {
			date: date,
			time: time,
			datetime: datetime
		},
		headers: {
			'X-Frappe-CSRF-Token': csrf_token
		},
		failOnStatusCode: false
	}).then((response) => {
		cy.expect(response.status).to.eq(200);
	});
});

Cypress.Commands.add('check_test_data', (date, time, datetime) => {
// Check the date, time and datetime entries on UI Test
	cy.request({
		method: 'GET',
		url: '/api/resource/UI Test/UI Test',
		failOnStatusCode: true
	}).then((response) => {
		cy.expect(response.body.data).to.have.property('time', time);
		cy.expect(response.body.data).to.have.property('date', date);
		cy.expect(response.body.data).to.have.property('datetime', datetime);
	});
});

Cypress.Commands.add('click_save_button', () => {
	cy.wait(50);
	cy.get('body', {timeout: 30000})
		.should('have.attr', 'data-ajax-state', 'complete');
	cy.contains('button.primary-action > span', 'Save')
		.parent().click();
	cy.wait(50);
	cy.get('body', {timeout: 30000})
		.should('have.attr', 'data-ajax-state', 'complete');
});

Cypress.Commands.add('get_field', (fieldname, fieldtype='Data') => {
	let selector = `.form-control[data-fieldname="${fieldname}"]`;

	if (fieldtype === 'Text Editor') {
		selector = `[data-fieldname="${fieldname}"] .ql-editor`;
	}

	return cy.get('.page-container:visible ' + selector);
});

Cypress.Commands.add('delayed_type', {prevSubject: 'element'}, (subject, text) => {
	// Wait for datepicker to open as it wipes out text entered
	// prior to the datepicker finishing loading
	cy.wrap(subject).click();
	cy.wait(500);  // Sometimes fails at 250ms. No DOM element to watch here,
	// and can look correct and then be overwritten by the datepicker, so
	// this long wait is extremely difficult to avoid.
	cy.wrap(subject).type('{selectall}{backspace}' + text).blur().should('have.value', text);
});

context('Datetime tests', () => {
	before(() => {
		cy.login('Administrator', 'qwe');
		cy.get_csrf_token();
		cy.install_ui_test();
		cy.visit('/desk#Form/UI Test/UI Test');
		cy.get('body', {timeout: 30000})
			.should('have.attr', 'data-ajax-state', 'complete');
		cy.update_datetime_formats(std_date_format, std_time_format);
		cy.update_test_data('', '', '');
	});

	beforeEach(() => {
		// Set the date format to the standard date format
		cy.log('Set the date and time formats to the standard format');
		cy.update_datetime_formats(std_date_format, std_time_format);
	});

	datetime_formats.forEach((datetime_format) => {
		it('tests datetime format ' + datetime_format[0] + ' plus ' + datetime_format[1], function() {
			let date_test_data = date_formats[datetime_format[0]];
			let time_test_data = time_formats[datetime_format[1]];
			cy.log('updating data via request');
			cy.update_test_data(
				date_test_data[1],
				time_test_data[1],
				date_test_data[1] + ' ' + time_test_data[1]
			);
			cy.log('updating date & time formats via request');
			cy.update_datetime_formats(date_test_data[0], time_test_data[0]);
			cy.reload();
			cy.get('body', {timeout: 30000})
				.should('have.attr', 'data-ajax-state', 'complete');

			// Test that values are now in the test format
			cy.get_field('date')
				.should('have.value', date_test_data[2]);
			cy.get_field('time')
				.should('have.value', time_test_data[2]);
			cy.get_field('datetime')
				.should('have.value', date_test_data[2] + ' ' + time_test_data[2]);

			// Set values to second test data
			cy.get_field('date').delayed_type(date_test_data[3]);
			cy.get_field('time').delayed_type(time_test_data[3]);
			cy.get_field('datetime').delayed_type(date_test_data[3] + ' ' + time_test_data[3]);
			cy.click_save_button();

			// Check that database values are set correctly
			cy.check_test_data(
				date_test_data[4],
				time_test_data[4],
				date_test_data[4] + ' ' + time_test_data[4]
			);
		});
	});

});
