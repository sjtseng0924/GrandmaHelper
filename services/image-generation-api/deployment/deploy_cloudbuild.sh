#!/bin/bash

# Production Image Generation API Deployment using Cloud Build (No Docker needed)

set -e

# Configuration for PRODUCTION SERVICE (replaces existing)
PROJECT_ID="hackathon-468512"
SERVICE_NAME="morning-image-api"  # Same name - replaces existing service
REGION="asia-east1"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "🚀 Deploying PRODUCTION Image Generation API to Google Cloud Run (via Cloud Build)"
echo "Project ID: $PROJECT_ID"
echo "Service Name: $SERVICE_NAME (REPLACING EXISTING)"
echo "Region: $REGION"
echo "Image: $IMAGE_NAME"
echo ""
echo "⚠️  This will REPLACE the existing production service with new text overlay functionality"

# Build image using Cloud Build (no local Docker needed)
echo "Building image using Cloud Build..."
gcloud builds submit --tag $IMAGE_NAME .

# Deploy to Cloud Run (replaces existing service)
echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --port 8081 \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --project $PROJECT_ID

echo "🎉 Production Deployment completed!"
PROD_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --project $PROJECT_ID --format 'value(status.url)')
echo "🔗 Production Service URL: $PROD_URL"
echo ""
echo "✅ NEW PRODUCTION ENDPOINTS:"
echo "   • Health: $PROD_URL/health"
echo "   • NEW Text Overlay: $PROD_URL/generate-with-text"
echo "   • Original (compatible): $PROD_URL/generate"
echo ""
echo "🎯 Your existing URL now has perfect Chinese text overlay functionality!"
echo "📝 Use /generate-with-text for best results with Chinese text"