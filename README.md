# Product Scraper

A Python script to scrape product details from the search page. Built using `requests` and `BeautifulSoup`. 

## Features
- Extracts product name, price, MRP, discount, stock availability, and image URL
- Supports scraping multiple pages (pagination handling)
- Exports results directly to a CSV file

## Prerequisites
- Python 3.6+
- `requests`
- `beautifulsoup4`

## Installation
Clone the repository and install the required dependencies:
```bash
git clone https://github.com/AryaDuhan/scraper.git
cd scraper
pip install -r requirements.txt
```

## Usage
Run the script using Python:
```bash
python scraper.py "external harddrive"
```

### Options
- Search for a specific product: `python scraper.py "rtx 4060"`
- Set maximum pages to scrape: `python scraper.py "ram ddr5" --pages 3`
- Specify output CSV file name: `python scraper.py "ssd" --output results.csv`
