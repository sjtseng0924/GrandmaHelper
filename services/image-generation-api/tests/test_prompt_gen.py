#!/usr/bin/env python3
"""
Test script for prompt_generation.py module
"""
import sys
from prompt_generation import load_morning_config, generate_display_text, build_image_prompt

def test_scenarios():
    """Test various prompt generation scenarios"""
    config = load_morning_config()
    
    test_cases = [
        {"desc": "Christmas Day", "date": "2025-12-25", "prompt": None, "style": "countryside_landscape"},
        {"desc": "Valentine's Day", "date": "2025-02-14", "prompt": None, "style": "coffee_rose"},
        {"desc": "Custom prompt with style", "date": None, "prompt": "cute kittens with morning coffee", "style": "apple_closeup"},
        {"desc": "Custom text only", "date": None, "prompt": None, "custom_text": "今天會很美好", "style": None},
        {"desc": "Random default", "date": None, "prompt": None, "style": None},
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"TEST CASE {i}: {case['desc']}")
        print(f"{'='*60}")
        
        # Generate text
        text_data = generate_display_text(
            config, 
            prompt=case['prompt'],
            date=case['date'],
            custom_text=case.get('custom_text')
        )
        
        # Generate prompt  
        image_prompt, source_type = build_image_prompt(config, text_data, case['style'])
        
        print(f"📅 Date: {case['date']}")
        print(f"💬 Custom prompt: {case['prompt']}")
        print(f"🎨 Style: {case['style']}")
        print(f"📝 Text overlay: {text_data['main_text']} | {text_data['blessing_text']}")
        print(f"🖼️  Image prompt ({source_type}):")
        print(f"   {image_prompt}")
        
        if text_data.get('holiday'):
            print(f"🎉 Holiday detected: {text_data['holiday']}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Single test case
        prompt = sys.argv[1] if len(sys.argv) > 1 else None
        date = sys.argv[2] if len(sys.argv) > 2 else None
        style = sys.argv[3] if len(sys.argv) > 3 else None
        
        config = load_morning_config()
        text_data = generate_display_text(config, prompt=prompt, date=date)
        image_prompt, source_type = build_image_prompt(config, text_data, style)
        
        print("Generated text data:", text_data)
        print("Generated prompt:", image_prompt)
        print("Source type:", source_type)
    else:
        # Run all test scenarios
        test_scenarios()