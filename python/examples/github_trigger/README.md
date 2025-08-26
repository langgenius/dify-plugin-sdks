# GitHub Trigger Plugin

This plugin provides GitHub webhook triggers for Dify workflows, allowing you to automatically respond to GitHub events like code pushes, pull requests, issues, and more.

## Features

- **Push Event Trigger**: Responds to code pushes to GitHub repositories
- **Webhook Signature Verification**: Securely validates GitHub webhook requests
- **OAuth Integration**: Easy authentication with GitHub
- **Rich Event Data**: Extracts detailed information from GitHub events

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure GitHub OAuth (Optional)

If you want to use OAuth for authentication:

1. Go to your GitHub Settings > Developer settings > OAuth Apps
2. Create a new OAuth App
3. Set the Authorization callback URL to your Dify instance
4. Copy the Client ID and Client Secret

### 3. Generate GitHub Personal Access Token

1. Go to GitHub Settings > Developer settings > Personal access tokens
2. Generate a new token with appropriate repository permissions
3. Copy the token for use in the plugin configuration

### 4. Set Up Webhook

1. Go to your repository Settings > Webhooks
2. Add a new webhook with:
   - Payload URL: Your Dify plugin webhook endpoint
   - Content type: `application/json`
   - Secret: (optional but recommended for security)
   - Events: Select the events you want to trigger on (e.g., "Pushes")

## Available Triggers

### Push Trigger

Triggered when someone pushes code to a repository.

**Event Variables:**
- `repository_name`: Name of the repository
- `repository_full_name`: Full name (owner/repo)
- `repository_url`: Repository URL
- `branch`: Branch name that was pushed to
- `ref`: Git reference (e.g., refs/heads/main)
- `pusher_name`: Name of the user who pushed
- `pusher_email`: Email of the user who pushed
- `commits_count`: Number of commits in the push
- `commits`: Array of commit objects with details
- `head_commit`: Information about the head commit

**Parameters:**
- `repository_filter` (optional): Filter by repository name
- `branch_filter` (optional): Filter by branch name

## Usage in Dify

1. Install the plugin in your Dify instance
2. Configure the plugin with your GitHub credentials
3. Create a workflow and add the GitHub trigger
4. Configure the trigger parameters as needed
5. Add your workflow logic to process the GitHub event data

## Example Workflow

```yaml
# Example workflow triggered by GitHub push events
triggers:
  - type: github_trigger.push_trigger
    parameters:
      branch_filter: "main"  # Only trigger on main branch pushes

steps:
  - name: process_push
    type: code
    code: |
      # Access trigger variables
      repo_name = trigger.repository_name
      branch = trigger.branch
      commits = trigger.commits
      
      # Your processing logic here
      print(f"New push to {repo_name} on branch {branch}")
      print(f"Number of commits: {len(commits)}")
```

## Security

- Always use webhook secrets to verify request authenticity
- Store credentials securely using Dify's credential management
- Use OAuth when possible for better security
- Regularly rotate access tokens

## Troubleshooting

1. **Webhook not triggering**: Check that the webhook URL is correct and accessible
2. **Authentication errors**: Verify your GitHub token has the required permissions
3. **Signature verification fails**: Ensure the webhook secret matches your configuration
