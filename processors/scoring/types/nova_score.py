import requests

class NovaScoreCalculator:
    NOVA_MAP = {
        1: 100,  # Unprocessed or minimally processed foods
        2: 80,   # Processed culinary ingredients
        3: 50,   # Processed foods
        4: 20    # Ultra-processed foods
    }
    
    def fetch_nova_from_off(self, ean=None, product_name=None):
        """Fetch NOVA score from Open Food Facts API."""
        # Try by barcode first
        if ean:
            url = f"https://world.openfoodfacts.org/api/v0/product/{ean}.json"
            try:
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    product = data.get('product', {})
                    nova_group = product.get('nova-group')
                    if nova_group:
                        return int(nova_group)
            except Exception as e:
                print(f"Error fetching NOVA by EAN: {e}")
        
        # Fallback: search by product name
        if product_name:
            url = "https://world.openfoodfacts.org/cgi/search.pl"
            params = {
                "search_terms": product_name,
                "search_simple": 1,
                "action": "process",
                "json": 1
            }
            try:
                resp = requests.get(url, params=params, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    products = data.get('products', [])
                    if products:
                        nova_group = products[0].get('nova-group')
                        if nova_group:
                            return int(nova_group)
            except Exception as e:
                print(f"Error fetching NOVA by name: {e}")
        return None
    
    def calculate_local_nova(self, product_data):
        """Calculate NOVA score locally based on product data."""
        # Since nova_group is not available in our product data,
        # return None to indicate no Nova data available
        return None
    
    def calculate(self, product_data):
        """Calculate NOVA score, trying API first, then falling back to local calculation."""
        ean = product_data.get('barcode')
        name = product_data.get('name')
        
        # Try to get NOVA from Open Food Facts API
        nova_group = self.fetch_nova_from_off(ean=ean, product_name=name)
        nova_score_set_by = None
        
        if nova_group is not None:
            nova_score_set_by = 'api'
            # Map NOVA group to score
            score = self.NOVA_MAP.get(nova_group, 50)
            return score, nova_score_set_by
        
        # Fallback to local calculation
        score = self.calculate_local_nova(product_data)

        if score is None:
            return None, None
        nova_score_set_by = 'local'
        return score, nova_score_set_by 