# GitHub Container Registry Setup

This document describes how to set up GitHub Container Registry for publishing Docker images.

## Overview

GitHub Container Registry allows you to publish and distribute Docker images. The CI/CD pipeline automatically publishes images when code is merged to main.

## Setting Up Container Registry

### 1. Enable Container Registry

1. Go to your GitHub repository
2. Click on "Settings" tab
3. Scroll down to "Features" section
4. Ensure "Inherit access from source repository" is enabled for packages

### 2. Configure Package Permissions

1. Go to "Settings" → "Actions" → "General"
2. Scroll down to "Workflow permissions"
3. Select "Read and write permissions"
4. Check "Allow GitHub Actions to create and approve pull requests"
5. Save the changes

## Container Registry Access

The GitHub Actions workflow uses the `GITHUB_TOKEN` secret to authenticate with GitHub Container Registry. This token is automatically provided by GitHub Actions and has the necessary permissions to push images.

## Example Workflow Configuration

The workflow automatically configures container registry access:

```yaml
- name: Log in to Container Registry
  uses: docker/login-action@v3
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}
```

## Using Published Images

Once images are published, you can pull and run them:

```bash
# Pull the latest version
docker pull ghcr.io/your-org/your-repo:latest

# Pull a specific version
docker pull ghcr.io/your-org/your-repo:v1.2.3

# Run the container
docker run -p 8080:8080 ghcr.io/your-org/your-repo:latest
```

## Best Practices

1. **Use semantic versioning**: Always use semantic version tags for releases
2. **Test images locally**: Test Docker images before publishing
3. **Monitor image security**: Regularly scan published images for vulnerabilities
4. **Document usage**: Include usage instructions in release notes
5. **Tag consistently**: Use consistent tagging strategy across releases
6. **Monitor registry usage**: Track image downloads and usage

## Troubleshooting

### Registry Access Denied

If you get "Access denied" errors:

1. Check that "Inherit access from source repository" is enabled for packages
2. Verify workflow permissions are set to "Read and write permissions"
3. Ensure the `GITHUB_TOKEN` has package write permissions

### Image Push Failed

If image push fails:

1. Check that the image name follows the correct format: `ghcr.io/owner/repo:tag`
2. Verify the workflow has the necessary permissions
3. Check Docker build logs for errors

### Tag Already Exists

If you get "Tag already exists" errors:

1. Use a different version tag
2. Delete the existing tag if it's not being used
3. Check for version conflicts in the pipeline

## References

- [GitHub Container Registry Documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [GitHub Actions Permissions](https://docs.github.com/en/actions/security-guides/automatic-token-authentication#permissions-for-the-github_token) 