QUnit.module('views');

QUnit.only("Check if all desk icons are visible", function(assert) {
	assert.expect(1);
	let done = assert.async();
	let random = frappe.utils.get_random(10);
	let iconLength;
	let deskIconLength;

	frappe.run_serially([
		() => frappe.set_route('modules_setup'),

		() => {
			iconLength = $('#page-modules_setup > div.container.page-body > div.page-wrapper > div > div.row.layout-main > div > div.layout-main-section > div.padding.modules-setup-icons').children('div').length
			for (var i=1; i<=iconLength; i++){
				if (!($('#page-modules_setup > div.container.page-body > div.page-wrapper > div > div.row.layout-main > div > div.layout-main-section > div.padding.modules-setup-icons > div:nth-child('+i+') > div > label > input').is(':checked'))){
					$('#page-modules_setup > div.container.page-body > div.page-wrapper > div > div.row.layout-main > div > div.layout-main-section > div.padding.modules-setup-icons > div:nth-child('+i+') > div > label > input').click()
				}
			}
		},

		() => {$('div#page-modules_setup button.btn.btn-primary.btn-sm.primary-action').click()},

		() => frappe.set_route(),

		() => {
			// todo Refresh coupled with code doesn't work
			// $('span.avatar.avatar-small > div').click()
			// $('ul#toolbar-user li:nth-child(3) > a').click()
			// setTimeout(frappe.timeout(4),2000);
			// window.setTimeout(frappe.timeout(4), 4000);
			// console.log('howdy')
		},

		() => {
			deskIconLength = $('#icon-grid').children('div').length
		},


		() => {
			assert.ok(iconLength+2 == deskIconLength);
			return done();
		},

		// () => {return done();}

	]);
});


// Inject Reload
// $('#page-Form\\2f Test\\20 Runner > div.page-head > div > div > div.text-right.col-md-5.col-sm-4.col-xs-6.page-actions > span.page-icon-group.hidden-xs.hidden-sm').before('<button class="btn btn-sm"><a href="#" onclick="return frappe.ui.toolbar.clear_cache();">Reload</a></button>')


QUnit.test("Desktop icon link verification", function(assert) {
	assert.expect(8);
	let done = assert.async();
	let random = frappe.utils.get_random(10);
	let deskIconLength;
	let routes = [["modules", "Desk"],
					["List", "File"],
					["modules", "Website"],
					["modules", "Integrations"],
					["List", "Communication", "Inbox"],
					["modules", "Contacts"],
					["modules", "Setup"],
					["modules", "Core"]
					];


	frappe.run_serially([
		() => frappe.set_route(),

		() => {
			deskIconLength = $('#icon-grid').children('div').length
		},

		() => {
			for (var i=1; i<=deskIconLength-1; i++){
				$('#icon-grid > div:nth-child('+i+') > div.app-icon').click()
				assert.deepEqual(routes[i-1], frappe.get_route())
				frappe.set_route()
			}
		},

		

		() => {
			return done();
		},

		// () => {return done();}

	]);
});