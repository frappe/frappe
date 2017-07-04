QUnit.module('views');

QUnit.test("Check if all desk icons are visible", function(assert) {
	assert.expect(1);
	let done = assert.async();
	let iconLength;
	let deskIconLength;

	frappe.run_serially([
		// Goto module setup page to add/ remove desktop icons
		() => frappe.set_route('modules_setup'),

		// Tick all options to make all desktop icons visible
		() => {
			iconLength = $('#page-modules_setup > div.container.page-body > div.page-wrapper > div > div.row.layout-main > div > div.layout-main-section > div.padding.modules-setup-icons').children('div').length;
			for (var i=1; i<=iconLength; i++){
				if (!($('#page-modules_setup > div.container.page-body > div.page-wrapper > div > div.row.layout-main > div > div.layout-main-section > div.padding.modules-setup-icons > div:nth-child('+i+') > div > label > input').is(':checked'))){
					$('#page-modules_setup > div.container.page-body > div.page-wrapper > div > div.row.layout-main > div > div.layout-main-section > div.padding.modules-setup-icons > div:nth-child('+i+') > div > label > input').click();
				}
			}
		},

		// Save
		() => {$('div#page-modules_setup button.btn.btn-primary.btn-sm.primary-action').click();},

		// Goto Desktop
		() => frappe.set_route(),

		// Refresh to make desktop icons visible
		// Logically this is necessary, and Travis build should fail, but it's passing for some reason!
		// (maybe because drivers (like gecko etc.) are being used by Travis and they don't need refresh)
		// Locally if run 1st time the test fails
		() => {
			// todo Refresh coupled with code doesn't work
			// frappe.ui.toolbar.clear_cache();
			// $('span.avatar.avatar-small > div').click();
			// $('ul#toolbar-user li:nth-child(3) > a').click();
			// window.setTimeout(frappe.timeout(4), 4000);
			// console.log('howdy')
		},

		// Count the no. of desktop icons
		() => {
			deskIconLength = $('#icon-grid').children('div').length;
		},

		// Check if no of ticked icons is equal to that visible on the desktop
		// +2 because Explore and Developer are on by default and they cannot be turned off in modules_setup
		() => {
			assert.ok(iconLength+2 == deskIconLength);
			return done();
		}
	]);
});


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
		// Goto Desktop
		() => frappe.set_route(),

		// Check the no. of icons present on the desk
		() => {
			deskIconLength = $('#icon-grid').children('div').length
		},

		// Click every desk icon and check if the link is correct
		() => {
			for (var i=1; i<=deskIconLength-1; i++){
				$('#icon-grid > div:nth-child('+i+') > div.app-icon').click();
				assert.deepEqual(routes[i-1], frappe.get_route());
				frappe.set_route();
			}
		},

		

		() => {
			return done();
		},

		// () => {return done();}

	]);
});


// Inject Reload for east of development 
// $('#page-Form\\2f Test\\20 Runner > div.page-head > div > div > div.text-right.col-md-5.col-sm-4.col-xs-6.page-actions > span.page-icon-group.hidden-xs.hidden-sm').before('<button class="btn btn-sm"><a href="#" onclick="return frappe.ui.toolbar.clear_cache();">Reload</a></button>')

