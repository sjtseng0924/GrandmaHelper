#!/usr/bin/env python3
"""
Quick test script for the enhanced API
"""

import requests
import json
import base64
from datetime import datetime

API_BASE = "https://morning-image-api-855188038216.asia-east1.run.app"

def test_basic_generate():
    """Test basic image generation"""
    print("🧪 Testing basic generation...")
    
    response = requests.post(f"{API_BASE}/generate", timeout=120)
    
    if response.status_code == 200:
        filename = f"test_basic_{datetime.now().strftime('%H%M%S')}.jpg"
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"✅ Basic test successful! Saved: {filename}")
        return True
    else:
        print(f"❌ Basic test failed: {response.status_code}")
        print(response.text)
        return False

def test_with_prompt():
    """Test with user prompt"""
    print("🧪 Testing with prompt 'two realistic dogs'...")
    
    data = {'prompt': 'two realistic dogs'}
    response = requests.post(f"{API_BASE}/generate", data=data, timeout=120)
    
    if response.status_code == 200:
        filename = f"test_dogs_{datetime.now().strftime('%H%M%S')}.jpg"
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"✅ Prompt test successful! Saved: {filename}")
        return True
    else:
        print(f"❌ Prompt test failed: {response.status_code}")
        print(response.text)
        return False

def test_json_response():
    """Test JSON response to see blessing text"""
    print("🧪 Testing JSON response...")
    
    data = {'prompt': 'beautiful sunset'}
    response = requests.post(f"{API_BASE}/generate-json", data=data, timeout=120)
    
    if response.status_code == 200:
        result = response.json()
        
        print("✅ JSON test successful!")
        print(f"📝 Generated blessing: {result['savepoints']['2_text_generation']['blessing_text']}")
        print(f"📝 Enhanced prompt: {result['savepoints']['3_prompt_building']['image_prompt'][:100]}...")
        
        # Save image from base64
        image_data = base64.b64decode(result['image_base64'])
        filename = f"test_json_{datetime.now().strftime('%H%M%S')}.jpg"
        with open(filename, 'wb') as f:
            f.write(image_data)
        print(f"💾 Image saved: {filename}")
        
        return True
    else:
        print(f"❌ JSON test failed: {response.status_code}")
        print(response.text)
        return False

def test_health():
    """Test health endpoint"""
    print("🧪 Testing health endpoint...")
    
    response = requests.get(f"{API_BASE}/health")
    
    if response.status_code == 200:
        health = response.json()
        print("✅ Health check successful!")
        print(f"📊 Service: {health['service']}")
        print(f"📊 Version: {health['version']}")
        print(f"📊 Features: {', '.join(health['features'])}")
        return True
    else:
        print(f"❌ Health check failed: {response.status_code}")
        return False

def main():
    print("🚀 Testing Enhanced Morning Image API")
    print("=" * 50)
    
    # Test health first
    if not test_health():
        print("❌ Health check failed, stopping tests")
        return
    
    print()
    
    # Test basic generation
    test_basic_generate()
    print()
    
    # Test with prompt
    test_with_prompt()
    print()
    
    # Test JSON response
    test_json_response()
    
    print()
    print("🎉 All tests completed! Check the generated images.")

if __name__ == "__main__":
    main()