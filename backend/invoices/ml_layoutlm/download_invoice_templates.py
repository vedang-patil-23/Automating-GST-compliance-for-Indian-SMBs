import os
import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import time
import random
import urllib.parse

def download_invoice_templates(num_templates=5, output_dir="Invoice Templates"):
    """
    Download sample invoice templates from free stock photo websites.
    
    Args:
        num_templates (int): Number of templates to download
        output_dir (str): Directory to save the templates
    """
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")

    # List of free stock photo websites to try
    websites = [
        "https://www.pexels.com/search/invoice%20template/",
        "https://pixabay.com/images/search/invoice%20template/",
        "https://unsplash.com/s/photos/invoice-template"
    ]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    downloaded_count = 0
    for website in websites:
        if downloaded_count >= num_templates:
            break

        try:
            print(f"\nSearching on {website}...")
            response = requests.get(website, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"Failed to access {website}: HTTP {response.status_code}")
                continue

            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find image elements (adjust selectors based on website)
            if 'pexels.com' in website:
                img_elements = soup.select('img[src*="images.pexels.com"]')
            elif 'pixabay.com' in website:
                img_elements = soup.select('img[src*="cdn.pixabay.com"]')
            elif 'unsplash.com' in website:
                img_elements = soup.select('img[src*="images.unsplash.com"]')
            else:
                img_elements = soup.select('img')

            for img in img_elements:
                if downloaded_count >= num_templates:
                    break

                try:
                    # Get image URL
                    img_url = img.get('src')
                    if not img_url:
                        continue

                    # Make sure URL is absolute
                    if not img_url.startswith(('http://', 'https://')):
                        img_url = urllib.parse.urljoin(website, img_url)

                    # Download image
                    img_response = requests.get(img_url, headers=headers, timeout=10)
                    if img_response.status_code == 200:
                        # Open image with PIL to verify it's valid
                        img = Image.open(BytesIO(img_response.content))
                        
                        # Save image
                        output_path = os.path.join(output_dir, f'invoice_template_{downloaded_count + 1}.png')
                        img.save(output_path, 'PNG')
                        print(f"Downloaded template {downloaded_count + 1}: {output_path}")
                        
                        downloaded_count += 1
                        
                        # Add a small delay to avoid overwhelming the server
                        time.sleep(random.uniform(1, 2))
                    else:
                        print(f"Failed to download image: HTTP {img_response.status_code}")

                except Exception as e:
                    print(f"Error processing image: {str(e)}")
                    continue

        except Exception as e:
            print(f"Error accessing {website}: {str(e)}")
            continue

    print(f"\nDownloaded {downloaded_count} invoice templates to {output_dir}")

if __name__ == "__main__":
    # You can modify these parameters
    NUM_TEMPLATES = 5
    OUTPUT_DIR = "Invoice Templates"
    
    print("Starting invoice template download...")
    download_invoice_templates(NUM_TEMPLATES, OUTPUT_DIR) 