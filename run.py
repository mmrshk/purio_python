from processors.scraper.collect_links import LinkCollector
from processors.scraper.auchan_scraper import AuchanScraper
import os

def main():
    # Initialize collectors
    link_collector = LinkCollector()
    scraper = AuchanScraper()
    
    # Category URL to scrape
    # category_url = "https://www.auchan.ro/bacanie/ceai-si-cafea/cafea-macinata/c"
    # category_url = "https://www.auchan.ro/lactate-carne-mezeluri---peste/mezeluri/c"
    category_url = "https://www.auchan.ro/lactate-carne-mezeluri---peste/carne/carne-de-pasare/c"
    # category_url = "https://www.auchan.ro/bacanie/dulciuri/prajituri-fursecuri-si-piscoturi/c"
    # category_url = "https://www.auchan.ro/lactate-carne-mezeluri---peste/lactate/branza-si-telemea/c"
    # category_url = "https://www.auchan.ro/lactate-carne-mezeluri---peste/carne/carne-de-pasare/c"
    
    # First collect all product links
    print("Starting link collection...")
    link_collector.collect_links(category_url)
    
    # Get the generated links file path from the collector
    links_file = os.path.join(link_collector.save_dir, 'product_links.csv')
    
    if os.path.exists(links_file):
        print(f"Found links file at: {links_file}")
        
        # Pass the links file to the scraper
        scraper.links_file = links_file
        
        # Scrape products (optionally with a limit)
        products = scraper.scrape_products()  # Set limit=None to scrape all
        
        # Save the results
        # get name of the category from the URL
        category_name = category_url.split('/')[-2]
        scraper.save_to_csv(f"{category_name}.csv")
        
        print("Scraping completed successfully!")
    else:
        print("Error: Links file not found!")

if __name__ == "__main__":
    main()