import { Selector } from 'testcafe';

function today(){
	var today = new Date();
	var dd = today.getDate();
	var mm = today.getMonth()+1; //January is 0!
	var yyyy = today.getFullYear();
	var today = dd+'-'+mm+'-'+yyyy;
	return today;
}

fixture `ToDo Tests`
    .page `http://localhost:8000/login`;

test('ToDo - Insert, List and Delete', async t => {
    const new_btn = Selector("button.btn-primary").withText("New")
    const priority = Selector("select[data-fieldname='priority']")
    const desc = Selector("[data-fieldname='description'] div.note-editable")
    const save_btn = Selector("button.primary-action").withText("Save")
    const mytodo = Selector("a.list-id").withText("TestCafe.")
    const menu_btn = Selector("[data-page-route='Form/ToDo'] .menu-btn-group button")
    const yes_btn = Selector("button.btn-primary", {visibilityCheck: true}).withText("Yes")
    const refresh_btn = Selector("button").withText("Refresh")
    const delete_btn = Selector("a").withText("Delete")

	await t
	.typeText('#login_email', 'jane_doe@example.com')
	.typeText('#login_password', 'password')
	.click('.btn-login')
	.navigateTo('/desk#List/ToDo')
	
	// ToDo Insert
	.click(new_btn)
	.click("a.edit-full")
	.typeText("input[data-fieldname='date']", today())
	.click(priority)
	.click("option[value='High']")
	.expect(priority.value).eql("High")
	.typeText(desc, "Finish writing ToDo tests in TestCafe.")
	.click(save_btn)
	.wait(200)

	// Check List View
	.click("a[href='#List/ToDo']")
	.expect(mytodo.visible).ok()

	//ToDo Delete
	.click(mytodo)
	.click(menu_btn)
	.click(delete_btn)
	.click(yes_btn)

	// Check ListView Again
	.click(refresh_btn)
	.expect(mytodo.exists).notOk()
});
