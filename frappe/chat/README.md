### Frappé Chat

### Table of Contents
* [Developer Guide](#developer-guide)
	* [Client-Side Scripting](#client-side-scripting)

#### Developer Guide

##### Client-Side Scripting

##### `Chat Profile` Create

Creates a `Chat Profile` for the current logged in user.

| URL | Requires Auth |
|-----|---------------|
`/api/method/frappe.chat.doctype.chat_profile.chat_profile.create` | yes
Payload
| Parameter	   | Example 	   | Required   | Default | Description
|--------------|---------------|------------|---------|------------
| `user`	   | `foo@bar.com` | Yes 		|         | The email of the session user.
| `exists_ok ` | `true`		   | No         | `false` | throws an error if `Chat Profile` already exists.
| `fields`     | `"status"`    | No         | `null`  | The fields need to be retrieved. By default, retrieves all fields.

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