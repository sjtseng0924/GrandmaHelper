#!/usr/bin/env python3
"""
Complete test script that saves all files locally
Usage: python test_and_download.py "your test prompt"
"""

import requests
import json
import sys
import os
from datetime import datetime

API_BASE_URL = "https://morning-image-api-855188038216.asia-east1.run.app"

def test_and_download(test_prompt=None, test_date=None):
    """Test API and download all debug files"""
    print(f"🧪 Testing with prompt: '{test_prompt}' date: '{test_date}'")
    
    # Step 1: Generate image and get debug info
    data = {}
    if test_prompt:
        data['prompt'] = test_prompt
    if test_date:
        data['date'] = test_date
    
    print("📤 Calling /generate-json...")
    response = requests.post(f"{API_BASE_URL}/generate-json", data=data, timeout=120)
    
    if response.status_code != 200:
        print(f"❌ Error: {response.text}")
        return
    
    result = response.json()
    print(f"✅ Generation successful!")
    
    # Step 2: Show savepoints
    savepoints = result.get('savepoints', {})
    print(f"\n🔍 SAVEPOINTS:")
    for step, data in savepoints.items():
        print(f"  {step}: {data}")
    
    # Step 3: Download all files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Get debug file list
    debug_response = requests.get(f"{API_BASE_URL}/debug")
    debug_info = debug_response.json()
    recent_files = debug_info.get('recent_files', [])
    
    # Filter recent files (last 3)
    latest_files = sorted(recent_files, key=lambda x: x['modified'])[-6:]
    
    print(f"\n📁 DOWNLOADING FILES:")
    downloaded = []
    
    for file_info in latest_files:
        filename = file_info['name']
        local_name = f"{timestamp}_{filename}"
        
        print(f"  ⬇️  {filename} ({file_info['size']} bytes)")
        
        try:
            file_response = requests.get(f"{API_BASE_URL}/debug/files/{filename}")
            if file_response.status_code == 200:
                with open(local_name, 'wb') as f:
                    f.write(file_response.content)
                downloaded.append(local_name)
                print(f"     ✅ Saved as: {local_name}")
            else:
                print(f"     ❌ Failed to download: {filename}")
        except Exception as e:
            print(f"     ❌ Error downloading {filename}: {e}")
    
    # Step 4: Save prompt and text data locally
    prompt_data = {
        'image_prompt': savepoints.get('3_prompt_building', {}).get('image_prompt', ''),
        'text_generation': savepoints.get('2_text_generation', {}),
        'input_parsing': savepoints.get('1_input_parsing', {}),
        'test_info': {
            'timestamp': timestamp,
            'test_prompt': test_prompt,
            'test_date': test_date
        }
    }
    prompt_filename = f"{timestamp}_prompt_and_text.json"
    with open(prompt_filename, 'w', encoding='utf-8') as f:
        json.dump(prompt_data, f, ensure_ascii=False, indent=2)
    downloaded.append(prompt_filename)
    print(f"  ✅ Prompt & text data saved as: {prompt_filename}")

    # Step 5: Save final image from base64
    if 'image_base64' in result:
        import base64
        final_image_name = f"{timestamp}_final_result.jpg"
        image_data = base64.b64decode(result['image_base64'])
        with open(final_image_name, 'wb') as f:
            f.write(image_data)
        downloaded.append(final_image_name)
        print(f"  ✅ Final image saved as: {final_image_name}")
    
    # Step 6: Summary
    print(f"\n🎯 SUMMARY:")
    print(f"  📝 Prompt used: {savepoints.get('3_prompt_building', {}).get('image_prompt', 'N/A')[:100]}...")
    print(f"  📝 Text overlay: {savepoints.get('2_text_generation', {})}")
    print(f"  📁 Files downloaded: {len(downloaded)}")
    
    # Identify the key files
    prompt_file = None
    background_file = None
    final_file = None
    
    # Extract timestamp from the final image path to match background
    final_timestamp = None
    final_output_path = savepoints.get('5_final_composition', {}).get('output_file', '')
    if 'final_image_' in final_output_path:
        final_timestamp = final_output_path.split('final_image_')[1].split('.')[0]
    
    for filename in downloaded:
        if 'prompt_and_text' in filename:
            prompt_file = filename
        elif 'image_prompt' in filename or 'PROMPT_BUILD_RESULT' in filename:
            if not prompt_file:  # Prefer our local prompt file
                prompt_file = filename
        elif 'background_only' in filename or 'generated_bg' in filename:
            # The generated_bg files are actually the clean backgrounds
            if final_timestamp and final_timestamp in filename:
                # This matches our current generation
                background_file = filename
            elif not background_file:
                # Fallback to any background file
                background_file = filename
        elif 'final_image' in filename or 'final_result' in filename:
            final_file = filename
    
    print(f"\n🔑 KEY FILES:")
    print(f"  1️⃣  PROMPT: {prompt_file or 'Not found'}")
    print(f"  2️⃣  UNTEXT PIC: {background_file or 'Not found'}")  
    print(f"  3️⃣  TEXTED PIC: {final_file or 'Not found'}")
    
    return downloaded

def main():
    if len(sys.argv) > 1:
        test_prompt = sys.argv[1]
        test_date = sys.argv[2] if len(sys.argv) > 2 else None
    else:
        # Interactive mode
        test_prompt = input("Enter test prompt (or press Enter for random): ").strip()
        test_date = input("Enter date YYYY-MM-DD (or press Enter): ").strip()
        
        if not test_prompt:
            test_prompt = None
        if not test_date:
            test_date = None
    
    downloaded_files = test_and_download(test_prompt, test_date)
    
    if downloaded_files:
        print(f"\n🎉 Test complete! Check the downloaded files:")
        for filename in downloaded_files:
            print(f"   📄 {filename}")

if __name__ == "__main__":
    main()