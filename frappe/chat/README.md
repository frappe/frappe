### Frappé Chat

### Table of Contents
* [Developer Guide](#developer-guide)
	* [Client-Side Scripting](#client-side-scripting)

#### Developer Guide

##### Client-Side Scripting

###### `/api/method/frappe.chat.doctype.chat_profile.chat_profile.create`
* Creates a `Chat Profile` for the current logged in user.
```js
frappe.chat.create_chat_profile(null, (profile) => {
	// do something with "profile".
})
```
The first argument is a list `fields` you require to retrieve after the said `Chat Profile` has been created (defaults to `null` which retrieves you all fields).
For instance, let's retrieve the `status` of the user.
```js
frappe.chat.create_chat_profile("status", (profile) => {
	// do something with "profile".
})
```
Or a list of 'em.
```js
frappe.chat.create_chat_profile(["status", "chat_background"], (profile) => {
	// do something with "profile".
})
```

### TODO

#### Minor
- [ ] Add capital as prop to `frappe.components.Avatar`