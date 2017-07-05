QUnit.module('views');

QUnit.test("Check if all desk icons are visible", function(assert) {
	assert.expect(1);
	let done = assert.async();
	let random = frappe.utils.get_random(10);
	let iconLength;
	let deskIconLength;

	frappe.run_serially([
		() => frappe.set_route('modules_setup'),
		() => {
			iconLength = $('#page-modules_setup > div.container.page-body > div.page-wrapper > div > div.row.layout-main > div > div.layout-main-section > div.padding.modules-setup-icons').children('div').length;
			for (var i=1; i<=iconLength; i++){
				if (!($('#page-modules_setup > div.container.page-body > div.page-wrapper > div > div.row.layout-main > div > div.layout-main-section > div.padding.modules-setup-icons > div:nth-child('+i+') > div > label > input').is(':checked'))){
					$('#page-modules_setup > div.container.page-body > div.page-wrapper > div > div.row.layout-main > div > div.layout-main-section > div.padding.modules-setup-icons > div:nth-child('+i+') > div > label > input').click();
				}
			}
		},
		() => {$('div#page-modules_setup button.btn.btn-primary.btn-sm.primary-action').click();},
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
			deskIconLength = $('#icon-grid').children('div').length;
		},
		() => {
			assert.ok(iconLength+1 == deskIconLength);
			return done();
		}
		// () => {return done();}

	]);
});

QUnit.test("Desktop icon link verification", function(assert) {
	assert.expect(1);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.set_route(),
		() => {

			var deskIconLength = $('#icon-grid').children('div').length;                                 //total icon on desktop
			var i = Math.floor(Math.random() * (deskIconLength) + 1);                                    //random i between 1 to total no. of icon
			var iconname = document.querySelector(".case-wrapper:nth-child("+i+") > div > span").innerHTML;      //title of icon clicked
			$('#icon-grid > div:nth-child('+i+') > div.app-icon').click();
			frappe.timeout(1);
			var route = frappe.get_route();
			assert.deepEqual(route[1], iconname);                                                        //find icon name in route
			return done();
		}
	]);
});