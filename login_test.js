import { Selector } from 'testcafe';

fixture `Login Page`
    .page `http://127.0.0.1:8000/login`;

test('Check login', async t => {
    const loginEmail = Selector('#login_email');
    const my_settings = Selector('li > a').withText('My Settings');
    const my_email = Selector('[data-fieldname="email"] .control-value');

    await t
        .typeText(loginEmail, 'Administrator')
        .typeText('#login_password', 'admin')
        .click('.btn-login')
        .click('[data-link="modules"]');
});
