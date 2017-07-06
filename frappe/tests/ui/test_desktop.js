QUnit.module('views');

QUnit.test("Desktop icon link verification", function(assert) {
	assert.expect(1);
	let done = assert.async();

	frappe.run_serially([
		() => frappe.set_route(),
		() => {

			//total icon on desktop
			var deskIconLength = $('#icon-grid').children('div').length;
			//random number between 1 to total no. of icon
			var random = Math.floor(Math.random() * (deskIconLength) + 1);
			//title of icon clicked
			var iconname = document.querySelector(".case-wrapper:nth-child("+random+") > div > span").innerHTML;
			$('#icon-grid > div:nth-child('+random+') > div.app-icon').click();
			var route = frappe.get_route();
			//find icon name in route
			assert.deepEqual(route[1], iconname);
		},
		() => done()
	]);
});

QUnit.test("test navbar notifications", function(assert) {
	assert.expect(2);
	let done = assert.async();
	let elementcontent;
	function elementchoose(x){
		return ('ul#dropdown-notification li:nth-child('+x+') > a');
	};

	frappe.run_serially([
		() => frappe.set_route(),
		() => {
			//add new todo if notifications are zero
			if (document.querySelector('.navbar-new-comments-true').innerHTML == 0)
				frappe.tests.setup_doctype('ToDo');
		},
		() => $('.navbar-new-comments-true').click(),
		() => {
			var count = $('#dropdown-notification').children('li').length;
			//choose random element from notification list
			var i = Math.floor(Math.random() * (count) + 1);
			if (document.querySelector(elementchoose(1)).innerText.replace(/[^a-z]/gi, '')=='ToDo' && i==2)
				i+=1;
			//get content of that element
			elementcontent = document.querySelector(elementchoose(i)).innerText;
			$(elementchoose(i)).click();
		},
		() => frappe.timeout(1),
		() => {
			//check route
			assert.deepEqual(elementcontent.replace(/[^a-z]/gi, ''), frappe.get_route()[1].replace(/[^a-z]/gi, ''));
			//check number of elements
			assert.ok(cur_list.data.length == elementcontent.replace(/[^0-9]/gi, ''));
		},
		() => done()
	]);
});
