#!/usr/bin/env python3
"""
Test client for the image generation API
Usage: python test_image_api.py
"""

import requests
import json
import base64
import os

# API base URL - deployed service
API_BASE_URL = "https://morning-image-api-855188038216.asia-east1.run.app"

def test_health():
    """Test health check endpoint"""
    print("Testing health check...")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_enhance_prompt():
    """Test prompt enhancement"""
    print("\nTesting prompt enhancement...")
    data = {
        "prompt": "a cute cat",
        "style": "realistic"
    }
    
    try:
        response = requests.post(f"{API_BASE_URL}/enhance-prompt", json=data)
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Original: {result.get('original_prompt')}")
        print(f"Enhanced: {result.get('enhanced_prompt')}")
        return response.status_code == 200
    except Exception as e:
        print(f"Prompt enhancement failed: {e}")
        return False

def test_prompt_variations():
    """Test prompt variations"""
    print("\nTesting prompt variations...")
    data = {
        "base_prompt": "a beautiful landscape at sunset",
        "variations": 3
    }
    
    try:
        response = requests.post(f"{API_BASE_URL}/test-prompts", json=data)
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Base prompt: {result.get('base_prompt')}")
        print("Variations:")
        for i, variation in enumerate(result.get('variations', []), 1):
            print(f"  {i}. {variation}")
        return response.status_code == 200
    except Exception as e:
        print(f"Prompt variations failed: {e}")
        return False

def test_image_generation():
    """Test image generation (may take longer)"""
    print("\nTesting image generation...")
    data = {
        "prompt": "a simple blue circle on white background",
        "number_of_images": 1,
        "guidance_scale": 20
    }
    
    try:
        response = requests.post(f"{API_BASE_URL}/generate-image", json=data)
        print(f"Status: {response.status_code}")
        result = response.json()
        
        if response.status_code == 200:
            print(f"Generated {result.get('count', 0)} images")
            
            # Save first image to file for verification
            if result.get('images'):
                image_data = result['images'][0]['image_base64']
                with open('test_generated_image.png', 'wb') as f:
                    f.write(base64.b64decode(image_data))
                print("Image saved as 'test_generated_image.png'")
        else:
            print(f"Error: {result.get('message')}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"Image generation failed: {e}")
        return False

def test_prompt_test():
    """Test the new prompt testing endpoint (text only)"""
    print("\nTesting prompt testing endpoint...")
    data = {
        "prompt": "make this more artistic and colorful"
    }
    
    try:
        response = requests.post(f"{API_BASE_URL}/prompt-test", json=data)
        print(f"Status: {response.status_code}")
        result = response.json()
        
        if response.status_code == 200:
            print(f"Original prompt: {result.get('original_prompt')}")
            print(f"Enhanced prompt: {result.get('enhanced_prompt')}")
            print(f"Had input image: {result.get('had_input_image')}")
            
            # Save the generated image
            if result.get('image_base64'):
                image_data = result['image_base64']
                with open('prompt_test_image.png', 'wb') as f:
                    f.write(base64.b64decode(image_data))
                print("Image saved as 'prompt_test_image.png'")
        else:
            print(f"Error: {result.get('message')}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"Prompt testing failed: {e}")
        return False

def test_morning_image_generation():
    """Test the main morning image generation endpoint"""
    print("\\nTesting morning image generation...")
    data = {
        "festival": "冬至",
        "blessing": "平安健康，闔家團圓",
        "style": "countryside_landscape"
    }
    
    try:
        response = requests.post(f"{API_BASE_URL}/generate", json=data)
        print(f"Status: {response.status_code}")
        result = response.json()
        
        if response.status_code == 200:
            print(f"Festival: {result.get('festival')}")
            print(f"Style: {result.get('style')}")
            print(f"Prompt used: {result.get('prompt_used', '')[:100]}...")
            
            # Save the generated image
            if result.get('image_base64'):
                image_data = result['image_base64']
                with open('morning_image.png', 'wb') as f:
                    f.write(base64.b64decode(image_data))
                print("Morning image saved as 'morning_image.png'")
        else:
            print(f"Error: {result.get('message')}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"Morning image generation failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Starting Image Generation API Tests")
    print("=" * 50)
    
    tests = [
        ("Health Check", test_health),
        ("Morning Image Generation", test_morning_image_generation),
        ("Prompt Enhancement", test_enhance_prompt),
        ("Prompt Variations", test_prompt_variations),
        ("Image Generation", test_image_generation),
        ("Prompt Testing", test_prompt_test)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        success = test_func()
        results.append((test_name, success))
        print(f"{test_name}: {'PASS' if success else 'FAIL'}")
    
    print("\n" + "="*50)
    print("TEST RESULTS SUMMARY:")
    for test_name, success in results:
        status = "PASS" if success else "FAIL"
        print(f"  {test_name}: {status}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    print(f"\nOverall: {passed}/{total} tests passed")

if __name__ == "__main__":
    main()