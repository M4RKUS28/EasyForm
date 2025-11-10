#!/bin/bash

# EasyForm Load Balancer Setup
# This script updates the existing Piatto load balancer to also serve EasyForm

# Project configuration
PROJECT_ID="cloud-run-hackathon-475303"

echo "Setting up load balancer for EasyForm..."
echo "This will update the existing piatto-url-map to also route traffic for easyform-ai.com"

# 1. Reserve a global IPv4 address for EasyForm (optional - you might want to use the same as Piatto)
echo "Note: You can either use the same IP as Piatto or reserve a new one."
echo "To reserve a new IP, run:"
echo "gcloud compute addresses create easyform-web-ip --ip-version=IPV4 --global"
echo ""
echo "To get the IP address:"
echo "gcloud compute addresses describe easyform-web-ip --global --format='get(address)'"
echo ""

# 2. Create managed SSL certificate for easyform-ai.com
echo "Creating managed SSL certificate for easyform-ai.com..."
gcloud compute ssl-certificates create easyform-managed-cert \
  --domains=easyform-ai.com,www.easyform-ai.com

# 3. Update the URL map to include EasyForm routes
echo "Updating URL map to include EasyForm routes..."
gcloud compute url-maps import piatto-url-map \
  --source=easyform-url-map.yaml \
  --global

# 4. Update the HTTPS proxy to include the new certificate
echo "Updating HTTPS proxy to include EasyForm certificate..."
echo "Run this command manually after the certificate is provisioned:"
echo ""
echo "gcloud compute target-https-proxies update piatto-https-proxy \\"
echo "  --ssl-certificates=piatto-managed-cert,easyform-managed-cert \\"
echo "  --url-map=piatto-url-map"
echo ""

echo "Load balancer setup initiated!"
echo ""
echo "Next steps:"
echo "1. Point your DNS A records for easyform-ai.com and www.easyform-ai.com to the load balancer IP"
echo "2. Wait for the SSL certificate to be provisioned (check with: gcloud compute ssl-certificates describe easyform-managed-cert)"
echo "3. Once certificate is ACTIVE, run the command above to update the HTTPS proxy"
echo "4. Test the setup:"
echo "   curl -I https://easyform-ai.com/"
echo "   curl -I https://easyform-ai.com/api/health"
