var pageLoad = 3000
module.exports = {
	beforeEach: browser => {
		browser
			.url(browser.launch_url + '/login')
			.waitForElementVisible('body', pageLoad)
      .assert.title('Login')
			.assert.visible('#login_email', 'Check if login box is visible')
			.setValue("#login_email", "Administrator")
			.setValue("#login_password", "frappe")
			.click(".btn-login")
			.waitForElementVisible("#body_div", pageLoad)
      .assert.title('Desktop')
      .url(browser.launch_url + '/desk#List/User/List')
      .pause(pageLoad)
      .assert.title('User');
	},

  'Create User': browser =>{
    browser
      .assert.visible('button.btn.btn-primary.btn-sm.primary-action span', 'Check if New Button is visible')
      .click('button.btn.btn-primary.btn-sm.primary-action span')
      .waitForElementVisible('div.control-input input[data-fieldname="email"]', pageLoad)
      .setValue('div.control-input input[data-fieldname="email"]','test@test.com')
      .setValue('div.control-input input[data-fieldname="first_name"]','testUser')
      .click('div.modal.fade.in > div.modal-dialog > div > div.modal-header > div > div.col-xs-5 > div > button[type="button"].btn.btn-primary.btn-sm')
      .url(browser.launch_url + '/desk#List/User/List')
      .pause(pageLoad)
      .assert.visible('a[data-name="test@test.com"]', 'New User Created');
  },

  'Delete User': browser =>{
    browser
      .waitForElementVisible('body' ,pageLoad)
      .click('a[data-name="test@test.com"]')
      .pause(pageLoad)
      .assert.title('testUser - test@test.com')
      .click('[data-page-route="Form/User"] .menu-btn-group')
      .click('div#page-Form\2f User li:nth-child(13) > a')
      .pause(pageLoad)
  },

  after: browser => browser.end()
};
