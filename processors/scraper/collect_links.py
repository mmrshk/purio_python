import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import json
import time
import random
import os
import re
import base64

class LinkCollector:
    def __init__(self):
        self.base_url = "https://www.auchan.ro"
        self.graphql_url = "https://www.auchan.ro/_v/segment/graphql/v1"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json'
        }
        self.links = {}
        self.all_links = {}
        self.save_dir = None  # Directory to save links

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

    def get_category_products(self, category_url):
        """Get all product URLs from a category using GraphQL API"""
        try:
            unique_products = {}
            page = 0
            page_size = 24
            max_retries = 3
            empty_pages = 0
            max_empty_pages = 3
            
            print("Starting to collect products...")
            
            while True:  # Remove max_pages limit
                print(f"\nProcessing page {page + 1}")
                
                # Extract category path from URL
                category_path = category_url.split('/')[-4:-1]  # Get last three parts before 'c'
                category_query = '/'.join(category_path)
                
                # Create selectedFacets from category path
                selected_facets = []
                for i, category in enumerate(category_path, 1):
                    selected_facets.append({
                        "key": f"category-{i}",
                        "value": category
                    })

                # Create variables object
                variables = {
                    "hideUnavailableItems": False,
                    "skuFilter": "ALL_AVAILABLE",
                    "simulationBehavior": "default",
                    "installmentCriteria": "MAX_WITHOUT_INTEREST",
                    "productOriginVtex": False,
                    "map": "category-1,category-2,category-3",
                    "query": category_query,
                    "orderBy": "OrderByBestDiscountDESC",
                    "from": page * page_size,
                    "to": (page + 1) * page_size - 1,
                    "selectedFacets": selected_facets,
                    "facetsBehavior": "Dynamic",
                    "categoryTreeBehavior": "default",
                    "withFacets": False,
                    "advertisementOptions": {
                        "showSponsored": True,
                        "sponsoredCount": 3,
                        "advertisementPlacement": "top_search",
                        "repeatSponsoredProducts": True
                    }
                }

                # Convert variables to base64
                variables_json = json.dumps(variables)
                variables_b64 = base64.b64encode(variables_json.encode()).decode()

                extensions = {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "9177ba6f883473505dc99fcf2b679a6e270af6320a157f0798b92efeab98d5d3",
                        "sender": "vtex.store-resources@0.x",
                        "provider": "vtex.search-graphql@0.x"
                    },
                    "variables": variables_b64
                }

                # Convert extensions to URL-encoded string
                extensions_str = quote(json.dumps(extensions))

                # Construct the final URL
                base_params = {
                    "workspace": "master",
                    "maxAge": "short",
                    "appsEtag": "remove",
                    "domain": "store",
                    "locale": "ro-RO",
                    "__bindingId": "4355a719-f08a-43c0-b383-6e0289ed396b",
                    "operationName": "productSearchV3",
                    "variables": "{}"
                }
                
                url = f"{self.graphql_url}?{'&'.join(f'{k}={v}' for k, v in base_params.items())}&extensions={extensions_str}"
                
                # Add retry logic
                for retry in range(max_retries):
                    try:
                        response = requests.get(url, headers=self.headers)
                        response.raise_for_status()
                        
                        data = response.json()
                        products = data.get('data', {}).get('productSearch', {}).get('products', [])
                        
                        if not products:
                            empty_pages += 1
                            print(f"No products found on this page (empty page {empty_pages}/{max_empty_pages})")
                            if empty_pages >= max_empty_pages:
                                print("Reached maximum consecutive empty pages, stopping collection")
                                return unique_products, unique_products
                            break
                        
                        empty_pages = 0  # Reset empty pages counter
                        new_products_found = 0
                        
                        for product in products:
                            product_url = f"{self.base_url}{product.get('link', '')}"
                            product_name = product.get('productName', 'Unknown Product')
                            
                            if product_url not in unique_products:
                                unique_products[product_url] = product_name
                                new_products_found += 1
                                print(f"Found new product: {product_name} - {product_url}")
                        
                        print(f"\nFound {new_products_found} new unique products on this page")
                        print(f"Total unique products collected so far: {len(unique_products)}")
                        
                        # Add delay between pages
                        time.sleep(random.uniform(2, 3))
                        
                        page += 1
                        break  # Break retry loop if successful
                        
                    except Exception as e:
                        if retry == max_retries - 1:
                            raise e
                        print(f"Retry {retry + 1}/{max_retries}")
                        time.sleep(random.uniform(2, 4))
            
        except Exception as e:
            print(f"Error getting category products: {e}")
            return {}, {}

    def save_links(self):
        """Save collected links to a CSV file in the category directory"""
        if not self.save_dir:
            raise ValueError("save_dir must be set before saving links")
        csv_path = os.path.join(self.save_dir, 'product_links.csv')
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write("Product Name,Product URL\n")
            for url, name in self.links.items():
                # Escape quotes in name
                safe_name = name.replace('"', '""')
                f.write(f'"{safe_name}","{url}"\n')
        print(f"Saved {len(self.links)} unique products to {csv_path}")

    def load_links(self):
        """Load previously collected links from JSON files"""
        try:
            # Load unique links
            if os.path.exists(self.links_file):
                with open(self.links_file, 'r', encoding='utf-8') as f:
                    self.links = json.load(f)
                print(f"Loaded {len(self.links)} unique products from {self.links_file}")
            else:
                print("No existing unique products file found")
            
            # Load all links
            if os.path.exists(self.all_links_file):
                with open(self.all_links_file, 'r', encoding='utf-8') as f:
                    self.all_links = json.load(f)
                print(f"Loaded {len(self.all_links)} total products from {self.all_links_file}")
            else:
                print("No existing all products file found")
        except Exception as e:
            print(f"Error loading links: {e}")

    def collect_links(self, category_url):
        """Collect all product links from a category"""
        print(f"Collecting links from: {category_url}")
        self.set_save_dir(category_url)
        self.links = {}
        self.all_links = {}
        print("Cleared existing product links")
        all_products, unique_products = self.get_category_products(category_url)
        self.links.update(unique_products)
        self.all_links.update(all_products)
        print(f"Total unique products collected: {len(self.links)}")
        print(f"Total products collected (including duplicates): {len(self.all_links)}")
        self.save_links()
        time.sleep(random.uniform(1, 3))

def main():
    # Initialize collector
    collector = LinkCollector()
    
    # Load existing links if any
    collector.load_links()
    
    # Category URL to collect links from
    # category_url = "https://www.auchan.ro/lactate-carne-mezeluri---peste/lactate/branza-si-telemea/c"
    # category_url = "https://www.auchan.ro/lactate-carne-mezeluri---peste/pescarie/peste-proaspat/c"
    category_url = "https://www.auchan.ro/lactate-carne-mezeluri---peste/lactate/lapte/c"
    
    # Collect links
    collector.collect_links(category_url)

if __name__ == "__main__":
    main()