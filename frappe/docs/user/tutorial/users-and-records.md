# Making Users and Records

Now that we have created the models, we can directly start making records using Frappe Desk UI. You do not have to create views! Views in Frappe are automatically made based on the DocType properties.

### 4.1 Creating User

To make records, we will first create a User. To create a user, go to:

> Setup > Users > User > New

Create a new User and set the name and first name and new password.

Also give the Librarian and Library Member Roles to this user

<img class="screenshot" alt="Add User Roles" src="{{url_prefix}}/assets/img/add_user_roles.png">

Now logout and login using the new user id and password.

### 4.2 Creating Records

You will now see an icon for the Library Management module. Click on that icon and you will see the Module page:

<img class="screenshot" alt="Library Management Module" src="{{url_prefix}}/assets/img/lib_management_module.png">

Here you can see the DocTypes that we have created for the application. Let us start creating a few records.

First let us create a new Article:

<img class="screenshot" alt="New Article" src="{{url_prefix}}/assets/img/new_article_blank.png">

Here you will see that the the DocType you had created has been rendered as a form. The validations and other rules will also apply as designed. Let us fill out one Article.

<img class="screenshot" alt="New Article" src="{{url_prefix}}/assets/img/new_article.png">

You can also add an image.

<img class="screenshot" alt="Attach Image" src="{{url_prefix}}/assets/img/attach_image.gif">

Now let us create a new member:

<img class="screenshot" alt="New Library Member" src="{{url_prefix}}/assets/img/new_member.png">

After this, let us create a new membership record for the member.

Here if you remember we had set the values of Member First Name and Member Last Name to be directly fetched from the Member records and as soon as you will select the member id, the names will be updated.

<img class="screenshot" alt="New Library Membership" src="{{url_prefix}}/assets/img/new_lib_membership.png">

As you can see that the date is formatted as year-month-day which is a system format. To set / change date, time and number formats, go to

> Setup > Settings > System Settings

<img class="screenshot" alt="System Settings" src="{{url_prefix}}/assets/img/system_settings.png">

{next}
