import csv
import os
from bs4 import BeautifulSoup
import requests

# Define file paths and constants
IDS_FILE = "extracted_ids.txt"
OUTPUT_FILE = "scraped_jobs_list.csv"

# Company name configuration variable
COMPANY_NAME = "Swapfiets"


def load_job_ids(file_path):
    """Reads extracted IDs from a local text file."""
    if not os.path.exists(file_path):
        print(f"Error: '{file_path}' not found!")
        print("Please run your previous regex script to generate the IDs first.")
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        # Read lines, strip spaces, and filter out any blank lines
        ids = [line.strip() for line in f if line.strip().isdigit()]

    print(f"Loaded {len(ids)} job IDs from {file_path}.")
    return ids


def main():
    # 1. Load the IDs from your text file
    job_ids = load_job_ids(IDS_FILE)
    if not job_ids:
        return

    # 2. Set up a persistent Session (keeps execution fast without needing sleep)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )

    scraped_jobs_data = []

    print("\nStarting fast scraping sequence (No sleep pauses)...")

    # 3. Process every dynamic ID
    for index, job_id in enumerate(job_ids, start=1):
        job_url = f"https://jobs.swapfiets.com/jobs/{job_id}"
        print(f"[{index}/{len(job_ids)}] Fetching: {job_url}")

        try:
            # Fetch the page through the active session
            response = session.get(job_url, timeout=10)

            if response.status_code != 200:
                print(f"   -> Failed: HTTP Status {response.status_code}")
                continue

            # Parse the text response with BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")

            # --- Extract Data Using Target Framer Structural Names ---

            # Job Title
            title_div = soup.find("div", {"data-framer-name": "Title"})
            job_title = (
                title_div.get_text(strip=True) if title_div else "N/A"
            )

            # Job Type (e.g., "Store & Field")
            tag_div = soup.find("div", {"data-framer-name": "Tag"})
            job_type = tag_div.get_text(strip=True) if tag_div else "N/A"

            # Region / Location
            location_div = soup.find("div", {"data-framer-name": "Location"})
            region = (
                location_div.get_text(strip=True) if location_div else "N/A"
            )

            # Type of Contract
            contract_div = soup.find("div", {"data-framer-name": "Contract"})
            contract_type = (
                contract_div.get_text(strip=True) if contract_div else "N/A"
            )

            # Posting Date (Framer maps this element label to 'Salary')
            date_div = soup.find("div", {"data-framer-name": "Salary"})
            posting_date = (
                date_div.get_text(strip=True) if date_div else "N/A"
            )

            # Apply Link Lookup
            apply_link = "N/A"
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if "careers.hibob.com" in href or "apply" in href.lower():
                    apply_link = href
                    break

            # Collect results if a title was found
            if job_title != "N/A":
                scraped_jobs_data.append(
                    {
                        "Company": COMPANY_NAME,
                        "Job ID": job_id,
                        "Job Title": job_title,
                        "Job Type": job_type,
                        "Posting Date": posting_date,
                        "Contract Type": contract_type,
                        "Region": region,
                        "Apply Link": apply_link,
                    }
                )
            else:
                print("   -> Warning: Page layout did not match parameters.")

        except Exception as e:
            print(f"   -> Network Error with ID {job_id}: {e}")

    # 4. Save everything to the CSV file
    if scraped_jobs_data:
        keys = scraped_jobs_data[0].keys()
        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as output:
            dict_writer = csv.DictWriter(output, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(scraped_jobs_data)

        print(
            f"\nSuccess! Extracted {len(scraped_jobs_data)} entries directly into '{OUTPUT_FILE}'"
        )
    else:
        print("\nNo job fields could be parsed.")


if __name__ == "__main__":
    main()