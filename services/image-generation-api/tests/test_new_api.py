#!/usr/bin/env python3
"""
Test script for the improved Morning Image Generation API
Tests all the curl examples you specified
"""

import requests
import json
import base64
import os
import time

# API base URL - update this to your deployed service URL
# API_BASE_URL = "http://localhost:8081"  # Local testing
API_BASE_URL = "https://morning-image-api-855188038216.asia-east1.run.app"  # Production

def save_image_from_response(response, filename):
    """Save image from response to file"""
    if response.headers.get('content-type', '').startswith('image/'):
        # Direct image response
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"✅ Image saved as '{filename}' ({len(response.content)} bytes)")
        return True
    else:
        print(f"❌ Expected image response, got {response.headers.get('content-type')}")
        print(f"Response: {response.text[:200]}...")
        return False

def test_basic_random_image():
    """Test: Basic Random Image - curl -X POST .../generate -o morning.png"""
    print("\n" + "="*60)
    print("🧪 TEST: Basic Random Image")
    print("="*60)
    
    try:
        # Empty POST request
        response = requests.post(f"{API_BASE_URL}/generate", timeout=60)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            return save_image_from_response(response, 'test_basic_random.png')
        else:
            print(f"❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Basic random image test failed: {e}")
        return False

def test_with_text_prompt():
    """Test: With Text Prompt - curl -X POST .../generate -F "prompt=cute cats and coffee" -o morning.png"""
    print("\n" + "="*60)
    print("🧪 TEST: With Text Prompt")
    print("="*60)
    
    try:
        # Form data with prompt
        data = {'prompt': 'cute cats and coffee'}
        response = requests.post(f"{API_BASE_URL}/generate", data=data, timeout=60)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            return save_image_from_response(response, 'test_with_prompt.png')
        else:
            print(f"❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Text prompt test failed: {e}")
        return False

def test_holiday_date_image():
    """Test: Holiday/Date Image - curl -X POST .../generate -F "date=2024-12-25" -o christmas.png"""
    print("\n" + "="*60)
    print("🧪 TEST: Holiday/Date Image")
    print("="*60)
    
    try:
        # Form data with date
        data = {'date': '2024-12-25'}
        response = requests.post(f"{API_BASE_URL}/generate", data=data, timeout=60)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            return save_image_from_response(response, 'test_christmas.png')
        else:
            print(f"❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Holiday date test failed: {e}")
        return False

def test_image_upload_with_text():
    """Test: Image Upload + Text - curl -X POST .../generate -F "image=@photo.jpg" -F "prompt=make it peaceful" -o edited.png"""
    print("\n" + "="*60)
    print("🧪 TEST: Image Upload + Text")
    print("="*60)
    
    try:
        # Create a simple test image file
        test_image_path = 'test_upload.jpg'
        if not os.path.exists(test_image_path):
            # Create a simple colored square for testing
            from PIL import Image
            img = Image.new('RGB', (512, 512), color='lightblue')
            img.save(test_image_path, 'JPEG')
            print(f"Created test image: {test_image_path}")
        
        # Upload image with prompt
        with open(test_image_path, 'rb') as f:
            files = {'image': f}
            data = {'prompt': 'make it peaceful and serene'}
            response = requests.post(f"{API_BASE_URL}/generate", files=files, data=data, timeout=60)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            return save_image_from_response(response, 'test_uploaded_edited.png')
        else:
            print(f"❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Image upload test failed: {e}")
        return False

def test_json_response():
    """Test: JSON Response - curl -X POST .../generate-json -F "prompt=beautiful sunrise" """
    print("\n" + "="*60)
    print("🧪 TEST: JSON Response with Debug Info")
    print("="*60)
    
    try:
        # Form data with prompt for JSON response
        data = {'prompt': 'beautiful sunrise over mountains'}
        response = requests.post(f"{API_BASE_URL}/generate-json", data=data, timeout=60)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ JSON response received")
            print(f"Status: {result.get('status')}")
            print(f"MIME type: {result.get('mime_type')}")
            print(f"Debug directory: {result.get('debug_dir')}")
            
            # Show savepoints (debug info)
            if 'savepoints' in result:
                print("\n🔍 SAVEPOINTS (Debug Info):")
                for step, data in result['savepoints'].items():
                    print(f"  {step}: {data}")
            
            # Save the base64 image
            if 'image_base64' in result:
                image_data = base64.b64decode(result['image_base64'])
                with open('test_json_response.jpg', 'wb') as f:
                    f.write(image_data)
                print(f"✅ Image saved as 'test_json_response.jpg' ({len(image_data)} bytes)")
                return True
        else:
            print(f"❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ JSON response test failed: {e}")
        return False

def test_template_generation():
    """Test: Template Generation - curl -X POST .../generate-template -H "Content-Type: application/json" -d '{"template":"coffee_style","custom_text":"peaceful morning"}' """
    print("\n" + "="*60)
    print("🧪 TEST: Template Generation")
    print("="*60)
    
    try:
        # JSON body for template generation
        headers = {'Content-Type': 'application/json'}
        payload = {
            "template": "countryside_landscape", 
            "custom_text": "peaceful morning vibes"
        }
        response = requests.post(f"{API_BASE_URL}/generate-template", 
                               json=payload, headers=headers, timeout=60)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Template response received")
            print(f"Template: {result.get('template')}")
            print(f"Status: {result.get('status')}")
            
            # Show savepoints
            if 'savepoints' in result:
                print("\n🔍 Template Savepoints:")
                for key, value in result['savepoints'].items():
                    print(f"  {key}: {value}")
            
            # Save the base64 image
            if 'image_base64' in result:
                image_data = base64.b64decode(result['image_base64'])
                with open('test_template.jpg', 'wb') as f:
                    f.write(image_data)
                print(f"✅ Template image saved as 'test_template.jpg' ({len(image_data)} bytes)")
                return True
        else:
            print(f"❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Template generation test failed: {e}")
        return False

def test_health_and_debug():
    """Test health and debug endpoints"""
    print("\n" + "="*60)
    print("🧪 TEST: Health & Debug Endpoints")
    print("="*60)
    
    try:
        # Test health endpoint
        response = requests.get(f"{API_BASE_URL}/health")
        print(f"Health Status: {response.status_code}")
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ Service: {health_data.get('service')}")
            print(f"✅ Version: {health_data.get('version')}")
            print(f"✅ Config Loaded: {health_data.get('config_loaded')}")
            print(f"✅ Debug Dir: {health_data.get('debug_dir')}")
        
        # Test debug endpoint
        response = requests.get(f"{API_BASE_URL}/debug")
        print(f"Debug Status: {response.status_code}")
        if response.status_code == 200:
            debug_data = response.json()
            print(f"✅ Debug Directory: {debug_data.get('debug_directory')}")
            print(f"✅ Config Summary: {debug_data.get('config_summary')}")
            
            recent_files = debug_data.get('recent_files', [])
            print(f"✅ Recent Debug Files: {len(recent_files)}")
            for file_info in recent_files[-3:]:  # Show last 3 files
                print(f"  - {file_info['name']} ({file_info['size']} bytes)")
        
        return True
        
    except Exception as e:
        print(f"❌ Health/debug test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting Morning Image Generation API Tests")
    print(f"🎯 Testing API at: {API_BASE_URL}")
    print("="*80)
    
    # Test order matches your curl examples
    tests = [
        ("Health & Debug", test_health_and_debug),
        ("Basic Random Image", test_basic_random_image),
        ("With Text Prompt", test_with_text_prompt), 
        ("Holiday/Date Image", test_holiday_date_image),
        ("JSON Response", test_json_response),
        ("Template Generation", test_template_generation),
        # ("Image Upload + Text", test_image_upload_with_text),  # Requires PIL
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n⏳ Running: {test_name}")
        start_time = time.time()
        try:
            success = test_func()
            duration = time.time() - start_time
            results.append((test_name, success, f"{duration:.1f}s"))
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"🏁 {test_name}: {status} ({duration:.1f}s)")
        except Exception as e:
            duration = time.time() - start_time
            results.append((test_name, False, f"{duration:.1f}s"))
            print(f"🏁 {test_name}: ❌ FAIL ({duration:.1f}s) - {e}")
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST RESULTS SUMMARY:")
    print("="*80)
    
    passed = 0
    for test_name, success, duration in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status}  {test_name:<25} {duration:>10}")
        if success:
            passed += 1
    
    total = len(results)
    print(f"\n🎯 Overall: {passed}/{total} tests passed ({100*passed/total:.0f}%)")
    
    if passed == total:
        print("🎉 All tests passed! Your API is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the logs above for details.")
    
    print(f"\n💡 Check the generated images and debug files:")
    print(f"   - Generated images: test_*.png, test_*.jpg") 
    print(f"   - Debug directory: /tmp/morning_debug (on server)")

if __name__ == "__main__":
    main()