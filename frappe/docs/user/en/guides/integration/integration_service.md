# Integration Service

Its a platform to configure third party services. In first release, we are introducing four services
as a built-in feature of frappe.

- PayPal
- Razorpay
- LDAP Based Authentication
- Dropbox Integration

## How to configure service?

1. If service is not pre-created then create new service by selecting service name from dropdown. To
create integration service, `Setup > Integrations > Integration Service`
<img class="screenshot" alt="IntegrationService" src="{{docs_base_url}}/assets/img/create_service.png">

1. Next step is, setup credentials for respective service,
 - To setup parameters click on `Edit Settings` button, this will open a popup with pre-defined paramters
<img class="screenshot" alt="IntegrationService" src="{{docs_base_url}}/assets/img/edit_settings.png">

 - After filling required details, click on `Set`.
<img class="screenshot" alt="IntegrationService" src="{{docs_base_url}}/assets/img/setup_params.png">
 
 - After setting up all mandatory parameters, Save document.
<img class="screenshot" alt="IntegrationService" src="{{docs_base_url}}/assets/img/save_params.png">

1. To enable service, check `Enable` and Save document, this will validate your settings and enable service.
<img class="screenshot" alt="IntegrationService" src="{{docs_base_url}}/assets/img/enable_service.png">