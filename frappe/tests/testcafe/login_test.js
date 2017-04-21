import { Selector } from 'testcafe';

fixture `Login Page`
    .page `http://localhost:8000/login`;

test('Check login', async t => {
    const wizardHeading  = Selector("p.lead")

    await t
        .typeText('#login_email', 'Administrator')
        .typeText('#login_password', 'admin')
        .click('.btn-login')
	.expect(wizardHeading.innerText).eql("Welcome");
});
