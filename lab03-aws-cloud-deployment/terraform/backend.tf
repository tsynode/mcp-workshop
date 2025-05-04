terraform {
  backend "s3" {
    # These values will be set by the GitHub Actions workflow
    # bucket = "mcp-workshop-terraform-state"
    # key    = "lab03/terraform.tfstate"
    # region = "us-west-2"
  }
}
