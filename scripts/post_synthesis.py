import json
import os
from dotenv import load_dotenv
from scripts.supabase_utils import supabase
from scripts.wp_utils import fetch_categories, fetch_tags
from scripts.gpt_utils import query_gpt, function_call_gpt, generate_wp_field_completion_function
from datetime import datetime
import re
from bs4 import BeautifulSoup, Tag, NavigableString
import math
from scripts.prompts import synthesis, combined_factsheet_system_prompt
import requests
from PIL import Image, ImageDraw, ImageFont
import io
import textwrap
import base64

# Load .env file
load_dotenv()
# Get prompt from environment variables
synthesis_prompt = synthesis

def post_synthesis(topic, categories, tags):
    """Generate WordPress post content from a topic."""
    try:
        # Skip rejected CVEs
        topic_name = topic.get('name', '')
        if isinstance(topic_name, dict):
            topic_name = topic_name.get('rendered', '')
        elif not isinstance(topic_name, str):
            topic_name = str(topic_name)
        
        if topic_name.startswith('CVE:') and '** REJECT **' in str(topic.get('description', '')):
            print(f"Skipping rejected CVE: {topic_name}")
            return None
            
        # Create the post info
        content = f'<div style="max-width:640px; margin: auto;">'
        
        # Handle CVE posts differently
        if topic_name.startswith('CVE:'):
            # Extract CVE details
            description = topic.get('description', '')
            if isinstance(description, dict):
                description = description.get('rendered', '')
            elif not isinstance(description, str):
                description = str(description)
            
            cvss_match = re.search(r'CVSS Score: ([\d.]+) \((.*?)\)', description)
            cvss_score = cvss_match.group(1) if cvss_match else 'N/A'
            severity = cvss_match.group(2) if cvss_match else 'N/A'
            
            # Enhanced meta description for CVE posts
            meta_desc = f"Security Alert: {topic_name} - {severity} severity vulnerability. CVSS Score: {cvss_score}. "
            if description:
                first_sentence = re.split(r'[.!?]', description)[0].strip()
                meta_desc += first_sentence
            
            # Enhanced content with structured data
            content += f'<div itemscope itemtype="http://schema.org/TechArticle">'
            content += f'<meta itemprop="headline" content="{topic_name}">'
            content += f'<meta itemprop="description" content="{meta_desc}">'
            content += f'<h2>Vulnerability Details</h2>'
            content += f'<p><strong>CVSS Score:</strong> <span itemprop="score">{cvss_score}</span> (<span itemprop="severity">{severity}</span>)</p>'
            content += f'<div itemprop="articleBody"><p>{description}</p></div>'
            content += '</div>'
            
            # Enhanced security tags
            security_tags = ['Security Vulnerabilities', 'CVE']
            
            # Add severity-based tags
            if severity.lower() == 'critical':
                security_tags.extend(['Critical Vulnerabilities', 'High-Risk Vulnerabilities'])
            elif severity.lower() == 'high':
                security_tags.append('High-Risk Vulnerabilities')
            elif severity.lower() == 'medium':
                security_tags.append('Medium-Risk Vulnerabilities')
                
            # Add affected system tags with broader coverage
            description_lower = description.lower()
            system_tags = {
                'windows': ['Windows Security', 'Microsoft Vulnerabilities'],
                'linux': ['Linux Security', 'Unix Systems'],
                'android': ['Mobile Security', 'Android Vulnerabilities'],
                'ios': ['Mobile Security', 'iOS Vulnerabilities'],
                'router': ['Network Security', 'Network Infrastructure'],
                'network': ['Network Security', 'Infrastructure Security'],
                'web': ['Web Security', 'Web Application Security'],
                'http': ['Web Security', 'Protocol Vulnerabilities'],
                'cloud': ['Cloud Security', 'Cloud Infrastructure'],
                'aws': ['Cloud Security', 'AWS Security'],
                'azure': ['Cloud Security', 'Microsoft Azure'],
                'kubernetes': ['Container Security', 'Cloud Native'],
                'docker': ['Container Security', 'DevOps Security']
            }
            
            for keyword, tags_list in system_tags.items():
                if keyword in description_lower:
                    security_tags.extend(tags_list)
                    
            # Get tag IDs for the selected tags
            post_tags = []
            for tag_name in security_tags:
                matching_tags = [tag['id'] for tag in tags if isinstance(tag, dict) and tag.get('name', '').lower() == tag_name.lower()]
                if matching_tags:
                    post_tags.extend(matching_tags)
                    
            if not post_tags:  # If no tags were found, use default security tags
                post_tags = [tag['id'] for tag in tags if isinstance(tag, dict) and tag.get('name', '') in ['Security Vulnerabilities', 'CVE']]
        else:
            # Regular article
            description = topic.get('description', '')
            if isinstance(description, dict):
                description = description.get('rendered', '')
            elif not isinstance(description, str):
                description = str(description)
            content += f'<p>{description}</p>'
        
        # Add factsheet content if available
        if topic.get('factsheet'):
            content += '<h2>Key Facts</h2>'
            if isinstance(topic['factsheet'], str):
                try:
                    factsheet = json.loads(topic['factsheet'])
                except json.JSONDecodeError:
                    factsheet = topic['factsheet']
            else:
                factsheet = topic['factsheet']
            
            if isinstance(factsheet, list):
                content += '<ul>'
                for fact in factsheet:
                    content += f'<li>{str(fact)}</li>'
                content += '</ul>'
            else:
                content += f'<p>{str(factsheet)}</p>'
        
        # Add external source info if available
        if topic.get('external_source_info'):
            content += '<h2>Additional Information</h2>'
            if isinstance(topic['external_source_info'], str):
                try:
                    ext_info = json.loads(topic['external_source_info'])
                except json.JSONDecodeError:
                    ext_info = topic['external_source_info']
            else:
                ext_info = topic['external_source_info']
            
            if isinstance(ext_info, list):
                content += '<ul>'
                for info in ext_info:
                    content += f'<li>{str(info)}</li>'
                content += '</ul>'
            else:
                content += f'<p>{str(ext_info)}</p>'
        
        content += '</div>'
        
        # Generate unique slug
        base_slug = topic_name.lower()
        base_slug = re.sub(r'[^a-z0-9\s-]', '', base_slug)  # Remove special characters
        base_slug = re.sub(r'\s+', '-', base_slug.strip())  # Replace spaces with hyphens
        
        # Create meta description
        if topic_name.startswith('CVE:'):
            # For CVE posts, create a structured meta description
            description = topic.get('description', '')
            if isinstance(description, dict):
                description = description.get('rendered', '')
            elif not isinstance(description, str):
                description = str(description)
                
            cvss_match = re.search(r'CVSS Score: ([\d.]+) \((.*?)\)', description)
            cvss_score = cvss_match.group(1) if cvss_match else 'N/A'
            severity = cvss_match.group(2) if cvss_match else 'N/A'
            
            # Extract the main vulnerability description (first sentence)
            main_desc = re.split(r'[.!?]', description)[0].strip()
            
            meta_desc = f"{topic_name}: {main_desc}. CVSS Score: {cvss_score} ({severity})"
        else:
            # For regular articles, use the description
            meta_desc = description
            
        # Ensure meta description is not too long
        if len(meta_desc) > 155:
            # Try to cut at a sentence boundary
            sentences = re.split(r'[.!?]', meta_desc)
            meta_desc = ''
            for sentence in sentences:
                if len(meta_desc + sentence) <= 152:
                    meta_desc += sentence + '.'
                else:
                    break
            if not meta_desc:  # If no complete sentence fits, cut at word boundary
                meta_desc = meta_desc[:152].rsplit(' ', 1)[0]
            meta_desc = meta_desc.strip() + '...'
        
        # Get default category ID
        default_category_id = None
        if categories and isinstance(categories, list):
            for cat in categories:
                if isinstance(cat, dict) and cat.get('name') == 'Uncategorized':
                    default_category_id = cat.get('id')
                    break
            if default_category_id is None and len(categories) > 0:
                first_cat = categories[0]
                if isinstance(first_cat, dict):
                    default_category_id = first_cat.get('id')
        if default_category_id is None:
            default_category_id = 1  # Default to Uncategorized
        
        # Create the post info dictionary with proper type checking
        post_info = {
            'title': str(topic_name),
            'content': str(content),
            'excerpt': str(meta_desc[:150] + ('...' if len(meta_desc) > 150 else '')),
            'slug': str(base_slug),
            'status': 'draft',
            'categories': [default_category_id],
            'tags': post_tags if 'post_tags' in locals() else [],
            'yoast_meta': {
                'yoast_wpseo_metadesc': str(meta_desc),
                '_yoast_wpseo_metadesc': str(meta_desc),  # Additional field required by Yoast
                'yoast_wpseo_focuskw': str(topic_name),
                'yoast_wpseo_title': f"{topic_name} | Security Testing Guide",
                'yoast_wpseo_opengraph-description': str(meta_desc),
                'yoast_wpseo_twitter-description': str(meta_desc),
                'yoast_wpseo_meta-robots-noindex': '0',  # Ensure post is indexed
                'yoast_wpseo_meta-robots-nofollow': '0'  # Ensure links are followed
            },
            'meta': {
                'yoast_wpseo_metadesc': str(meta_desc),
                '_yoast_wpseo_metadesc': str(meta_desc),
                'yoast_wpseo_focuskw': str(topic_name),
                'yoast_wpseo_title': f"{topic_name} | Security Testing Guide",
                'yoast_wpseo_opengraph-description': str(meta_desc),
                'yoast_wpseo_twitter-description': str(meta_desc),
                'yoast_wpseo_meta-robots-noindex': '0',
                'yoast_wpseo_meta-robots-nofollow': '0'
            },
            'seo': {
                'metaDesc': str(meta_desc),
                'twitterDescription': str(meta_desc),
                'opengraphDescription': str(meta_desc),
                'title': f"{topic_name} | Security Testing Guide",
                'canonical': '',  # Let WordPress generate this
                'focuskw': str(topic_name),
                'metaRobotsNoindex': 'index',
                'metaRobotsNofollow': 'follow'
            }
        }
        
        # Generate featured image
        try:
            featured_image = generate_featured_image(topic_name, is_cve=topic_name.startswith('CVE:'))
            if featured_image:
                # Upload to WordPress first and get media ID
                media_id = upload_media_to_wordpress(
                    featured_image,
                    title=f"Featured Image for {topic_name}",
                    alt_text=topic_name
                )
                if media_id:
                    # Store the media ID, not the binary data
                    post_info['featured_media'] = media_id
                    print(f"Successfully generated and uploaded featured image with ID: {media_id}")
                else:
                    print("Failed to upload featured image to WordPress")
        except Exception as e:
            print(f"Error generating/uploading featured image: {e}")
            print(f"Error details: ", e.__class__.__name__)
        
        return post_info
        
    except Exception as e:
        print(f"Error in post_synthesis: {e}")
        print(f"Error details: ", e.__class__.__name__)
        return None

def post_completion(post_info, functions):
    # Enhanced SEO optimization
    title = post_info['title']
    description = post_info.get('excerpt', '')
    is_cve = title.startswith('CVE:')
    
    # Optimize title for SEO
    if is_cve:
        cvss_score = re.search(r'CVSS Score: ([\d.]+)', description)
        severity = re.search(r'\((.*?)\)', description)
        if cvss_score and severity:
            seo_title = f"{title}: {severity.group(1)} Severity Vulnerability (CVSS: {cvss_score.group(1)}) - CyberNow"
        else:
            seo_title = f"{title}: Security Vulnerability Analysis - CyberNow"
    else:
        seo_title = f"{title} | Latest Cybersecurity News - CyberNow"
    
    # Optimize meta description
    meta_desc = post_info.get('yoast_meta', {}).get('yoast_wpseo_metadesc', '')
    if not meta_desc:
        if is_cve:
            meta_desc = f"Detailed analysis of {title}. Learn about the vulnerability, its impact, CVSS score, and recommended security measures. Stay informed about cybersecurity threats."
        else:
            meta_desc = f"{description[:120]}... Read the latest cybersecurity news and analysis on CyberNow."
    
    # Optimize focus keywords
    focus_kw = post_info.get('yoast_meta', {}).get('yoast_wpseo_focuskw', '')
    if not focus_kw:
        if is_cve:
            focus_kw = f"{title} vulnerability"
        else:
            # Extract potential focus keyword from title
            focus_kw = ' '.join(title.split()[:3])
    
    # Update SEO metadata
    post_info['yoast_meta'] = {
        'yoast_wpseo_title': seo_title,
        'yoast_wpseo_metadesc': meta_desc,
        'yoast_wpseo_focuskw': focus_kw
    }
    
    # Call GPT for additional optimization
    instructions = "With this information, complete all of the missing fields in the JSON object (or optimize any that could be better for SEO) using the WordPressPostFieldCompletion function."
    json_str = json.dumps(post_info)
    model = os.getenv('FUNCTION_CALL_MODEL')
    response = function_call_gpt(json_str, instructions, model, functions)
    
    # Parse the response and update post_info
    if isinstance(response, dict):
        # Update post_info with new fields from response, preserving our SEO optimizations
        for key, value in response.items():
            if key not in ['content', 'yoast_meta']:  # Don't override content or our SEO optimizations
                post_info[key] = value
    else:
        print(f"Unexpected response format: {response}")
    
    return post_info


def sanitize_text(text):
    # Remove all spaces, newlines, and tabs from the text and make all characters lowercase
    return re.sub(r'\s', '', text).lower()

def generate_featured_image(title, is_cve=False):
    """Generate a featured image for the post."""
    try:
        # Create a new image with a dark background
        width = 1200
        height = 630
        background_color = '#1a1a1a' if is_cve else '#2c3e50'
        img = Image.new('RGB', (width, height), color=background_color)
        draw = ImageDraw.Draw(img)
        
        # Try to load custom fonts, fall back to default if not available
        try:
            # Look for fonts in common system locations
            font_locations = [
                '/System/Library/Fonts/Helvetica.ttc',  # macOS
                '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',  # Linux
                'C:\\Windows\\Fonts\\Arial.ttf'  # Windows
            ]
            
            title_font = None
            for font_path in font_locations:
                if os.path.exists(font_path):
                    title_font = ImageFont.truetype(font_path, 60)
                    break
                    
            if not title_font:
                title_font = ImageFont.load_default()
                print("Warning: Using default font as no system fonts were found")
        except Exception as e:
            print(f"Font loading error: {e}")
            title_font = ImageFont.load_default()
        
        # Create gradient overlay
        for y in range(height):
            # Calculate gradient color
            if is_cve:
                # Red gradient for CVE posts
                alpha = int(255 * (1 - y/height))
                color = (231, 76, 60, alpha)  # Red shade
            else:
                # Blue gradient for regular posts
                alpha = int(255 * (1 - y/height))
                color = (41, 128, 185, alpha)  # Blue shade
            draw.line([(0, y), (width, y)], fill=color)
        
        # Add a subtle pattern overlay for visual interest
        pattern_size = 10
        for x in range(0, width, pattern_size):
            for y in range(0, height, pattern_size):
                if (x + y) % (pattern_size * 2) == 0:
                    draw.point((x, y), fill='#ffffff')
        
        # Calculate text position and size
        if is_cve:
            # For CVE posts, split into CVE ID and description
            cve_id = title.split(':')[1].strip()
            
            # Draw CVE ID
            font_size = 80
            title_font = title_font.font_variant(size=font_size)
            text_width = draw.textlength(cve_id, font=title_font)
            
            while text_width > width - 100 and font_size > 40:
                font_size -= 10
                title_font = title_font.font_variant(size=font_size)
                text_width = draw.textlength(cve_id, font=title_font)
            
            x = (width - text_width) // 2
            y = height // 3
            
            # Add a semi-transparent background box for better readability
            padding = 20
            box_coords = [
                x - padding,
                y - padding,
                x + text_width + padding,
                y + font_size + padding
            ]
            draw.rectangle(box_coords, fill='#00000066')
            
            # Draw the text
            draw.text((x, y), cve_id, font=title_font, fill='#ffffff')
            
            # Add "Security Advisory" text
            advisory_font = title_font.font_variant(size=40)
            advisory_text = "Security Advisory"
            text_width = draw.textlength(advisory_text, font=advisory_font)
            x = (width - text_width) // 2
            draw.text((x, y + font_size + 40), advisory_text, font=advisory_font, fill='#e74c3c')
        else:
            # For regular posts, wrap the title
            font_size = 60
            title_font = title_font.font_variant(size=font_size)
            
            # Calculate maximum width for text
            max_width = width - 100
            
            # Wrap text and adjust font size if needed
            words = title.split()
            lines = []
            current_line = []
            
            while words:
                current_line.append(words[0])
                test_line = ' '.join(current_line)
                text_width = draw.textlength(test_line, font=title_font)
                
                if text_width > max_width:
                    if len(current_line) == 1:
                        # Single word is too long, need to reduce font size
                        font_size -= 5
                        title_font = title_font.font_variant(size=font_size)
                        if font_size < 30:  # Minimum readable size
                            break
                        continue
                    else:
                        # Complete the previous line
                        current_line.pop()
                        lines.append(' '.join(current_line))
                        current_line = []
                        continue
                
                words.pop(0)
                if not words:
                    lines.append(' '.join(current_line))
            
            # Calculate total height of text block
            line_height = font_size + 10
            total_height = len(lines) * line_height
            
            # Draw each line
            y = (height - total_height) // 2
            for line in lines:
                text_width = draw.textlength(line, font=title_font)
                x = (width - text_width) // 2
                
                # Add text shadow for better readability
                shadow_offset = 2
                draw.text((x + shadow_offset, y + shadow_offset), line, font=title_font, fill='#00000088')
                draw.text((x, y), line, font=title_font, fill='#ffffff')
                y += line_height
        
        # Add CyberNow watermark
        watermark_font = title_font.font_variant(size=30)
        watermark_text = "CyberNow.info"
        text_width = draw.textlength(watermark_text, font=watermark_font)
        
        # Add shadow to watermark
        shadow_offset = 1
        draw.text(
            (width - text_width - 19, height - 49),
            watermark_text,
            font=watermark_font,
            fill='#00000088'
        )
        draw.text(
            (width - text_width - 20, height - 50),
            watermark_text,
            font=watermark_font,
            fill='#ffffff'
        )
        
        # Convert to bytes
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG', optimize=True, quality=95)
        img_byte_arr.seek(0)
        
        return img_byte_arr.getvalue()
        
    except Exception as e:
        print(f"Error generating featured image: {e}")
        import traceback
        print(traceback.format_exc())
        return None

