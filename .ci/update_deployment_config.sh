#!/bin/bash

# Deployment Config Update Script for GitLab CI
# =============================================
# This script handles deployment configuration updates

set -e

echo "Starting deployment-config repo update..."

# Validate required environment variables
if [ -z "$CI_PROJECT_NAMESPACE" ] || [ -z "$CI_PROJECT_NAME" ] || [ -z "$CI_INTEGRATION_ENV" ]; then
    echo "Error: Required environment variables are missing"
    echo "CI_PROJECT_NAMESPACE: $CI_PROJECT_NAMESPACE"
    echo "CI_PROJECT_NAME: $CI_PROJECT_NAME"
    echo "CI_INTEGRATION_ENV: $CI_INTEGRATION_ENV"
    exit 1
fi

if ! rm -rf deployment-config; then
    echo "Error: Failed to remove existing deployment-config directory"
    exit 1
fi

# Clone deployment config
if ! git clone $GITLAB_CI_REPO_URL; then
    echo "Error: Failed to clone deployment-config repository"
    exit 1
fi

# Extract relative path from namespace (simplified)
remainder="${CI_PROJECT_NAMESPACE#ise/ccppday0/domains/}"
if [ "$remainder" = "$CI_PROJECT_NAMESPACE" ]; then
    remainder="${CI_PROJECT_NAMESPACE#ise/ccppday0/}"
fi

if [ -z "$remainder" ]; then
    echo "Error: Failed to parse namespace from $CI_PROJECT_NAMESPACE"
    exit 1
fi

DEPLOYMENT_CONFIG_STG_PROJECT_PATH="deployment-config/$CI_INTEGRATION_ENV/apps/$remainder/$CI_PROJECT_NAME"

# Create project structure in this deployment-config env on-demand
if [ ! -d "${DEPLOYMENT_CONFIG_STG_PROJECT_PATH}" ]; then
  if ! mkdir -p $DEPLOYMENT_CONFIG_STG_PROJECT_PATH; then
      echo "Error: Failed to create deployment config directory"
      exit 1
  fi
  microservice_latest_version=$(curl -s -H "Content-Type: application/json" -H "PRIVATE-TOKEN:${CCPP_ACCESS_TOKEN}" "${GITLAB_API_MICROSERVICE_CHART}?package_name=microservice&package_type=helm&sort" | jq -r '.[].version' | sort -rV | head -n 1)
  if [ $? -ne 0 ] || [ -z "$microservice_latest_version" ]; then
      echo "Error: Failed to get latest microservice helm chart version"
      exit 1
  fi
  cat <<EOT >> chart_reference.json
  {
    "chart": {
      "name": "microservice",
      "version": "$microservice_latest_version",
      "repository": "${GITLAB_API_MICROSERVICE_CHART}/helm/dev"
    }
  }
EOT
  if ! mv chart_reference.json $DEPLOYMENT_CONFIG_STG_PROJECT_PATH/; then
      echo "Error: Failed to move chart_reference.json"
      exit 1
  fi
fi

APP_VALUES_FILE="values.yaml"
APP_VALUES_STG_FILE="values-staging.yaml"
DEPLOYMENT_VALUES_FILE="${DEPLOYMENT_CONFIG_STG_PROJECT_PATH}/values.yaml"
WORKING_COPY_VALUES_FILE="${DEPLOYMENT_CONFIG_STG_PROJECT_PATH}/values.template.yaml"

# Copy values file to working location
if [ -f "$APP_VALUES_FILE" ]; then
  if ! cp "$APP_VALUES_FILE" "$WORKING_COPY_VALUES_FILE"; then
      echo "Error: Failed to copy $APP_VALUES_FILE"
      exit 1
  fi
elif [ -f "$APP_VALUES_STG_FILE" ]; then
  if ! cp "$APP_VALUES_STG_FILE" "$WORKING_COPY_VALUES_FILE"; then
      echo "Error: Failed to copy $APP_VALUES_STG_FILE"
      exit 1
  fi
elif [ -f "$DEPLOYMENT_VALUES_FILE" ]; then
  if ! cp "$DEPLOYMENT_VALUES_FILE" "$WORKING_COPY_VALUES_FILE"; then
      echo "Error: Failed to copy $DEPLOYMENT_VALUES_FILE"
      exit 1
  fi
else
  echo "The values.yaml file was expected but not found at $APP_VALUES_FILE, $APP_VALUES_STG_FILE or $DEPLOYMENT_VALUES_FILE." >&2
  exit 1
fi

# Apply dynamically calculated image registry and tag to values.template.yaml 
registry_url=$(echo "${CI_REPOSITORY_URL}" | sed -e "s|\/\/.*gitlab|\/\/gitlab|" \
                                              -e "s|com/ise|com:5050/ise|" \
                                              -e 's/\.git$//' \
                                              -e 's/^https:\/\///')

# Update values file in place
if [[ -n "$INCREMENTED_VERSION" ]]; then
  if ! awk -v incremented_version="${INCREMENTED_VERSION}" '/image:/ { p = 1 } p && /tag:/ && !c++ { sub(/: .*/, ": " incremented_version) } 1' "$WORKING_COPY_VALUES_FILE" > temp.yaml; then
      echo "Error: Failed to update image tag in values file"
      exit 1
  fi
  if ! mv temp.yaml "$WORKING_COPY_VALUES_FILE"; then
      echo "Error: Failed to replace values file"
      exit 1
  fi
fi

# Update registry URL
if [[ -n "$registry_url" ]]; then
    if ! sed -i -e "s#\(\s*repository:\s*\).*#\1 ${registry_url}#" "$WORKING_COPY_VALUES_FILE"; then
        echo "Error: Failed to update registry URL in values file"
        exit 1
    fi
fi  

# Final move to deployment location
if ! mv "$WORKING_COPY_VALUES_FILE" "$DEPLOYMENT_VALUES_FILE"; then
    echo "Error: Failed to move final values file to deployment location"
    exit 1
fi

echo "Committing deployment configuration changes..."
if ! cd deployment-config; then
    echo "Error: Failed to change to deployment-config directory"
    exit 1
fi
if ! git config user.email "${GITLAB_USER_EMAIL}"; then
    echo "Error: Failed to set git user email"
    exit 1
fi
if ! git config user.name "${GITLAB_USER_LOGIN}"; then
    echo "Error: Failed to set git user name"
    exit 1
fi
if ! git add -A; then
    echo "Error: Failed to add files to git"
    exit 1
fi
if ! git commit -m "AUTO Commit from project CI ${CI_PROJECT_NAME}"; then
    echo "Error: Failed to commit changes"
    exit 1
fi
if ! git push $GITLAB_CI_REPO_URL; then
    echo "Error: Failed to push changes to deployment-config"
    exit 1
fi
echo "All done :)" 