
fixture `Example page`
    .page `http:localhost:8000/login`;
    
test('Successful Login', async t => {
    await t
        .typeText('#login_email', 'Administrator')
        .click('#login_password', 'admin')
        .click('.btn-login')
        .click('[data-link="modules"]');
});
