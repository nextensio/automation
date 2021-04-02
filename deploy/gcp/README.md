This create a set of kubernetes cluster in GCP. Each cluster has a directory name under 
kops and its attribute specified in spec file under that directory.

Before running deploy.sh, some step needs to be performed in GCP.

1. Open a GCP account
2. Create a Service account - GCP menu -> IAM & Admin -> Service Accounts -> + CREATE SERVICE ACCOUNT
3. Add key - select Service Account created in above step and Add Key
4. Download the key and name it key.json and keep it in ~/.google

- To create a cluster - ./deploy.sh --create
- To delete a cluster - ./deploy.sh --delete

