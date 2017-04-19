import { Selector } from 'testcafe';

fixture `Login Page`
    .page `http://selenium.erpnext.com/`;

test('Check login', async t => {
    const loginEmail = Selector('#login_email');
    const my_settings = Selector('li > a').withText('My Settings');
    const my_email = Selector('[data-fieldname="email"] .control-value');

    await t
        .typeText(loginEmail, 'jane_do@mailtothis.com')
        .typeText('#login_password', 'selenium')
        .click('.btn-login')
        .click('.dropdown-navbar-user')
        .click(my_settings)
        .expect(my_email.innerText).eql('jane_do@mailtothis.com')
});