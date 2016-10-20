# Using OAuth

Once the client and provider settings are entered, following steps can be used to start using OAuth 2.0

### Authorization Code Endpoint

#### Authorization Request

URL:
```
0.0.0.0:8000/api/method/frappe.integration_broker.oauth2.authorize
```
Params:
```
client_id = <client ID of registered app>
scope = <access scope, e.g. scope=project will allow you to access project doctypes.>
response_type = "code"
redirect_uri = <redirect uri from OAuth Client>
```

#### Confirmation Dialog

<img class="screenshot" src="assets/frappe/img/oauth_confirmation_page.png">

Click 'Allow' to receive authorization code in redirect uri.

```
http://localhost:3000/oauth_code?code=plkj2mqDLwaLJAgDBAkyR1W8Co08Ud
```
If user clicks 'Deny' receive error
```
http://localhost:3000/oauth_code?code=plkj2mqDLwaLJAgDBAkyR1W8Co08Ud
```

### Token Endpoints

#### Get Access Token

URL:
```
0.0.0.0:8000/api/method/frappe.integration_broker.oauth2.get_token
```
Params:
```
grant_type = "authorization_code"
code = <code received in redirect uri after confirmation>
redirect_uri= <valid redirect uri>
client_id = <client ID of app from OAuth Client>
```
Response:
```
{
	"access_token": "pNO2DpTMHTcFHYUXwzs74k6idQBmnI",
	"token_type": "Bearer",
	"expires_in": 3600,
	"refresh_token": "cp74cxbbDgaxFuUZ8Usc7egYlhKbH1",
	"scope": "project"
}
```

#### Refresh Access Token

URL:
```
0.0.0.0:8000/api/method/frappe.integration_broker.oauth2.get_token
```
Params:
```
grant_type = "refresh_token"
refresh_token = <refresh token from the response of get_token call with grant_type=authorization_code>
redirect_uri= <valid redirect uri>
client_id = <client ID of app from OAuth Client>
```
Response:
```
{
	"access_token": "Ywz1iNk0b21iAmjWAYnFWT4CuudHD5",
	"token_type": "Bearer",
	"expires_in": 3600,
	"refresh_token": "PNux3Q8Citr3s9rl2zEsKuU1l8bSN5",
	"scope": "project"
}
```
#### Revoke Token Endpoint

URL:
```
0.0.0.0:8000/api/method/frappe.integration_broker.oauth2.revoke_token
```
Params:
```
client_id = <client ID of app from OAuth Client>    
token = <access token to be revoked>
```
Response:
```
{"status": 200}
```

### Accessing Resource

Add parameter `access_token=<valid_bearer_token>` to Frappe's REST API endpoints to access user's resource
  
e.g.
```
frappe-server/api/method/dotted.path.to.function?param1=aaa&param2=bbb&access_token=valid_access_token 
frappe-server/api/resource/DocType/DocName?fields=["name","description"]&access_token=valid_access_token
```
