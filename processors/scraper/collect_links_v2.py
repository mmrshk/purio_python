import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote, urlencode
import json
import time
import random
import os
import re
import base64
import pandas as pd

# Link example for Batoane ciocolata: https://www.auchan.ro/bacanie/dulciuri/batoane-ciocolata/c
# https://www.auchan.ro/_v/segment/graphql/v1?workspace=master&maxAge=short&appsEtag=remove&domain=store&locale=ro-RO&__bindingId=4355a719-f08a-43c0-b383-6e0289ed396b&operationName=productSearch&variables=%7B%7D&extensions=%7B%22persistedQuery%22%3A%7B%22version%22%3A1%2C%22sha256Hash%22%3A%22e19f45bc82c1b7a801ee75732fa941c938dd139a6ad281cd87d2ebe97b0e41e6%22%2C%22sender%22%3A%22auchan.out-of-stock-similar-products%400.x%22%2C%22provider%22%3A%22vtex.search-graphql%400.x%22%7D%2C%22variables%22%3A%22eyJwcm9kdWN0TmFtZSI6IkJhdG9uIGRlIGNpb2NvbGF0YSBjdSBsYXB0ZSBLaXRLYXQgQ2h1bmt5LCA0MGciLCJjYXRlZ29yeUlkIjoiMzA2MDEwMCIsImNhdGVnb3J5TGV2ZWwiOiJjYXRlZ29yeS0zIiwiZnJvbSI6MCwidG8iOjl9%22%7D

# Search and put category ID on line 120
# To find the category ID, open desired category, open network, search for:
# route":{"domain":"store","id":"store.search#subcategory","params":{"id":

class LinkCollectorV2:
    def __init__(self, category_id="3060100"):
        self.base_url = "https://www.auchan.ro"
        self.graphql_url = "https://www.auchan.ro/_v/segment/graphql/v1"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json'
        }
        self.links = {}
        self.all_links = {}
        self.save_dir = None
        self.products_data = []
        self.category_id = category_id

    def set_save_dir(self, category_url):
        """Set the directory to save links based on category_url"""
        # Extract last two non-empty parts before '/c'
        parts = [p for p in category_url.split('/') if p]
        if 'c' in parts:
            c_index = parts.index('c')
            if c_index >= 2:
                category1 = parts[c_index - 2]
                category2 = parts[c_index - 1]
                self.save_dir = os.path.join('auchan', category1, category2)
                os.makedirs(self.save_dir, exist_ok=True)
            else:
                raise ValueError("Category URL does not have enough parts before '/c'")
        else:
            raise ValueError("Category URL does not contain '/c'")

    def extract_product_data(self, product):
        """Extract relevant data from a product"""
        try:
            # Basic product info
            product_data = {
                'name': product.get('productName', ''),
                'url': f"{self.base_url}{product.get('link', '')}",
                'brand': product.get('brand', ''),
                'description': product.get('description', ''),
                'category_id': product.get('categoryId', ''),
                'ean': '',
                'price': None,
                'list_price': None,
                'ingredients': '',
                'nutritional_info': {},
                'external_id': ''
            }

            # Get EAN and price from items
            if product.get('items'):
                item = product['items'][0]
                product_data['ean'] = item.get('ean', '')
                
                # Get price from sellers
                if item.get('sellers'):
                    seller = item['sellers'][0]
                    if seller.get('commertialOffer'):
                        offer = seller['commertialOffer']
                        product_data['price'] = offer.get('Price')
                        product_data['list_price'] = offer.get('ListPrice')

            # Extract ingredients and nutritional info from specifications
            if product.get('specificationGroups'):
                for group in product['specificationGroups']:
                    if group.get('name') == 'Informatii Generale':
                        for spec in group.get('specifications', []):
                            if spec.get('name') == 'Ingrediente':
                                product_data['ingredients'] = spec.get('values', [''])[0]
                    
                    elif group.get('name') == 'Informatii nutritionale':
                        for spec in group.get('specifications', []):
                            name = spec.get('name', '')
                            value = spec.get('values', [''])[0]
                            product_data['nutritional_info'][name] = value

            # Extract external_id (Cod produs)
            product_id = product.get('productId', '')
            product_data['external_id'] = product_id

            return product_data
        except Exception as e:
            print(f"Error extracting product data: {e}")
            return None

    def get_category_products(self, category_url):
        """Get all product URLs from a category using GraphQL API"""
        try:
            unique_products = {}
            all_products = {}
            page = 0
            page_size = 9  # Changed to 9 to match the API's limit
            max_retries = 3
            empty_pages = 0
            max_empty_pages = 3
            
            print("Starting to collect products...")
            
            while True:
                print(f"\nProcessing page {page + 1}")
                
                # Extract category path from URL
                category_path = category_url.split('/')[-4:-1]  # Get last three parts before 'c'
                
                # Convert category name to proper format (e.g., "batoane-ciocolata" -> "Batoane ciocolata")
                category_name = category_path[-1].replace('-', ' ').title()
                
                # Create variables object for the extensions
                variables = {
                    "productName": category_name,  # Use the formatted category name
                    "categoryId": self.category_id,  # Use the instance variable
                    "categoryLevel": "category-3",
                    "from": page * page_size,
                    "to": (page + 1) * page_size - 1  # This will give us 0-8, 9-17, etc.
                }

                # Convert variables to base64
                variables_json = json.dumps(variables)
                variables_b64 = base64.b64encode(variables_json.encode()).decode()

                # Create extensions object with new query hash
                extensions = {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "e19f45bc82c1b7a801ee75732fa941c938dd139a6ad281cd87d2ebe97b0e41e6",
                        "sender": "auchan.out-of-stock-similar-products@0.x",
                        "provider": "vtex.search-graphql@0.x"
                    },
                    "variables": variables_b64
                }

                # Convert extensions to URL-encoded string
                extensions_str = quote(json.dumps(extensions))

                # Construct the final URL with proper encoding
                base_params = {
                    "workspace": "master",
                    "maxAge": "short",
                    "appsEtag": "remove",
                    "domain": "store",
                    "locale": "ro-RO",
                    "__bindingId": "4355a719-f08a-43c0-b383-6e0289ed396b",
                    "operationName": "productSearch",
                    "variables": "{}"
                }
                
                # Construct URL exactly like the working example
                url = f"{self.graphql_url}?{urlencode(base_params)}&extensions={extensions_str}"
                
                print(f"Requesting URL: {url}")  # Debug print
                print(f"Decoded variables: {variables}")  # Debug print of variables
                print(f"Base64 variables: {variables_b64}")  # Debug print of base64 variables
                
                # Add retry logic
                for retry in range(max_retries):
                    try:
                        response = requests.get(url, headers=self.headers)
                        response.raise_for_status()
                        
                        data = response.json()
                        if not data or 'data' not in data:
                            print(f"Invalid response format: {data}")
                            if retry == max_retries - 1:
                                return all_products, unique_products
                            continue
                            
                        products = data.get('data', {}).get('productSearch', {}).get('products', [])
                        
                        if not products:
                            empty_pages += 1
                            print(f"No products found on this page (empty page {empty_pages}/{max_empty_pages})")
                            if empty_pages >= max_empty_pages:
                                print("Reached maximum consecutive empty pages, stopping collection")
                                return all_products, unique_products
                            break
                        
                        empty_pages = 0  # Reset empty pages counter
                        new_products_found = 0
                        
                        for product in products:
                            product_url = f"{self.base_url}{product.get('link', '')}"
                            product_name = product.get('productName', 'Unknown Product')
                            
                            # Add to all products
                            all_products[product_url] = product_name
                            
                            # Add to unique products if not already present
                            if product_url not in unique_products:
                                unique_products[product_url] = product_name
                                new_products_found += 1
                                print(f"Found new product: {product_name} - {product_url}")
                                
                                # Extract and store detailed product data
                                product_data = self.extract_product_data(product)
                                if product_data:
                                    self.products_data.append(product_data)
                        
                        print(f"\nFound {new_products_found} new unique products on this page")
                        print(f"Total unique products collected so far: {len(unique_products)}")
                        print(f"Total products collected (including duplicates): {len(all_products)}")
                        
                        # Add delay between pages
                        time.sleep(random.uniform(2, 3))
                        
                        page += 1
                        break  # Break retry loop if successful
                        
                    except Exception as e:
                        print(f"Error on retry {retry + 1}: {str(e)}")
                        if retry == max_retries - 1:
                            raise e
                        print(f"Retry {retry + 1}/{max_retries}")
                        time.sleep(random.uniform(2, 4))
            
        except Exception as e:
            print(f"Error getting category products: {e}")
            return all_products, unique_products  # Return what we have so far

    def save_links(self):
        """Save collected links to CSV files in the category directory"""
        if not self.save_dir:
            raise ValueError("save_dir must be set before saving links")
            
        # Save basic links
        csv_path = os.path.join(self.save_dir, 'product_links.csv')
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write("Product Name,Product URL\n")
            for url, name in self.links.items():
                safe_name = name.replace('"', '""')
                f.write(f'"{safe_name}","{url}"\n')
        print(f"Saved {len(self.links)} unique products to {csv_path}")
        
        # Save detailed product data
        if self.products_data:
            detailed_csv_path = os.path.join(self.save_dir, 'product_details.csv')
            df = pd.DataFrame(self.products_data)
            df.to_csv(detailed_csv_path, index=False, encoding='utf-8')
            print(f"Saved detailed product data to {detailed_csv_path}")

    def collect_links(self, category_url):
        """Collect all product links from a category"""
        print(f"Collecting links from: {category_url}")
        self.set_save_dir(category_url)
        self.links = {}
        self.all_links = {}
        self.products_data = []
        print("Cleared existing product links")
        
        # Get products and update both links dictionaries
        all_products, unique_products = self.get_category_products(category_url)
        self.links.update(unique_products)
        self.all_links.update(all_products)
        
        print(f"Total unique products collected: {len(self.links)}")
        print(f"Total products collected (including duplicates): {len(self.all_links)}")
        
        # Save the collected data
        self.save_links()
        
        # Add a small delay before finishing
        time.sleep(random.uniform(1, 3))
        
        return self.links  # Return the collected links

def main():
    # Initialize collector with category ID
    category_id = "3060100"  # Example category ID
    collector = LinkCollectorV2(category_id=category_id)
    
    # Category URL to collect links from
    category_url = "https://www.auchan.ro/lactate-carne-mezeluri---peste/lactate/iaurt/c"
    
    # Collect links
    collector.collect_links(category_url)

if __name__ == "__main__":
    main() 