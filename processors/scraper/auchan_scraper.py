import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
from urllib.parse import urljoin
import os
import re
import json
from processors.helpers.fix_doubled_names import fix_doubled_name

class AuchanScraper:
    def __init__(self):
        self.base_url = "https://www.auchan.ro"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.products = []
        self.images_dir = None
        self.links_file = None
        self.category_dir = None  # New: store category directory

    def set_category_dir(self):
        """Set the category directory based on the links file path"""
        if self.links_file:
            # Split the path into parts
            path_parts = self.links_file.split('/')
            
            # Find the indices of relevant parts (between 'auchan' and 'product_links.csv')
            if 'auchan' in path_parts and 'product_links.csv' in path_parts:
                auchan_index = path_parts.index('auchan')
                file_index = path_parts.index('product_links.csv')
                
                # Get all category parts between 'auchan' and 'product_links.csv'
                category_parts = path_parts[auchan_index:file_index]
                
                # Join all parts to create the full category directory
                self.category_dir = os.path.join(*category_parts)
                
                if not os.path.exists(self.category_dir):
                    os.makedirs(self.category_dir)
            else:
                raise ValueError("Invalid links file path structure")
        else:
            raise ValueError("links_file must be set before setting category_dir")

    def set_images_dir(self):
        """Set the images directory inside the category directory"""
        if not self.category_dir:
            self.set_category_dir()
        self.images_dir = os.path.join(self.category_dir, 'images')
        if not os.path.exists(self.images_dir):
            os.makedirs(self.images_dir)
            print(f"Images will be saved to: {self.images_dir}")

    def create_product_image_dir(self, product_name):
        """Create a directory for a specific product's images"""
        safe_name = self.sanitize_filename(product_name)
        product_dir = os.path.join(self.images_dir, safe_name)
        if not os.path.exists(product_dir):
            os.makedirs(product_dir)
        return product_dir

    def sanitize_filename(self, filename):
        """Remove invalid characters from filename and limit length"""
        # Remove invalid characters
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Limit filename length to 100 characters
        if len(safe_name) > 100:
            safe_name = safe_name[:100]
        return safe_name

    def download_image(self, image_url, product_name, image_index=0):
        """Download and save product image"""
        try:
            if not image_url or not self.images_dir:
                return None
            
            # Clean and validate the image URL
            if not image_url.startswith('http'):
                if image_url.startswith('//'):
                    image_url = 'https:' + image_url
                elif image_url.startswith('/'):
                    image_url = 'https://www.auchan.ro' + image_url
                else:
                    print(f"Invalid image URL format: {image_url}")
                    return None
            
            # Create product-specific directory
            product_dir = self.create_product_image_dir(product_name)
            
            # Get file extension from URL or default to jpg
            try:
                file_extension = image_url.split('.')[-1].split('?')[0].lower()
                if file_extension not in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                    file_extension = 'jpg'
            except:
                file_extension = 'jpg'
            
            # Add index to filename to handle multiple images
            filename = f"image_{image_index}.{file_extension}"
            filepath = os.path.join(product_dir, filename)
            
            # Download image with timeout
            response = requests.get(image_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            # Save image
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            print(f"Image saved successfully: {filename}")
            return filepath
        except requests.exceptions.RequestException as e:
            print(f"Error downloading image for {product_name}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error downloading image for {product_name}: {e}")
            return None

    def get_product_images(self, soup):
        """Extract all product images from the carousel"""
        image_urls = set()  # Use a set to automatically deduplicate URLs
        
        # Find only the main carousel images (ignore thumbnails)
        main_carousel = soup.find('div', class_='vtex-store-components-3-x-carouselGaleryCursor')
        if main_carousel:
            # Find all image elements in the main carousel
            image_elements = main_carousel.find_all('img', class_='vtex-store-components-3-x-productImageTag')
            
            for img in image_elements:
                if 'src' in img.attrs:
                    # Get the highest resolution image URL
                    srcset = img.get('srcset', '')
                    if srcset:
                        # Parse srcset to get the highest resolution image
                        urls = [url.strip().split(' ')[0] for url in srcset.split(',')]
                        if urls:
                            # Get the last (highest resolution) URL and remove any query parameters
                            base_url = urls[-1].split('?')[0]
                            image_urls.add(base_url)
                    else:
                        # Remove any query parameters from the src URL
                        base_url = img['src'].split('?')[0]
                        image_urls.add(base_url)
        
        # Convert set back to list and sort for consistent ordering
        return sorted(list(image_urls))

    def get_category_products(self, category_url):
        """Get all product URLs from a category page"""
        try:
            response = requests.get(category_url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Find all product links
            product_links = []
            for product in soup.find_all('div', class_='product-item'):
                link = product.find('a', href=True)
                if link:
                    product_links.append(urljoin(self.base_url, link['href']))
            
            return product_links
        except Exception as e:
            print(f"Error getting category products: {e}")
            return []

    def get_product_details(self, product_url):
        """Get detailed information about a specific product"""
        try:
            response = requests.get(product_url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Extract product information
            product_data = {
                'name': '',
                'description': '',
                'ingredients': '',
                'price': '',
                'url': product_url,
                'image_urls': [],
                'image_paths': [],
                'specifications': {},
                'nutritional_info': {},
                'category': self.category_dir if self.category_dir else '',
                'external_id': ''
            }
            
            # Get product name
            name_element = soup.find('h1', class_='vtex-store-components-3-x-productNameContainer')
            if name_element:
                product_data['name'] = fix_doubled_name(name_element.text.strip())
            
            # Get product price
            price_element = soup.find('span', class_='vtex-product-price-1-x-currencyInteger')
            if price_element:
                price_decimal = soup.find('span', class_='vtex-product-price-1-x-currencyDecimal')
                price_fraction = soup.find('span', class_='vtex-product-price-1-x-currencyFraction')
                price = price_element.text.strip()
                if price_decimal:
                    price += price_decimal.text.strip()
                if price_fraction:
                    price += price_fraction.text.strip()
                product_data['price'] = price + ' lei'
            
            # Get all product images
            product_data['image_urls'] = self.get_product_images(soup)
            
            # Download all images
            for i, image_url in enumerate(product_data['image_urls']):
                image_path = self.download_image(image_url, product_data['name'], i)
                if image_path:
                    product_data['image_paths'].append(image_path)
            
            # Get product description
            desc_element = soup.find('div', class_='vtex-store-components-3-x-productDescriptionText')
            if desc_element:
                product_data['description'] = desc_element.text.strip()
            
            # Get specifications and nutritional info
            spec_rows = soup.find_all('div', class_='vtex-flex-layout-0-x-flexRow--specificationRow')
            for row in spec_rows:
                name_element = row.find('span', class_='vtex-product-specifications-1-x-specificationName')
                value_element = row.find('span', class_='vtex-product-specifications-1-x-specificationValue')
                if name_element and value_element:
                    spec_name = name_element.text.strip()
                    spec_value = value_element.text.strip()
            
                    # Check if it's nutritional information
                    if spec_name in ['Kcal pe 100g sau 100ml', 'Grasimi (g sau ml)', 'Proteine (g sau ml)',
                                   'Glucide (g sau ml)', 'Zaharuri (g sau ml)']:
                        product_data['nutritional_info'][spec_name] = spec_value
                    else:
                        product_data['specifications'][spec_name] = spec_value
                    
                    # Special case for ingredients
                    if spec_name == 'Ingrediente':
                        product_data['ingredients'] = spec_value
            
            # Extract external_id (Cod produs) from the product details section
            try:
                prod_id_container = soup.find('span', class_='vtex-product-identifier-0-x-product-identifier--productId')
                if prod_id_container:
                    value_span = prod_id_container.find('span', class_='vtex-product-identifier-0-x-product-identifier__value')
                    if value_span:
                        product_data['external_id'] = value_span.text.strip()
            except Exception as e:
                print(f"Error extracting external_id: {e}")
            
            # Print the scraped data for verification
            print(f"External ID: {product_data['external_id']}")
            print(f"Name: {product_data['name']}")
            print(f"Price: {product_data['price']}")
            print(f"Number of images found: {len(product_data['image_paths'])}")
            if product_data['ingredients']:
                print(f"Ingredients: {product_data['ingredients']}")
            if product_data['nutritional_info']:
                print("Nutritional Info:")
                for key, value in product_data['nutritional_info'].items():
                    print(f"  {key}: {value}")
            
            return product_data
        except Exception as e:
            print(f"Error getting product details: {e}")
            return None

    def scrape_category(self, category_url, limit=3):
        """Scrape products from a category with a limit"""
        product_links = self.get_category_products(category_url)
        print(f"Found {len(product_links)} products in category")
        print(f"Will scrape first {limit} products for testing")
        
        for i, link in enumerate(product_links[:limit]):
            print(f"\nScraping product {i+1}/{limit}")
            product_data = self.get_product_details(link)
            if product_data:
                self.products.append(product_data)
                print(f"Successfully scraped: {product_data['name']}")
                if product_data['image_paths']:
                    print(f"Images saved to: {product_data['image_paths']}")
            
            # Add a random delay to be respectful to the server
            time.sleep(random.uniform(1, 3))
        
        return self.products

    def scrape_products(self, limit=None):
        """Scrape products using the collected links"""
        if not self.links_file:
            print("No links file specified")
            return []
        
        # Set up images directory
        self.set_images_dir()
        
        try:
            # Read the CSV file properly
            df = pd.read_csv(self.links_file)
            if 'Product URL' in df.columns:
                links = df['Product URL'].dropna().tolist()
            else:
                print("CSV does not contain 'Product URL' column")
                return []
            
            total_products = len(links)
            if limit:
                print(f"Found {total_products} products, will scrape {limit} products")
                links = links[:limit]
            else:
                print(f"Found {total_products} products to scrape")
            
            for i, link in enumerate(links, 1):
                # Clean the URL if it has extra quotes or spaces
                link = link.strip().strip('"')
                if not link:
                    continue
                    
                print(f"\nScraping product {i}/{len(links)}: {link}")
                try:
                    product_data = self.get_product_details(link)
                    if product_data:
                        self.products.append(product_data)
                        print(f"Successfully scraped: {product_data['name']}")
                        if product_data['image_paths']:
                            print(f"Images saved to: {product_data['image_paths']}")
                    
                    # Add a small delay between requests
                    time.sleep(random.uniform(1, 2))
                except Exception as e:
                    print(f"Error scraping product {link}: {e}")
                    continue
            
            return self.products
        except Exception as e:
            print(f"Error reading links file: {e}")
            return []

    def save_to_csv(self, filename=None):
        """Save scraped products to a CSV file inside the category directory"""
        if not self.products:
            print("No products to save")
            return
        if not self.category_dir:
            self.set_category_dir()
        if filename is None:
            # Default CSV filename is the category name
            category_name = os.path.basename(self.category_dir)
            filename = os.path.join(self.category_dir, f"{category_name}.csv")
        else:
            filename = os.path.join(self.category_dir, os.path.basename(filename))
        df = pd.DataFrame(self.products)
        df.to_csv(filename, index=False, encoding='utf-8')
        print(f"Saved {len(self.products)} products to {filename}")

def main():
    # Initialize scraper
    scraper = AuchanScraper()
    
    # Use the specific JSON file for branza si telemea
    scraper.links_file = 'auchan/lactate/lapte/product_links.csv'
    
    # Set up category and images directories
    scraper.set_category_dir()
    scraper.set_images_dir()
    
    # Scrape products using the collected links with a limit
    products = scraper.scrape_products(limit=100)  # Set limit to 10 products
    
    # Save results with a specific filename (optional, will be placed in category folder)
    scraper.save_to_csv('lapte.csv')

if __name__ == "__main__":
    main()