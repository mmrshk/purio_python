# Food Facts Data Collection

A Python-based data collection and processing pipeline for food products from Auchan Romania. The project scrapes product information, processes images for barcodes, and stores the data in a structured format in Supabase.

## Project Structure

```
food_facts/
├── processors/
│   ├── barcodes/           # Barcode processing modules
│   ├── helpers/            # Helper functions and utilities
│   ├── scraper/            # Web scraping modules
│   └── supabase/          # Supabase integration
├── auchan/                 # Scraped data storage
│   └── [category]/
│       ├── images/        # Product images
│       ├── product_links.csv
│       └── [category]_processed.csv
├── process_category.py     # Main processing script
└── requirements.txt        # Project dependencies
```

## Features

- Automated product data collection from Auchan Romania
- Image downloading and barcode extraction
- Specification and nutritional information mapping
- Data cleaning and validation
- Supabase integration for data storage
- Duplicate product detection
- Case-insensitive product name matching

## Prerequisites

- Python 3.8+
- OpenCV
- pyzbar
- Supabase account and credentials

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd food_facts
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in the project root with:
```
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```

## Usage

### Finding Category ID

To find a category ID:

1. Open the desired category page on Auchan's website (e.g., https://www.auchan.ro/lactate-carne-mezeluri---peste/lactate/iaurt/c)
2. Open your browser's Developer Tools (F12 or right-click -> Inspect)
3. Go to the "Network" tab
4. In the search/filter box, type: `route`
5. Look for a request that contains: `"domain":"store","id":"store.search#subcategory","params":{"id":`
6. The number after `"id":` is your category ID

Example:
```json
{
  "route": {
    "domain": "store",
    "id": "store.search#subcategory",
    "params": {
      "id": "2030300"  // This is your category ID
    }
  }
}
```

### Running the Script

To process a category, use the following command:

```bash
python process_category.py "CATEGORY_URL" --category-id "CATEGORY_ID"
```

Example:
```bash
python process_category.py "https://www.auchan.ro/lactate-carne-mezeluri---peste/lactate/iaurt/c" --category-id "2030300"
```

### What the Script Does

The script performs the following steps:
1. Collects product links from the specified category
2. Scrapes detailed product information
3. Saves data to CSV files
4. Processes barcodes
5. Maps specifications and nutritional information
6. Saves the processed data

### Output

The script creates the following files in the `auchan/{category}/{subcategory}/` directory:
- `product_links.csv`: Contains all product URLs
- `{subcategory}.csv`: Raw scraped data
- `{subcategory}_processed.csv`: Processed data with mapped specifications
- `unmapped_columns.json`: List of columns that couldn't be automatically mapped
- `images/`: Directory containing product images

## Common Category IDs

Here are some common category IDs for reference:
- Dairy Products (Lactate): 2030300
- Chocolate Bars (Batoane ciocolata): 3060100
- Mineral Water (Apa plata): 2010100

## Troubleshooting

If you encounter any issues:
1. Make sure you have the correct category ID
2. Check that the category URL is valid and accessible
3. Ensure you have all required dependencies installed
4. Check the network connection and Auchan's website availability

