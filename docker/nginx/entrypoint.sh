#!/bin/sh
set -e
if [ -n "$API_BASE_URL" ]; then
    echo "Setting API_BASE_URL to: $API_BASE_URL"
    find /usr/share/nginx/html -type f \( -name '*.js' -o -name '*.html' \) \
        -exec sed -i "s|__API_BASE_URL__|$API_BASE_URL|g" {} +
else
    echo "API_BASE_URL not set; using build-time placeholder default"
fi
