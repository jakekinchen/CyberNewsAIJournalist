import os
from post_synthesis import generate_featured_image

def test_featured_images():
    """Test featured image generation with various titles."""
    test_cases = [
        {
            "title": "CVE: CVE-2025-22936",
            "is_cve": True,
            "output": "cve_test.png"
        },
        {
            "title": "The Rise of Decentralized Finance in 2025: A Comprehensive Analysis of Blockchain Technology and Its Impact on Modern Financial Systems",
            "is_cve": False,
            "output": "long_title_test.png"
        },
        {
            "title": "AI Security Update",
            "is_cve": False,
            "output": "short_title_test.png"
        }
    ]
    
    print("Testing featured image generation...")
    for case in test_cases:
        print(f"\nGenerating image for: {case['title']}")
        image_data = generate_featured_image(case['title'], case['is_cve'])
        
        if image_data:
            # Save the test image
            with open(case['output'], 'wb') as f:
                f.write(image_data)
            print(f"Successfully generated {case['output']}")
            
            # Get file size
            size_kb = os.path.getsize(case['output']) / 1024
            print(f"Image size: {size_kb:.1f}KB")
        else:
            print(f"Failed to generate image for {case['title']}")

if __name__ == "__main__":
    test_featured_images() 