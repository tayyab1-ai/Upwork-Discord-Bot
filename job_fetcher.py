import os
import re
import json
import time
import random
from curl_cffi import requests
from dotenv import load_dotenv
from auth_manager import update_cookies_and_headers_in_env
from database_setup import get_connection, save_job
from logger_config import log


# Fetch Jobs Function
def fetch_upwork_jobs(query, count=1):
    # request URL for Upwork's GraphQL API endpoint
    url = "https://www.upwork.com/api/graphql/v1"

    # Load environment variables from .env file
    load_dotenv(override=True)
    headers_raw = os.getenv('UPWORK_HEADERS', '{}')
    cookies_raw = os.getenv('UPWORK_COOKIES', '{}')
    
    # Convert raw JSON strings from environment variables to Python dictionaries
    headers = json.loads(headers_raw)
    cookies = json.loads(cookies_raw)

    json_data = {
        'query': '\n  query VisitorJobSearch($requestVariables: VisitorJobSearchV1Request!) {\n    search {\n      universalSearchNuxt {\n        visitorJobSearchV1(request: $requestVariables) {\n          paging {\n            total\n            offset\n            count\n          }\n          \n    facets {\n      jobType \n    {\n      key\n      value\n    }\n  \n      workload \n    {\n      key\n      value\n    }\n  \n      clientHires \n    {\n      key\n      value\n    }\n  \n      durationV3 \n    {\n      key\n      value\n    }\n  \n      amount \n    {\n      key\n      value\n    }\n  \n      contractorTier \n    {\n      key\n      value\n    }\n  \n      contractToHire \n    {\n      key\n      value\n    }\n  \n      \n    }\n  \n          results {\n            id\n            title\n            description\n            relevanceEncoded\n            ontologySkills {\n              uid\n              parentSkillUid\n              prefLabel\n              prettyName: prefLabel\n              freeText\n              highlighted\n            }\n            \n            jobTile {\n              job {\n                id\n                ciphertext: cipherText\n                jobType\n                weeklyRetainerBudget\n                hourlyBudgetMax\n                hourlyBudgetMin\n                hourlyEngagementType\n                contractorTier\n                sourcingTimestamp\n                createTime\n                publishTime\n                \n                hourlyEngagementDuration {\n                  rid\n                  label\n                  weeks\n                  mtime\n                  ctime\n                }\n                fixedPriceAmount {\n                  isoCurrencyCode\n                  amount\n                }\n                fixedPriceEngagementDuration {\n                  id\n                  rid\n                  label\n                  weeks\n                  ctime\n                  mtime\n                }\n              }\n            }\n          }\n        }\n      }\n    }\n  }\n  ',
        'variables': {
            'requestVariables': {
                'userQuery': query,
                'sort': 'recency',
                'highlight': True,
                'paging': {
                    'offset': 0,
                    'count': count,
                },
            },
        },
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            cookies=cookies,
            json=json_data,
            impersonate="chrome110",
            timeout=30
        )

        # ✅ Request Successful
        if response.status_code == 200:
            parsed_data = response.json()
    
            # Navigate through the nested JSON structure to extract job details
            """
            The JSON response from Upwork's GraphQL API is deeply nested
            {
                "data": {
                    "search": {
                        "universalSearchNuxt": {
                            "visitorJobSearchV1": {
                                "results": [...job details...]
                            }
                        }
                    }
                }
            }
            """
            data = parsed_data.get("data") or {}
            search = data.get("search") or {}
            universal = search.get("universalSearchNuxt") or {}
            job_search = universal.get("visitorJobSearchV1") or {}
            raw_results = job_search.get("results") or []
    
            # Ensure raw_results is a list
            if not isinstance(raw_results, list):
                raw_results = []
    
            # Process and format the raw job data into a cleaner structure
            formatted_jobs = []
    
            # Loop through each job in the raw results and extract relevant fields
            for job in raw_results:
                if not isinstance(job, dict):
                    continue
    
                job_tile = job.get("jobTile") or {}
                job_details = job_tile.get("job") or {}
                skills_list = job.get("ontologySkills") or []
                ciphertext = job_details.get("ciphertext")
                
                job_url = None
                if ciphertext:
                    job_url = f"https://www.upwork.com/jobs/{ciphertext}"
                
                # Raw nested json to clean python dict
                job_dict = {
                    "id": job.get("id"),
                    "title": job.get("title"),
                    "description": job.get("description"),
                    "job_type": job_details.get("jobType"),
                    "budget": (job_details.get("fixedPriceAmount") or {}).get("amount"),
                    "hourly_min": job_details.get("hourlyBudgetMin"),
                    "hourly_max": job_details.get("hourlyBudgetMax"),
                    "tier": job_details.get("contractorTier"),
                    "duration": (job_details.get("hourlyEngagementDuration") or {}).get("label"),
                    "published_time": job_details.get("publishTime"),
                    "created_time": job_details.get("createTime"),
                    "url": job_url,
                    "skills": ", ".join(
                        [s.get("prefLabel") for s in skills_list if isinstance(s, dict) and s.get("prefLabel")]
                    )
                }
    
                formatted_jobs.append(job_dict)
            print(f"✅  Successfully fetched {len(formatted_jobs)} jobs for query '{query}'.")
    
            return {
                "status": "success",
                "code": 200,
                "jobs": formatted_jobs
            }

        # ⚠️ Error 403
        elif response.status_code == 403:
            return {
                "status": "error",
                "code": 403,
                "message": "Access Denied - 403 Cloudflare Block."
            }
        

        # ⚠️ Other Errors
        else:
            return {
                "status": "error",
                "code": response.status_code,
                "message": f"Request Failed with status code {response.status_code}."
            }

    # ⚠️ Exception Handling - Network issues, timeouts, or JSON parsing errors
    except Exception as e:
        return {
            "status": "exception",
            "message": str(e)
        }


# Data Cleaning Function using regex
def clean_text(text):
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]*>', '', text)
    # Remove Upwork specific highlight symbols (e.g. H^Data^H)
    text = re.sub(r'H\^| \^H|\^H', '', text)
    # Clean extra white spaces
    text = " ".join(text.split())
    return text


# Function to check if a job already exists in the database
def job_exists(job_id):
    conn = get_connection()
    cursor = conn.cursor()
    # Check if the job exists
    cursor.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,))
    result = cursor.fetchone()
    conn.close()

    if result is not None:
        print(f"⚠️  Job with ID {job_id} already exists in the database. Skipping.")
        return True
    
    return False



# Main function to process and store jobs in database
def process_and_store_jobs(query, count):
    # Fetch jobs
    result = fetch_upwork_jobs(query, count)

    # Process and store jobs if fetch was successful
    if result["status"] == "success":
        jobs_list = result["jobs"]
        new_jobs_count = 0

        for job in jobs_list:
            job_id = job.get('id')

            # 1. Check if job already exists in database
            if job_exists(job_id):
                continue

            # 2. Data Cleaning for title and description
            job['title'] = clean_text(job.get('title'))
            job['description'] = clean_text(job.get('description'))
            job['skills'] = clean_text(job.get('skills')) 
            job['duration'] = clean_text(job.get('duration'))
            job['published_time'] = clean_text(job.get('published_time'))
            job['created_time'] = clean_text(job.get('created_time'))
            job['job_type'] = clean_text(job.get('job_type'))
            job['budget'] = job.get('budget') if job.get('budget') is not None else 0.0
            job['hourly_min'] = job.get('hourly_min') if job.get('hourly_min') is not None else 0.0
            job['hourly_max'] = job.get('hourly_max') if job.get('hourly_max') is not None else 0.0
            job['tier'] = job.get('tier') if job.get('tier') is not None else 0
            job['url'] = job.get('url') if job.get('url') is not None else ""
            job['category'] = query

            # 3. Store the cleaned dictionary directly into the database 
            save_job(job)
            log.info(f"✅  Stored New Job: {job['title']}")
            new_jobs_count += 1
        
        print(f"💬 Total {new_jobs_count} new jobs data cleaned and added to DB.")

    else:
        log.error(f"⚠️  Error fetching jobs: {result.get('message')}")

        # Wait before retrying to avoid rapid requests
        print("\nWaiting before retrying (2-5 seconds)...\n")
        time.sleep(random.randint(2, 5))  

        # Update cookies and headers
        update_cookies_and_headers_in_env()

        # Retry fetching jobs after updating headers and cookies
        log.info("Retrying fetch after updating...\n")
        process_and_store_jobs(query, count)


# Function to get new job IDs that are not yet posted to Discord
def get_new_job_ids(category):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT job_id FROM jobs WHERE discord_posted = 0 AND category = ?", (category,))
    new_job_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    print(f"🔍 Found {len(new_job_ids)} jobs for {category} not yet posted to Discord.")
    return new_job_ids


# TESTING: Fetch and Display Raw and Cleaned Data
def testing(query, count):
    result = fetch_upwork_jobs(query, count)
    print(f"--- Showing {len(result['jobs'])} Jobs --- \n\n")
    
    # Display Cleaned Data
    print("\n--- Processing Cleaned Data ---\n")
    for job in result["jobs"]:
        cleaned_title = clean_text(job.get('title'))
        cleaned_desc = clean_text(job.get('description'))
        
        print(f"✅ Cleaned Title:    {cleaned_title}")
        print(f"✅ Cleaned Description:    {cleaned_desc}")
        print(f"✅ Cleaned Posted Time:    {clean_text(job.get('published_time'))}")
        print(f"✅ Cleaned URL:    {clean_text(job.get('url'))}")
        print("-" * 30)


"""
# TEST FUNCTION CALL
testing("Python", 5)
"""



"""
# TESTING: Get new job IDs
new_job_ids = get_new_job_ids(category="AI")
print(f"New Job IDs not yet posted to Discord: {new_job_ids}")
"""