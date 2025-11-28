# Process Category Usage Examples

## Basic Usage

### Full Pipeline (Default)
```bash
python process_category.py "https://www.auchan.ro/bacanie/c" --category-id "your-category-id"
```

### Start from Health Scoring Only
```bash
python process_category.py "https://www.auchan.ro/bacanie/c" --category-id "your-category-id" --start-from health-scoring
```

### Start from Supabase Insertion
```bash
python process_category.py "https://www.auchan.ro/bacanie/c" --category-id "your-category-id" --start-from supabase
```

### Start from Barcode Processing
```bash
python process_category.py "https://www.auchan.ro/bacanie/c" --category-id "your-category-id" --start-from barcodes
```

## Available Start Points

| Option | Description | Steps Skipped |
|--------|-------------|---------------|
| `scraping` (default) | Full pipeline | None |
| `barcodes` | Skip scraping | Steps 1-3 |
| `supabase` | Skip scraping + barcodes + mapping | Steps 1-5 |
| `health-scoring` | Skip everything except health scoring | Steps 1-6 |

## Use Cases

### 1. Resume After Scraping
If you've already scraped products but want to redo barcode processing:
```bash
python process_category.py "https://www.auchan.ro/bacanie/c" --category-id "your-category-id" --start-from barcodes
```

### 2. Resume After Supabase Insertion
If products are already in Supabase but you want to recalculate health scores:
```bash
python process_category.py "https://www.auchan.ro/bacanie/c" --category-id "your-category-id" --start-from health-scoring
```

### 3. Fix Health Scores Only
If you want to recalculate health scores for existing products:
```bash
python process_category.py "https://www.auchan.ro/bacanie/c" --category-id "your-category-id" --start-from health-scoring
```

## File Requirements

Each start point requires certain files to exist:

- **`scraping`**: No requirements (starts from scratch)
- **`barcodes`**: Requires `{subcategory}.csv` file
- **`supabase`**: Requires `{subcategory}_processed.csv` file
- **`health-scoring`**: Requires `{subcategory}_processed.csv` file

## Error Handling

The script will check for required files and give clear error messages if they're missing:

```
Error: CSV file not found at /path/to/file.csv
Error: Processed CSV file not found at /path/to/file_processed.csv
```
