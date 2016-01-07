# REST API

Frappe ships with an HTTP API. There are two parts of this API.

1. Remote Procedure Calls (RPC)
2. REST

## 1. RPC

A request to an endpoint `/api/method/{dotted.path.to.function}` will call
a whitelisted python function. A function can be whitelisted using the
`frappe.whitelist` decorator.

For example, Add the following to sample\_app/\_\_init\_\_.py

	@frappe.whitelist(allow_guest=True)
	def ping():
		return 'pong'

<span class="label label-success">GET</span> http://frappe.local:8000**/api/method/sample_app.ping**

_Response:_

	{
	  "message": "pong"
	}


## 2. REST

All documents in Frappe are available via a RESTful API with prefix
`/api/resource/`.

### Login

To login, you will have to send a POST request to the login method.

<span class="label label-info">POST</span> http://frappe.local:8000**/api/method/login**

	usr=Administrator&pwd=admin

_Response:_

	{
	   "full_name": "Administrator",
	   "message": "Logged In"
	}


Try to make an authenticated request

<span class="label label-success">GET</span> http://frappe.local:8000**/api/method/frappe.auth.get\_logged\_user**

_Response:_

	{
	   "message": "Administrator"
	}


### Listing Documents

To list documents, the URL endpoint is `/api/resource/{doctype}` and the
expected HTTP verb is GET.

Response is returned as JSON Object and the listing is an array in with the key `data`.

<span class="label label-success">GET</span> http://frappe.local:8000**/api/resource/Person**

_Response:_

	{
	   "data": [
		  {
			 "name": "000000012"
		  },
		  {
			 "name": "000000008"
		  }
	   ]
	}


#### Fields

By default, only name field is included in the listing, to add more fields, you
can pass the fields param to GET request. The param has to be a JSON array.

<span class="label label-success">GET</span> http://frappe.local:8000**/api/resource/Person/?fields=["name", "first\_name"]**

_Response:_

	{
	   "data": [
		  {
			 "first_name": "Jane",
			 "name": "000000012"
		  },
		  {
			 "first_name": "John",
			 "name": "000000008"
		  }
	   ]
	}


#### Filters

You can filter the listing using sql conditions by passing them as the `filters`
GET param. Each condition is an array of the format, [{doctype}, {field},
{operator}, {operand}].

Eg, to filter persons with name Jane, pass a param `filters=[["Person", "first_name", "=", "Jane"]]`

<span class="label label-success">GET</span> http://frappe.local:8000**/api/resource/Person/**

_Response:_
	{
	   "data": [
		  {
			 "name": "000000012"
		  }
	   ]
	}


#### Pagination

All listings are returned paginated by 20 items. To change the page size, you
can pass `limit_page_length`. To request succesive pages, pass `limit_start` as
per your `limit_page_length`.

For Example, to request second page, pass `limit_start` as 20.

<span class="label label-success">GET</span> http://frappe.local:8000**/api/resource/DocType**

_Response:_

	{
	   "data": [
		  {
			 "name": "testdoc"
		  },
		  {
			 "name": "Person"
		  },

		  ......

		  {
			 "name": "Website Template"
		  }
	   ]
	}


<span class="label label-success">GET</span> http://frappe.local:8000**/api/resource/DocType?limit_start=20**

_Response:_

	{
	   "data": [
		  {
			 "name": "Website Route"
		  },
		  {
			 "name": "Version"
		  },
		  {
			 "name": "Blog Post"
		  },

		  ......

		  {
			 "name": "Custom Field"
		  }
	   ]
	}


### CRUD

#### Create

You can create a document by sending a `POST` request to the url, `/api/resource/{doctype}`.

<span class="label label-info">POST</span> http://frappe.local:8000**/api/resource/Person**

_Body_:

	data={"first_name": "Robert"}

_Response:_

	{
	  "data": {
		"first_name": "Robert",
		"last_name": null,
		"modified_by": "Administrator",
		"name": "000000051",
		"parent": null,
		"creation": "2014-05-04 17:22:38.037685",
		"modified": "2014-05-04 17:22:38.037685",
		"doctype": "Person",
		"idx": null,
		"parenttype": null,
		"owner": "Administrator",
		"docstatus": 0,
		"parentfield": null
	  }
	}

#### Read

You can get a document by its name using the url, `/api/resource/{doctype}/{name}`

For Example,

<span class="label label-success">GET</span> http://frappe.local:8000**/api/resource/Person/000000012**

_Response:_

	{
	  "data": {
		"first_name": "Jane",
		"last_name": "Doe",
		"modified_by": "Administrator",
		"name": "000000012",
		"parent": null,
		"creation": "2014-04-25 17:56:51.105372",
		"modified": "2014-04-25 17:56:51.105372",
		"doctype": "Person",
		"idx": null,
		"parenttype": null,
		"owner": "Administrator",
		"docstatus": 0,
		"parentfield": null
	  }
	}

### Update

You can create a document by sending a `PUT` request to the url,
`/api/resource/{doctype}`. This acts like a `PATCH` HTTP request in which you do
not have to send the whole document but only the parts you want to change.

For Example,

<span class="label label-primary">PUT</span> http://frappe.local:8000**/api/resource/Person/000000008**

_Body:_

	data={"last_name": "Watson"}

_Response:_

	{
	  "data": {
		"first_name": "John ",
		"last_name": "Watson",
		"modified_by": "Administrator",
		"name": "000000008",
		"creation": "2014-04-25 17:26:22.728327",
		"modified": "2014-05-04 18:21:45.385995",
		"doctype": "Person",
		"owner": "Administrator",
		"docstatus": 0
	  }
	}

### Delete

You can delete a document by its name by sending a `DELETE` request to the url,
`/api/resource/{doctype}/{name}`.

For Example,

<span class="label label-danger">DELETE</span> http://frappe.local:8000**/api/resource/Person/000000008**

_Response:_

	{"message":"ok"}
