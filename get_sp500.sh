#!/usr/bin/env bash

set -euo pipefail

readonly URL="https://raw.githubusercontent.com/datasets/s-and-p-500-companies/refs/heads/main/data/constituents.csv"

python3 - "$URL" <<'PY'
import csv
import re
import sys
import urllib.request

url = sys.argv[1]
companies = []

with urllib.request.urlopen(url) as response:
    lines = (line.decode("utf-8-sig") for line in response)
    reader = csv.DictReader(lines)

    for row in reader:
        company = row.get("Security", "").strip() or "N/A"
        location = row.get("Headquarters Location", "").strip() or "N/A"
        founded = row.get("Founded", "").strip()

        match = re.match(r"^\d{4}", founded)
        year = int(match.group()) if match else None

        companies.append((year, company, location))

companies.sort(
    key=lambda item: (
        item[0] is None,
        item[0] if item[0] is not None else 0,
        item[1].casefold(),
    )
)

print(f'{"Company Name":<40} | {"Location":<35} | Founded')
print("-" * 90)

for year, company, location in companies:
    founded_year = str(year) if year is not None else "N/A"
    print(f"{company[:40]:<40} | {location[:35]:<35} | {founded_year}")
PY
