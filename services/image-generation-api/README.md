# Image Generation API for GrandmaHelper

This is a simple image generation and prompt testing service built on Google Vertex AI Imagen.

## Features

- **Image Generation**: Generate images from text prompts using Imagen 3.0
- **Prompt Enhancement**: Improve user prompts using Gemini for better image generation
- **Prompt Variations**: Generate multiple variations of a base prompt for testing
- **Health Check**: Simple health monitoring endpoint

## API Endpoints

### POST /generate-image
Generate images from text prompts.

**Request:**
```json
{
  "prompt": "a beautiful sunset over mountains",
  "number_of_images": 1,
  "guidance_scale": 20,
  "safety_filter_level": "block_few"
}
```

**Response:**
```json
{
  "status": "success",
  "prompt": "a beautiful sunset over mountains",
  "images": [
    {
      "image_id": 1,
      "image_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
      "mime_type": "image/png"
    }
  ],
  "count": 1
}
```

### POST /enhance-prompt
Enhance user prompts for better image generation.

**Request:**
```json
{
  "prompt": "a cute cat",
  "style": "realistic"
}
```

**Response:**
```json
{
  "status": "success",
  "original_prompt": "a cute cat",
  "enhanced_prompt": "A photorealistic portrait of an adorable fluffy tabby cat with bright green eyes, sitting in golden hour lighting...",
  "style": "realistic"
}
```

### POST /test-prompts
Generate variations of a base prompt for testing.

**Request:**
```json
{
  "base_prompt": "a beautiful landscape at sunset",
  "variations": 3
}
```

**Response:**
```json
{
  "status": "success",
  "base_prompt": "a beautiful landscape at sunset",
  "variations": [
    "A serene mountain landscape bathed in warm golden sunset light...",
    "Rolling hills and meadows under a vibrant orange and pink sunset sky...",
    "A dramatic coastal scene with cliffs silhouetted against a fiery sunset..."
  ],
  "count": 3
}
```

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "image-generation-api",
  "version": "1.0.0"
}
```

## Setup and Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up Google Cloud credentials:**
   ```bash
   gcloud auth application-default login
   ```

3. **Deploy to Cloud Run:**
   ```bash
   ./deploy.sh
   ```
   Service will be available at: https://morning-image-api-855188038216.asia-east1.run.app

4. **Test the deployed API:**
   ```bash
   python test_api.py
   ```

## Deployment

### Local Docker Testing
```bash
docker build -t image-gen-api .
docker run -p 8081:8081 image-gen-api
```

### GCP Cloud Run Deployment
```bash
./deploy.sh
```

## Environment Variables

- `PORT`: Server port (default: 8081)
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account key (for authentication)

## Notes

- Image generation may take 10-30 seconds depending on complexity
- Generated images are returned as base64-encoded PNG data
- The service uses Google Cloud Vertex AI, ensure proper authentication
- For production, consider implementing rate limiting and authentication