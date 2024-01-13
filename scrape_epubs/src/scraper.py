import os
os.environ["SECRETS"] = "True"
import re
import time
from selenium import webdriver
import time
import json
from datetime import datetime
from source_saver import save_json_source_data_to_db
from pdf_pipeline import save_json_chunk_data_to_db
from aimbase.initializer import AimbaseInitializer
from instarest import Initializer, DeclarativeBase

def convert_date(match):
    # Extract the timestamp (in milliseconds) and convert to seconds
    timestamp = int(match.group(1)) / 1000.0
    # Convert to a datetime object and format as ISO 8601
    return datetime.utcfromtimestamp(timestamp).isoformat() + 'Z'

def scraper(argv=None):
    # Initialize WebDriver
    driver = webdriver.Chrome(
        service=webdriver.ChromeService(executable_path="/usr/bin/chromedriver")
    )

    # Open the target webpage
    driver.get("https://www.e-publishing.af.mil")

    # Wait for the page to load completely
    time.sleep(5)

    # Redirect console.log to a JavaScript variable
    driver.execute_script(
        """
    window.logged_data = [];
    console.log = function() {
        window.logged_data.push(Array.from(arguments));
    };
    """
    )

    # Execute the AJAX call
    ajax_script = """
    var rvtoken = $("input[name='__RequestVerificationToken']").val();
    $.ajax({
        url: "/DesktopModules/MVC/EPUBS/EPUB/GetPubsBySeriesView/",
        method: "Get",
        headers: {
            "ModuleId": 449,
            "TabId": 131,
            "RequestVerificationToken": rvtoken
        },
        data: {
            "orgID": 10141,
            "catID": 1,
            "series": -1
        }
    })
    .done(function (data) {
        console.log(data);
    });
    """
    driver.execute_script(ajax_script)

    # Wait for the AJAX call to complete
    time.sleep(5)  # Adjust this wait time as necessary

    # Retrieve the logged data
    logged_data = driver.execute_script("return window.logged_data;")
    logged_data_str = json.dumps(logged_data)

    # Close the browser
    driver.quit()

    # match = re.search(r"data: (\{.*?\})", logged_data_str, re.DOTALL)
    # Extract the 'publications' array from the logged data using regex
    match = re.search(r"publications: (\[\{.*?\}\])", logged_data_str, re.DOTALL)
    publications_raw_data = match.group(1) if match else None

    # with open('publications_json.json', 'w') as file:
    #     file.write(publications_json)

    # Clean up the extracted JSON string
    # publications_json = publications_json.replace('\\r\\n', '').replace('\\"', '"')
    publications_raw_data = publications_raw_data.replace('\\"', '"').replace('\\\\/', '/')
    
    # Convert date format
    publications_raw_data = re.sub(r'\\/Date\((\d+)\)\\/', convert_date, publications_raw_data)

    # weird leftover cleanup
    publications_raw_data = publications_raw_data.replace('\\\\"', '')

    # Parse and write the cleaned JSON to a file
    try:
        publications_data = json.loads(publications_raw_data)
        with open("publications_data.json", "w") as file:
            json.dump(publications_data, file, indent=4)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")

    print("Number of pubs found: ", len(publications_data))
    return publications_data

def run_scraper():
    # Start measuring time
    start_time = time.time()

    publications_data = scraper()
    # with open("./publications_data.json", 'r') as file:
    #     publications_data = json.load(file)

    Initializer(DeclarativeBase).execute(vector_toggle=True)
    AimbaseInitializer().execute()

    save_json_source_data_to_db(publications_data)
    save_json_chunk_data_to_db(publications_data)

    # End measuring time
    end_time = time.time()

    # Calculate the time required to complete
    elapsed_time = end_time - start_time

    print(f"Time required to complete: {elapsed_time} seconds")

if __name__ == "__main__":
    run_scraper()
