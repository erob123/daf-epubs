import time
import datetime
from scrape_epubs.src.scraper import run_scraper

# Schedule the function to run every Saturday at 05:01 UTC
def schedule_function():
    now = datetime.datetime.utcnow()
    if now.weekday() == 5 and now.hour == 5 and now.minute == 1:  # Saturday is weekday 5
        run_scraper()

def main():
    # Run the scheduling loop
    while True:
        schedule_function()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()