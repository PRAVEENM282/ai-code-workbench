#!/bin/sh
set -eu
api_base_url=${WORKBENCH_API_BASE_URL:-/api/v1}
case "$api_base_url" in
  /*) ;;
  *) exit 1 ;;
esac
case "$api_base_url" in
  *[!a-zA-Z0-9_/-]*|'') exit 1 ;;
esac
printf 'window.WORKBENCH_CONFIG = { apiBaseUrl: "%s" };\n' "$api_base_url" > /tmp/runtime-config.js
