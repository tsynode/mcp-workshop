# Setting Up GitHub Secrets for AWS Deployment

This guide will walk you through the process of setting up the necessary GitHub secrets for deploying the Lab 03 MCP servers to AWS using GitHub Actions.

## Prerequisites

Before you begin, you'll need:

1. An AWS account with appropriate permissions
2. A GitHub account with access to your forked repository
3. AWS CLI installed locally (for creating credentials)

## Step 1: Create an IAM User in AWS

First, you need to create an IAM user with programmatic access and appropriate permissions:

1. Log in to the AWS Management Console
2. Navigate to IAM (Identity and Access Management)
3. Click on "Users" in the left sidebar, then "Add user"
4. Enter a username (e.g., `github-actions-mcp-workshop`)
5. Select "Programmatic access" for Access type
6. Click "Next: Permissions"
7. Select "Attach existing policies directly"
8. For this lab, you can attach the following policies (in a production environment, you would use more restrictive policies):
   - `AmazonECR-FullAccess`
   - `AmazonECS-FullAccess`
   - `AmazonVPCFullAccess`
   - `IAMFullAccess`
   - `AmazonS3FullAccess` (for Terraform state if using S3 backend)
   - `CloudWatchLogsFullAccess`
   - `AmazonRoute53FullAccess` (if using Route53 for DNS)
9. Click "Next: Tags" (optional)
10. Click "Next: Review"
11. Click "Create user"
12. **IMPORTANT**: On the success page, copy the "Access key ID" and "Secret access key". This is the only time you'll see the secret access key.

## Step 2: Add Secrets to GitHub Repository

Now, add these credentials as secrets in your GitHub repository:

1. Go to your GitHub repository
2. Click on "Settings" tab
3. In the left sidebar, click on "Secrets and variables" then "Actions"
4. Click "New repository secret"
5. Add the following secrets:

### AWS_ACCESS_KEY_ID

1. Name: `AWS_ACCESS_KEY_ID`
2. Value: Paste the access key ID you copied from AWS
3. Click "Add secret"

### AWS_SECRET_ACCESS_KEY

1. Name: `AWS_SECRET_ACCESS_KEY`
2. Value: Paste the secret access key you copied from AWS
3. Click "Add secret"

### AWS_REGION

1. Name: `AWS_REGION`
2. Value: Your preferred AWS region (e.g., `us-west-2`)
3. Click "Add secret"

## Step 3: Verify Secrets

To verify that your secrets are properly set up:

1. Go to the "Settings" tab of your repository
2. Click on "Secrets and variables" then "Actions"
3. You should see the three secrets listed:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `AWS_REGION`

## Step 4: Optional - Add Additional Secrets

Depending on your specific needs, you might want to add additional secrets:

### ACM_CERTIFICATE_ARN (Optional)

If you have an existing ACM certificate for HTTPS:

1. Name: `ACM_CERTIFICATE_ARN`
2. Value: The ARN of your ACM certificate
3. Click "Add secret"

## Security Considerations

- **IAM Best Practices**: In a production environment, you should create a custom IAM policy with the minimum permissions required.
- **Secret Rotation**: Regularly rotate your AWS access keys.
- **Environment Isolation**: Consider using different IAM users for different environments (dev, staging, prod).

## Troubleshooting

If you encounter issues with the GitHub Actions workflow:

1. **Permission Errors**: Ensure your IAM user has all the necessary permissions.
2. **Region Mismatch**: Make sure the region in your workflow matches the region where your resources should be deployed.
3. **Secret Issues**: Verify that your secrets are correctly named and contain the proper values.

## Cleanup

When you're done with the lab, consider:

1. Disabling or deleting the IAM user
2. Removing the GitHub secrets

This helps ensure that your AWS account remains secure and prevents any accidental deployments.
