# Ayuna DoStore

File and object store library for Ayuna-Pykit

## Data Source Authentication Strategies

Various data-sources such as Azure Blob, AWS S3 provide different ways to authenticate the user / identity and resolve the permissions. Accordingly, the following types of authentication are supported in Ayuna-io.

## Azure Blob Storage

The following are the supported ways to connect to an Azure blob storage container.

### Connection-String

This method provides access to the entire container and its blobs. This method does not check for individual RBAC for the user. This may be fine if the intention is to share all the container content to the user. On the other hand, this gives the user the complete ownership to do any of the CRUD operations which might be a risk unless the distribution of the connection-string is strictly controlled.

**What is needed to configure the store?**

* Azure storage container's `connection string` -> This essentially contains all the required information to connect to the container and access the blobs.

### Service Principal

For large enterprises, it is common to use the `Service Principal` to provide access to their users. Here, the enterpise IT team would register an Azure Entra-ID application and provide it's client-id, client-secret and the tenant-id to which it belongs to along with the URL of the Azure blob container. This is much secured compared to a connection-string since, it is scoped to an identity and not a master key. Further, the IT team can revoke the container access to the app, without having to change the storage account keys. It also provides audit logs for the app for observability.

**What is needed to configure the store?**

* Azure Entra-ID app's `client-id` -> Available as `application-id` in the Azure portal
* Azure Entra-ID app's `client-secret` -> The secured secret associated for the app
* The `tenant-id` to which the app belongs to
* The Azure `storage-account-url` to connect to -> E.g., *`https://<storage-account>.blob.core.windows.net`*

## AWS S3 Storage

### Using Long-term Keys

This is a more traditional approach where the user will use the access-key and access-secret generated for an IAM user with appropriate permissions to access the S3 bucket and use them to connect to the bucket and access its objects. These credentials are typically the long-term credentials without a temporary session-token. Moreover, the user configuring these credentials need not be the same IAM user in the AWS account. Hence, this poses higher risk of running CRUD operations on the target S3 bucket. So, strict control needs to be adapted while providing these credentials to the users.

**What is needed to configure the store?**

* The long-term `access-key` for the IAM user having required access to the target S3 bucket
* The corresponding, long-term `access-secret`
* The `bucket-name` to connect to
* The `region` constraint for the bucket

### Workload Identity Federation via OIDC

This is a standard, enterprise approach to authorize an Azure app to request access to the AWS S3 bucket / storage. To enable this, you and your customer perform a one-time handshake. You provide your Azure details, and they provide their AWS details.

**You must give the customer two pieces of information from your Azure Portal:**

* **Azure Tenant ID:** Your company's unique Azure Directory ID.
* **Azure App Client ID:** The ID of the Managed Identity (or App Registration) running your portal.

**The customer’s IT admin performs two steps:**

* **Create an OIDC Identity Provider:** They "tell" AWS to trust tokens coming from your specific Azure Tenant (`https://sts.windows.net/<Your-Tenant-ID>/`).
* **Create an IAM Role:** They create a role with a trust policy that says: "`Allow the Azure App with Client ID XYZ to assume this role.`"

**What is needed to configure the store?**

* The `role-arn` of the IAM role created by the customer (*e.g., arn:aws:iam::123456789012:role/MySaaSReaderRole*)
* The `bucket-name` to connect to
* The `region` constraint for the bucket

### Different AWS Account (The `Cross-Account Role`)

This is the standard for SaaS providers. It solves the "Confused Deputy" problem, a security risk where one customer might try to trick your app into accessing another customer's data.

* You (SaaS Provider) provide the customer with your AWS Account ID and a unique External ID (a random UUID you generate for that specific customer).
* Customer creates an IAM Role in their account.
* Trust Policy only allows your Account ID to assume it.
* Condition requires the ExternalId you provided.
* Permission Policy grants access to their S3 bucket.

**What is needed to configure the store?**

* The `role-arn` of the IAM role created by the customer (*e.g., arn:aws:iam::123456789012:role/MySaaSReaderRole*)
* The `bucket-name` to connect to
* The `region` constraint for the bucket

## GCP Storage

### Service Account Key (JSON)

The customer must generate the key and provide it to your portal.

* Create Service Account: Navigate to IAM & Admin > Service Accounts.
* Grant Permissions: Assign the Storage Object Viewer role for the specific bucket.
* Generate Key:
  * Click on the Service Account name.
  * Go to the Keys tab.
  * Click Add Key > Create new key.
  * Select JSON and click Create.
* Handover: The file (*e.g., credentials.json*) will download. They must upload this to your portal or store it in your backend's secure storage

**What is needed to configure the store?**

* The `credential configuration file`, a secret json file

### Workload Identity Federation

You give the customer the identity of your portal’s backend.

* If you are in Azure: Provide your Tenant ID and Managed Identity Client ID.
* If you are in AWS: Provide your AWS Account ID and IAM Role ARN.
* If you are in GCP: Provide your Service Account Email.

The customer creates a Workload Identity Pool and a Provider that trusts your specific cloud identity.

* They create a GCP Service Account (*e.g., `extractor-sa@customer-project.iam.gserviceaccount.com`*).
* They grant that Service Account the Storage Object Viewer role on their bucket.
* They create a "Trust Relationship" allowing your AWS/Azure identity to impersonate that Service Account.

**What is needed to configure the store?**

* The `credential configuration file`, a non-secret json file that describes how to bridge the two clouds

### Direct IAM Binding

If you are both on GCP, you don't even need a config file. The customer simply adds your Service Account email to their IAM policy.

What the customer does:

* Go to Cloud Storage > Buckets > Permissions.
* Click Grant Access.
  * Principal: `your-portal-sa@your-project.iam.gserviceaccount.com`.
  * Role: Storage Object Viewer.
