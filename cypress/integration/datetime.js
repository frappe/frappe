import datetime_doctype from '../fixtures/datetime_doctype';
const doctype_name = datetime_doctype.name;

context('Control Date, Time and DateTime', () => {
	before(() => {
		cy.login();
		cy.visit('/app/website');
		return cy.insert_doc('DocType', datetime_doctype, true);
	});

	describe('Date formats', () => {
		let date_formats = [
			{
				date_format: 'dd-mm-yyyy',
				part: 2,
				length: 4,
				separator: '-'
			},
			{
				date_format: 'mm/dd/yyyy',
				part: 0,
				length: 2,
				separator: '/'
			}
		];

		date_formats.forEach(d => {
			it('test date format ' + d.date_format, () => {
				cy.set_value('System Settings', 'System Settings', {
					date_format: d.date_format
				});
				cy.window()
					.its('frappe')
					.then(frappe => {
						// update sys_defaults value to avoid a reload
						frappe.sys_defaults.date_format = d.date_format;
					});

				cy.new_form(doctype_name);
				cy.get('.form-control[data-fieldname=date]').focus();
				cy.get('.datepickers-container .datepicker.active')
					.should('be.visible');
				cy.get(
					'.datepickers-container .datepicker.active .datepicker--cell-day.-current-'
				).click({ force: true });

				cy.window()
					.its('cur_frm')
					.then(cur_frm => {
						let formatted_value = cur_frm.get_field('date').input.value;
						let parts = formatted_value.split(d.separator);
						expect(parts[d.part].length).to.equal(d.length);
					});
			});
		});
	});

	describe('Time formats', () => {
		let time_formats = [
			{
				time_format: 'HH:mm:ss',
				value: '  11:00:12',
				match_value: '11:00:12'
			},
			{
				time_format: 'HH:mm',
				value: '  11:00:12',
				match_value: '11:00'
			}
		];

		time_formats.forEach(d => {
			it('test time format ' + d.time_format, () => {
				cy.set_value('System Settings', 'System Settings', {
					time_format: d.time_format
				});
				cy.window()
					.its('frappe')
					.then(frappe => {
						frappe.sys_defaults.time_format = d.time_format;
					});
				cy.new_form(doctype_name);
				cy.fill_field('time', d.value, 'Time').blur();
				cy.get_field('time').should('have.value', d.match_value);
			});
		});
	});

	describe('DateTime formats', () => {
		let datetime_formats = [
			{
				date_format: 'dd.mm.yyyy',
				time_format: 'HH:mm:ss',
				value: '   02.12.2019 11:00:12',
				doc_value: '2019-12-02 11:00:12',
				input_value: '02.12.2019 11:00:12'
			},
			{
				date_format: 'mm-dd-yyyy',
				time_format: 'HH:mm',
				value: '   12-02-2019 11:00:00',
				doc_value: '2019-12-02 11:00:00',
				input_value: '12-02-2019 11:00'
			}
		];
		datetime_formats.forEach(d => {
			it(`test datetime format ${d.date_format} ${d.time_format}`, () => {
				cy.set_value('System Settings', 'System Settings', {
					date_format: d.date_format,
					time_format: d.time_format
				});
				cy.window()
					.its('frappe')
					.then(frappe => {
						frappe.sys_defaults.date_format = d.date_format;
						frappe.sys_defaults.time_format = d.time_format;
					});
				cy.new_form(doctype_name);
				cy.fill_field('datetime', d.value, 'Datetime').blur();
				cy.get_field('datetime').should('have.value', d.input_value);

				cy.window()
					.its('cur_frm.doc.datetime')
					.should('eq', d.doc_value);
			});
		});
	});

	describe('Date/Datetime Hotkeys', () => {
		let keys = [
			{
				key: 'y',
				keycode: 89,
				from: '2021-08-12',
				expected: '2021-01-01',
			},
			{
				key: 'r',
				keycode: 82,
				from: '2021-08-12',
				expected: '2021-12-31',
			},
			{
				key: 'm',
				keycode: 77,
				from: '2021-08-12',
				expected: '2021-08-01',
			},
			{
				key: 'h',
				keycode: 72,
				from: '2021-08-12',
				expected: '2021-08-31',
			},
			{
				key: 'w',
				keycode: 87,
				from: '2021-08-12',
				expected: '2021-08-08',
			},
			{
				key: 'k',
				keycode: 75,
				from: '2021-08-12',
				expected: '2021-08-14',
			},
			// The following are incompatible with cy..type
			// {
			// 	key: '+',
			// 	keycode: 61,
			// 	from: '2021-08-12',
			// 	expected: '2021-08-13',
			// },
			// {
			// 	key: 'numpad +',
			// 	keycode: 107,
			// 	from: '2021-08-12',
			// 	expected: '2021-08-13',
			// },
			// {
			// 	key: '-',
			// 	keycode: 173,
			// 	from: '2021-08-12',
			// 	expected: '2021-08-11',
			// },
			// {
			// 	key: 'numpad -',
			// 	keycode: 109,
			// 	from: '2021-08-12',
			// 	expected: '2021-08-11',
			// },
			//TODO 't' key
		];
		let control_types = [
			{ fieldname: 'date', controltype: 'Date' }, { fieldname: 'datetime', controltype: 'DateTime' }
		];
		control_types.forEach(type => {
			keys.forEach((config) => {
				it(`'${config.key}' ${type.controltype} Hotkey`, () => {
					cy.set_value('System Settings', 'System Settings', {
						date_format: 'yyyy-mm-dd',
						time_format: 'HH:mm'
					});
					cy.window()
						.its('frappe')
						.then(frappe => {
							frappe.sys_defaults.date_format = 'yyyy-mm-dd';
							frappe.sys_defaults.time_format = 'HH:mm';
						});

					cy.new_form(doctype_name);
					cy.fill_field(type.fieldname, config.from, type.controltype).blur();
					cy.get_field(type.fieldname).should('include.value', config.from);

					cy.get_field(type.fieldname).click({ force: true });
					cy.get_field(type.fieldname).type(config.key);

					cy.get_field(type.fieldname).should('include.value', config.expected);
				});
			});
		});

	});


});
