/* Test date, time and datetime formats.
 * 
 * Date formats to test: yyyy-mm-dd, dd-mm-yyyy, dd/mm/yyyy, dd.mm.yyyy,
 *   mm/dd/yyyy, mm-dd-yyyy.
 * Time formats to test: HH:mm:ss, HH:mm
 */

const std_date_format = 'dd-mm-yyyy';
const std_time_format = 'HH:mm:ss';
const test_date1 = '06-02-1966';
const test_date2 = '27-12-1987';

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

Cypress.Commands.add('frappe_desk_visit', (hash) => {
	let ver = Math.random().toString(36).substr(2,7);
	cy.visit(`/desk?ver=${ver}#${hash}`);
	//cy.reload();
	cy.get('body', {timeout: 30000})
		.should('have.attr', 'data-ajax-state', 'complete');
	cy.get('.page-container:visible').should('exist');
});

Cypress.Commands.add('delayed_type', {prevSubject: 'element'}, (subject, text) => {
	// Wait for datepicker to open as it wipes out text entered
	// prior to the datepicker finishing loading
	cy.wait(250);
	cy.wrap(subject).type(text);
});

function test_date_format(date_format_key) {
	cy.log('Test date format ' + date_format_key);
	let test_dates = date_formats[date_format_key];
	let date_format = test_dates[0];

	// Set the administrator's birthday (should be in the standard format).
	cy.log("beforeEach: Set the Administrator's birthday");
	cy.frappe_desk_visit('Form/User/Administrator');
	cy.open_section('MORE INFORMATION');
	cy.get_field('birth_date').focus().clear().blur()
		.should('have.value', '');
	cy.get_field('birth_date').click().delayed_type(test_dates[1]).blur()
		.should('have.value', test_dates[1]);
	cy.click_save_button();
	cy.open_section('MORE INFORMATION');
	cy.get_field('birth_date').should('have.value', test_dates[1]);

	// Change the current date format to the date format being tested
	cy.log('Set the date format to the test format');
	cy.frappe_desk_visit('Form/System Settings');
	cy.open_section('DATE AND NUMBER FORMAT');
	cy.fill_field('date_format', date_format, 'Select')
		.should('have.value', date_format);
	cy.click_save_button();
	cy.open_section('DATE AND NUMBER FORMAT');
	cy.get_field('date_format').should('have.value', date_format);

	// Test that the date, set in standard format in 'beforeEach',
	// now looks right in the local format.
	cy.log("Check and set the Administrator's birthday");
	cy.frappe_desk_visit('Form/User/Administrator');
	cy.open_section('MORE INFORMATION');
	cy.get_field('birth_date')
		.should('have.value', test_dates[2]);
	cy.wait(250); // Wait for datepicker to change the field and double-check
	cy.get_field('birth_date')
		.should('have.value', test_dates[2]);
	// Now clear the date and set a new date in the tested format.
	cy.get_field('birth_date').focus().clear().blur()
		.should('have.value', '');
	cy.get_field('birth_date').click().delayed_type(test_dates[3]).blur()
		.should('have.value', test_dates[3]);
	cy.click_save_button();
	cy.open_section('MORE INFORMATION');
	cy.get_field('birth_date').should('have.value', test_dates[3]);

	// Set the date format to the standard date format
	cy.log('Set the date format to the standard format');
	cy.frappe_desk_visit('Form/System Settings');
	cy.open_section('DATE AND NUMBER FORMAT');
	cy.fill_field('date_format', std_date_format, 'Select')
		.should('have.value', std_date_format);;
	cy.click_save_button();
	cy.open_section('DATE AND NUMBER FORMAT');
	cy.get_field('date_format').should('have.value', std_date_format);

	// Test that the date, set earlier in the test format, now looks
	// right in the standard format.
	cy.log("Check the Administrator's birthday");
	cy.frappe_desk_visit('Form/User/Administrator');
	cy.open_section('MORE INFORMATION');
	cy.get_field('birth_date')
		.should('have.value', test_dates[4]);
	cy.wait(250); // Wait for datepicker to change the field and double-check
	cy.get_field('birth_date')
		.should('have.value', test_dates[4]);
}

function test_time_format(time_format_key) {
	cy.log('Test time format ' + time_format_key);
	let test_times = time_formats[time_format_key];
	let time_format = test_times[0];

	// Set the Website Chat From time (should be in standard format).
	cy.log('Set the Website Settings Chat From time');
	cy.frappe_desk_visit('Form/Website Settings');
	cy.get_field('chat_enable_from').focus().clear().blur()
		.should('have.value', '');
	cy.get_field('chat_enable_from').click().delayed_type(test_times[1]).blur()
		.should('have.value', test_times[1]);
	cy.click_save_button();
	cy.get_field('chat_enable_from').should('have.value', test_times[1]);

	// Change the current time format to the time format being tested
	cy.log('Set the time format to the test format');
	cy.frappe_desk_visit('Form/System Settings');
	cy.open_section('DATE AND NUMBER FORMAT');
	cy.fill_field('time_format', time_format, 'Select')
		.should('have.value', time_format);
	cy.click_save_button();
	cy.open_section('DATE AND NUMBER FORMAT');
	cy.get_field('time_format').should('have.value', time_format);

	// Test that the time, set in standard format in 'beforeEach',
	// now looks right in the local format.
	cy.log('Check and set the Website Settings Chat From time');
	cy.frappe_desk_visit('Form/Website Settings');
	cy.get_field('chat_enable_from')
		.should('have.value', test_times[2]);
	cy.wait(250); // Wait for datepicker to change the field and double-check
	cy.get_field('chat_enable_from')
		.should('have.value', test_times[2]);
	// Now clear the date and set a new date in the tested format.
	cy.get_field('chat_enable_from').focus().clear().blur()
		.should('have.value', '');
	cy.get_field('chat_enable_from').click().delayed_type(test_times[3]).blur()
		.should('have.value', test_times[3]);
	cy.click_save_button();
	cy.get_field('chat_enable_from').should('have.value', test_times[3]);

	// Set the time format to the standard time format
	cy.log('Set the time format to the standard format');
	cy.frappe_desk_visit('Form/System Settings');
	cy.open_section('DATE AND NUMBER FORMAT');
	cy.fill_field('time_format', std_time_format, 'Select')
		.should('have.value', std_time_format);
	cy.click_save_button();
	cy.open_section('DATE AND NUMBER FORMAT');
	cy.get_field('time_format').should('have.value', std_time_format);

	// Test that the time, set earlier in the test format, now looks
	// right in the standard format.
	cy.log('Check the Website Settings Chat From time');
	cy.frappe_desk_visit('Form/Website Settings');
	cy.get_field('chat_enable_from')
		.should('have.value', test_times[4]);
	cy.wait(250); // Wait for datepicker to change the field and double-check
	cy.get_field('chat_enable_from')
		.should('have.value', test_times[4]);
}

function test_datetime_format(date_format_key, time_format_key) {
	cy.log('Test datetime format ' + date_format_key + ' plus ' + time_format_key);
	let test_dates = date_formats[date_format_key];
	let test_times = time_formats[time_format_key];
	let test_datetimes = [
		test_dates[0] + ' ' + test_times[0],
		test_dates[1] + ' ' + test_times[1],
		test_dates[2] + ' ' + test_times[2],
		test_dates[3] + ' ' + test_times[3],
		test_dates[4] + ' ' + test_times[4]
	];
	let date_format = test_dates[0];
	let time_format = test_times[0];

	// Set the Web Page test-ui-datetime-webpage Start Date(time) (should be in standard format).
	cy.log('Check and set the Web Page test-ui-datetime-webpage Start Date(time)');
	cy.frappe_desk_visit('Form/Web Page/test-ui-datetime-webpage');
	cy.get_field('start_date').focus().clear().blur()
		.should('have.value', '');
	cy.get_field('start_date').click().delayed_type(test_datetimes[1]).blur()
		.should('have.value', test_datetimes[1]);
	cy.click_save_button();
	cy.get_field('start_date').should('have.value', test_datetimes[1]);

	// Change the current date and time format to the datetime format being tested
	cy.log('Set the date and time format to the test formats');
	cy.frappe_desk_visit('Form/System Settings');
	cy.open_section('DATE AND NUMBER FORMAT');
	cy.fill_field('date_format', date_format, 'Select')
		.should('have.value', date_format);
	cy.fill_field('time_format', time_format, 'Select')
		.should('have.value', time_format);
	cy.click_save_button();
	cy.open_section('DATE AND NUMBER FORMAT');
	cy.get_field('date_format').should('have.value', date_format);
	cy.get_field('time_format').should('have.value', time_format);

	// Test that the time, set in standard format in 'beforeEach',
	// now looks right in the local format.
	cy.log('Check and set the Web Page test-ui-datetime-webpage Start Date(time)');
	cy.frappe_desk_visit('Form/Web Page/test-ui-datetime-webpage');
	cy.get_field('start_date')
		.should('have.value', test_datetimes[2]);
	cy.wait(250); // Wait for datepicker to change the field and double-check
	cy.get_field('start_date')
		.should('have.value', test_datetimes[2]);
	// Now clear the date and set a new date in the tested format.
	cy.get_field('start_date').focus().clear().blur()
		.should('have.value', '');
	cy.get_field('start_date').click().delayed_type(test_datetimes[3]).blur()
		.should('have.value', test_datetimes[3]);
	cy.click_save_button();
	cy.get_field('start_date').should('have.value', test_datetimes[3]);

	// Set the date and time formats to the standard formats
	cy.log('Set the date and time format to the standard formats');
	cy.frappe_desk_visit('Form/System Settings');
	cy.open_section('DATE AND NUMBER FORMAT');
	cy.fill_field('date_format', std_date_format, 'Select')
		.should('have.value', std_date_format);
	cy.fill_field('time_format', std_time_format, 'Select')
		.should('have.value', std_time_format);
	cy.click_save_button();
	cy.open_section('DATE AND NUMBER FORMAT');
	cy.get_field('date_format').should('have.value', std_date_format);
	cy.get_field('time_format').should('have.value', std_time_format);

	// Test that the datetime, set earlier in the test format, now looks
	// right in the standard format.
	cy.log('Check the Web Page test-ui-datetime-webpage Start Date(time)');
	cy.frappe_desk_visit('Form/Web Page/test-ui-datetime-webpage');
	cy.get_field('start_date')
		.should('have.value', test_datetimes[4]);
	cy.wait(250); // Wait for datepicker to change the field and double-check
	cy.get_field('start_date')
		.should('have.value', test_datetimes[4]);
}

context('Date tests', () => {
	before(() => {
		cy.login('Administrator', 'qwe');
        });

	beforeEach(() => {
		cy.reload();

		// Set the date format to the standard date format
		cy.log('Set the date format to the standard format');
		cy.frappe_desk_visit('Form/System Settings');
		cy.open_section('DATE AND NUMBER FORMAT');
		cy.fill_field('date_format', std_date_format, 'Select')
			.should('have.value', std_date_format);
		cy.click_save_button();
		cy.open_section('DATE AND NUMBER FORMAT');
		cy.get_field('date_format').should('have.value', std_date_format);
	});

	Object.keys(date_formats).forEach((date_format_key) => {
		// Loop over each date format and test.
		it('tests date format ' + date_format_key, function() {
			test_date_format(date_format_key);
                });
	});

});

context('Time tests', () => {
	before(() => {
		cy.login('Administrator', 'qwe');
        });

	beforeEach(() => {
		cy.reload();

		// Set the time format to the standard time format
		cy.log('Set the time format to the standard format');
		cy.frappe_desk_visit('Form/System Settings');
		cy.open_section('DATE AND NUMBER FORMAT');
		cy.fill_field('time_format', std_time_format, 'Select')
			.should('have.value', std_time_format);
		cy.click_save_button();
		cy.open_section('DATE AND NUMBER FORMAT');
		cy.get_field('time_format').should('have.value', std_time_format);
	});

	Object.keys(time_formats).forEach((time_format_key) => {
		it('tests time format ' + time_format_key, function() {
			test_time_format(time_format_key);
		});
	});

});

context('Datetime tests', () => {
	before(() => {
		cy.login('Administrator', 'qwe');

		cy.log('Deleting the test Web Page, if it exists');
		cy.request({
			method: 'delete',
			url: '/api/resource/Web Page/test-ui-datetime-webpage',
			failOnStatusCode: false
		}).then((response) => {
			cy.expect(response.status).be.oneOf([202,404]);
		});
		cy.log('Creating a new test Web Page');
		cy.request({
			method: 'post',
			url: '/api/resource/Web Page',
			body: {title: "test-ui-datetime-webpage"},
			failOnStatusCode: true
		});

	});

	beforeEach(() => {
		cy.reload();

		// Set the date and time format to the standard formats
		cy.log('Set the date and time format to known values');
		cy.frappe_desk_visit('Form/System Settings');
		cy.open_section('DATE AND NUMBER FORMAT');
		cy.fill_field('date_format', std_date_format, 'Select')
			.should('have.value', std_date_format);
		cy.fill_field('time_format', std_time_format, 'Select')
			.should('have.value', std_time_format);
		cy.click_save_button();
		cy.open_section('DATE AND NUMBER FORMAT');
		cy.get_field('date_format').should('have.value', std_date_format);
		cy.get_field('time_format').should('have.value', std_time_format);
	});

	datetime_formats.forEach((datetime_format) => {
		it('tests datetime format ' + datetime_format[0] + ' plus ' + datetime_format[1], function() {
			test_datetime_format(datetime_format[0], datetime_format[1]);
		});
	});

});
