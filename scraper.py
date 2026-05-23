import os
import re
import csv
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# --- STEP 1 & 2: Get a random initial job URL ---
def get_initial_job_url(department_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    print(f"[Step 1] Fetching and parsing HTML from: {department_url}")
    
    try:
        response = requests.get(department_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        job_anchors = soup.find_all('a', href=re.compile(r'/jobs/\d+'))
        
        for anchor in job_anchors:
            href = anchor.get('href', '')
            match = re.search(r'/jobs/(\d+)', href)
            if match:
                job_id = match.group(1)
                job_url = f"https://jobs.swapfiets.com/jobs/{job_id}"
                print(f"[Step 2] Found Job ID '{job_id}'. Created initial URL: {job_url}")
                return job_url
                
        print("[-] Error: Could not extract any initial Job IDs from the HTML layout.")
        return None
    except Exception as e:
        print(f"[-] Network/Parsing Error in Step 1: {e}")
        return None


# --- STEPS 3, 4 & 5: Trace Network Traffic & Extract All Job IDs ---
def pipeline_extract_all_ids(job_url):
    if not job_url:
        print("[-] Aborting: No valid job URL provided.")
        return []

    print(f"\n[Step 3] Launching Chromium to trace network traffic on: {job_url}")
    unique_job_ids = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-gpu', '--no-sandbox', '--disable-setuid-sandbox']
        )
        context = browser.new_context()
        page = context.new_page()

        # Network interceptor callback loop
        def handle_response(response):
            request = response.request
            
            # [Step 4] Select Framer CMS backend data streams
            if request.resource_type in ["xhr", "fetch"] and request.url.startswith("https://framerusercontent.com/cms/"):
                try:
                    print(f"\n[Step 4] Intercepted Target Framer API: {request.url}")
                    text_data = response.text()
                    
                    # [Step 5] Run numeric digit bounding regex on the response data stream
                    id_regex = r"\b\d{12,17}\b"
                    matches = re.findall(id_regex, text_data)
                    
                    if matches:
                        print(f"[Step 5] Processing regex matches...")
                        for found_id in matches:
                            if found_id not in unique_job_ids:
                                unique_job_ids.add(found_id)
                                print(f"    -> Extracted Job ID: {found_id}")
                except Exception as e:
                    print(f"[-] Could not read text data from API stream: {e}")

        page.on("response", handle_response)
        page.goto(job_url, wait_until="networkidle")
        page.wait_for_timeout(4000)  # Safe buffer for async frames

        browser.close()
        
    return sorted(list(unique_job_ids))


# --- STEP 6: Loop through discovered IDs, scrape features, and write CSV ---
def execute_batch_scraping_and_save(job_ids, output_file="scraped_jobs_list.csv"):
    if not job_ids:
        print("\n[-] No job fields could be parsed because the Job ID list is empty.")
        return

    print(f"\n[Step 6] Initializing Batch Data Scraping loop for {len(job_ids)} jobs...")
    
    COMPANY_NAME = "Swapfiets"
    scraped_jobs_data = []

    # Maintain an active network session context to increase performance speed
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })

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
            job_title = title_div.get_text(strip=True) if title_div else "N/A"

            # Job Type (e.g., "Store & Field")
            tag_div = soup.find("div", {"data-framer-name": "Tag"})
            job_type = tag_div.get_text(strip=True) if tag_div else "N/A"

            # Region / Location
            location_div = soup.find("div", {"data-framer-name": "Location"})
            region = location_div.get_text(strip=True) if location_div else "N/A"

            # Type of Contract
            contract_div = soup.find("div", {"data-framer-name": "Contract"})
            contract_type = contract_div.get_text(strip=True) if contract_div else "N/A"

            # Posting Date (Framer maps this element label to 'Salary')
            date_div = soup.find("div", {"data-framer-name": "Salary"})
            posting_date = date_div.get_text(strip=True) if date_div else "N/A"

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

    # Save everything to the CSV file
    if scraped_jobs_data:
        keys = scraped_jobs_data[0].keys()
        with open(output_file, "w", newline="", encoding="utf-8") as output:
            dict_writer = csv.DictWriter(output, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(scraped_jobs_data)

        print(f"\nSuccess! Extracted {len(scraped_jobs_data)} entries directly into '{output_file}'")
    else:
        print("\nNo job fields could be parsed.")


# --- Pipeline Execution Orchestrator ---
if __name__ == "__main__":
    start_url = 'https://jobs.swapfiets.com/departments/store-field'
    csv_output_file = 'scraped_jobs_list.csv'
    
    # 1. Run Step 1 & 2 to find an entry link
    initial_url = get_initial_job_url(start_url)
    
    # 2. Run Step 3, 4 & 5 to trace background API data and pull all matching IDs
    if initial_url:
        all_discovered_ids = pipeline_extract_all_ids(initial_url)
        
        # 3. Run Step 6 to gather and format individual job features into your CSV structure
        execute_batch_scraping_and_save(all_discovered_ids, csv_output_file)
