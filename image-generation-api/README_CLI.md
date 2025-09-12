# Quick Test CLI for Gemini Image Generation

## 📁 **Organized Structure**

All image generation API files are now organized in the `image-generation-api/` folder:

```
image-generation-api/
├── production_morning_api.py      # Main production API
├── quick_test_cli.py              # 🆕 Quick CLI for testing  
├── requirements_production.txt     # Production API deps
├── requirements_cli.txt           # CLI deps
├── Dockerfile.production          # Docker config
├── cloudbuild.yaml               # Cloud Build config
├── real_ai_morning.png           # Example output
└── archive/                      # Old versions
```

## 🚀 **Quick CLI Usage**

### Basic Usage
```bash
# Set API key
export GEMINI_API_KEY="your-api-key-here"

# Generate image with prompt
python quick_test_cli.py "cute kittens playing with yarn balls"

# Custom output filename
python quick_test_cli.py "sunset over mountains" -o mountain_sunset.png
```

### With Input Images (Coming Soon)
```bash
# Use input images to guide generation
python quick_test_cli.py "make this more colorful" input1.jpg input2.png
```

## ✅ **Features**

✅ **Simple Command Line Interface** - Just provide a prompt  
✅ **Real AI Generation** - Uses Gemini 2.5 Flash (not fallback images)  
✅ **High Quality Output** - Generates 1.5MB+ real AI artwork  
✅ **Custom Output Names** - Specify your own filename  
✅ **Error Handling** - Clear error messages and validation  
✅ **API Key Validation** - Checks for required environment variables  

## 📊 **Example Output**

```bash
$ python quick_test_cli.py "cute kittens playing with yarn balls"
🚀 Quick Gemini Image Generator
📝 Prompt: cute kittens playing with yarn balls  
🎨 Generating image...
✅ Image saved as generated_image.png (1.53MB)
🎯 Real AI image generated with Gemini 2.5 Flash!
```

## 🔧 **Setup**

```bash
# Install dependencies
pip install -r requirements_cli.txt

# Set API key
export GEMINI_API_KEY="your-gemini-api-key"

# Make executable (optional)
chmod +x quick_test_cli.py
```

## 🎯 **Mission Accomplished**

✅ Organized all image generation files into dedicated folder  
✅ Created simple CLI for quick testing  
✅ Uses real Gemini 2.5 Flash (not "Gemini Nano" which doesn't exist)  
✅ Generates high-quality AI images (1.5MB+)  
✅ Ready for quick prompt testing and experimentation  

Perfect for rapid prototyping and testing different prompts! 🎨