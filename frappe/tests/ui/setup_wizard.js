var login = require("./login.js")['Login'];

module.exports = {
	before: browser => {
		browser
			.url(browser.launch_url + '/login')
			.waitForElementVisible('body', 5000);
	},
	'Login': login,
	'Welcome': browser => {
		let slide_selector = '[data-slide-name="welcome"]';
		browser
			.assert.title('Frappe Desk')
			.pause(5000)
			.assert.visible(slide_selector, 'Check if welcome slide is visible')
			.assert.value('select[data-fieldname="language"]', 'English')
			.click(slide_selector + ' .next-btn');
	},
	'Region': browser => {
		let slide_selector = '[data-slide-name="region"]';
		browser
			.waitForElementVisible(slide_selector , 2000)
			.pause(6000)
			.setValue('select[data-fieldname="language"]', "India")
			.pause(4000)
			.assert.containsText('div[data-fieldname="timezone"]', 'India Time - Asia/Kolkata')
			.click(slide_selector + ' .next-btn');
	},
	'User': browser => {
		let slide_selector = '[data-slide-name="user"]';
		browser
			.waitForElementVisible(slide_selector, 2000)
			.pause(3000)
			.setValue('input[data-fieldname="full_name"]', "John Doe")
			.setValue('input[data-fieldname="email"]', "john@example.com")
			.setValue('input[data-fieldname="password"]', "vbjwearghu")
			.click(slide_selector + ' .next-btn');
	},

	after: browser => {
		browser.end();
	},
};