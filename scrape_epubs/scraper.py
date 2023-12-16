"""
This file is adapted from work with the following notice:

This work is created by the Department of the Air Force under 17 U.S.C. 105. 
This work may be reproduced, copied, modified, and used to create derivative works, without restriction and is in the public domain.
When reproducing, copying, modifying, or creating derivative works, the portion(s) of the work attributable under 17 U.S.C. 105 
may be designated with the above notice where appropriate. Improperly claiming ownership of this work could be punishable by law 
under 17 U.S.C. 506(c).

The above copyright notice and this permission notice should be included in all copies or substantial portions of the work.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. 
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, 
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE 
OR OTHER DEALINGS IN THE SOFTWARE.
"""


import sys
import os
import time
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
import urllib
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from argparse import ArgumentParser

"""
Example usage:

As CLI:
python scraping_af_regulations.py 
    --website "https://www.e-publishing.af.mil/Product-Index/#/?view=pubs&orgID=10141&catID=1&series=5&modID=449&tabID=131" /
    --save_loc downloaded_pdfs /
    --driver_loc "C://Users/PA27879/chromium/chromedriver.exe"

As function:
scraper(
    argv=[
        "--website", 
        "https://www.e-publishing.af.mil/Product-Index/#/?view=pubs&orgID=10141&catID=1&series=5&modID=449&tabID=131", 
        "--save_loc", 
        "downloaded_pdfs", 
        "--driver_loc", 
        "C://Users/PA27879/chromium/chromedriver.exe"
    ]
)
"""


WEBSITE_KEY = 'website'
LOC_KEY = 'save_loc'
DRIVER_KEY = 'driver'
DRIVER_LOC_KEY = 'driver_loc'

def _parse_cli(argv):
        parser = ArgumentParser(description='splits the given bitext file into a source and target file')
        parser.add_argument('--%s' % WEBSITE_KEY, required=True, help='the website url from which to download all pdfs')
        parser.add_argument('--%s' % LOC_KEY, required=True, help='the destination in which to save the resulting pdfs')
        parser.add_argument('--%s' % DRIVER_KEY, required=False, help='Which driver to use (defaults to chrome)')
        parser.add_argument('--%s' % DRIVER_LOC_KEY, required=False, help='The location of the driver to use (defaults to path)')
        return vars(parser.parse_args(argv))

def download_pdf(pdf_loc, save_loc):
    pdf_name = os.path.split(pdf_loc)[-1]
    if not os.path.isdir(save_loc):
        os.mkdir(save_loc)
    with urllib.request.urlopen(pdf_loc) as web_file:
        web_pdf = web_file.read()
    with open(os.path.join(save_loc, pdf_name), 'wb+') as f:
        f.write(web_pdf)

def scraper(argv=None):

    if argv is None:
        argv = sys.argv[1:]
    opts = _parse_cli(argv=argv)
    url = opts[WEBSITE_KEY]
    save_loc = opts[LOC_KEY]
    driver = opts[DRIVER_KEY] if DRIVER_KEY in opts and opts[DRIVER_KEY] is not None else 'chrome'
    driver_loc = opts[DRIVER_LOC_KEY] if DRIVER_LOC_KEY in opts else None

    # check if ./<save_loc> exists--if not, create it
    if not os.path.isdir(save_loc):
        os.mkdir(save_loc)

    if driver == 'chrome':
        driver_func = webdriver.Chrome
    elif driver == 'firefox':
        driver_func = webdriver.Firefox
    else:
        raise ValueError('{} not currently supported'.format(driver))
    if driver_loc is None:
        driver = driver_func()
    else:
        # driver = driver_func(driver_loc)
        cService = webdriver.ChromeService(executable_path=driver_loc)
        driver = webdriver.Chrome(service = cService)

    try:
        mds = []
        driver.get(url)
        cont = True
        page = 2
        driver.find_element(By.LINK_TEXT, str(page)).click()

        while cont:
            print(page, end='\r', flush=True)
            content = driver.page_source
            soup = BeautifulSoup(content, features="html.parser")
            for i, obj in enumerate(soup.find_all('table')):
                all_rows = obj.find_all('tr')
                for j, row in enumerate(all_rows):
                    all_cols = row.find_all('td')
                    for k, col in enumerate(all_cols):
                        for link in col.find_all('a'):
                            title = link.get('title')
                            if title is not None and title == 'View Detail':
                                print(link.getText())
                                driver.find_element(By.LINK_TEXT, link.getText()).click()
                                # driver.find_element_by_link_text(link.getText()).click()
                                time.sleep(1)
                                metadata = {}
                                content = driver.page_source
                                soup = BeautifulSoup(content, features="html.parser")
                                for sub_row in soup.find_all('table')[0].find_all('tr'):
                                    for sub_col in sub_row.find_all('th'):
                                        feat_name = sub_col.getText()
                                    for sub_col in sub_row.find_all('td'):
                                        metadata[feat_name] = sub_col.getText()
                                # driver.find_element_by_class_name('close').click()
                                driver.find_element(By.CLASS_NAME, 'close').click()
                                time.sleep(1)
                                mds.append(metadata)
                            elif title is not None and title == 'Download PDF':
                                pdf_loc = link.get('href')
                                download_pdf(pdf_loc, save_loc)


            page += 1
            elements = driver.find_elements(By.LINK_TEXT, str(page))
            if len(elements) == 0:
                cont = False
            else:
                elements[0].click()

        driver.quit()
        metadata = pd.DataFrame.from_dict(mds)
        # metadata.index = metadata['Product Title']

        #

        metadata.to_csv(os.path.join(save_loc, 'metadata.csv'))
        
        
        
        # driver.get(url)
        # cont = True
        # page = 1
        # while cont:
        #     print(page, end='\r', flush=True)
        #     content = driver.page_source
        #     soup = BeautifulSoup(content, features="html.parser")
        #     for i, obj in enumerate(soup.find_all('table')):
        #         all_links = obj.find_all('a')
        #         for j, link in enumerate(all_links):
        #             pdf_loc = link.get('href')
        #             if pdf_loc and pdf_loc != '#':
        #                 download_pdf(pdf_loc, save_loc)
        #     page += 1
        #     elements = driver.find_elements(By.LINK_TEXT, str(page))
        #     # elements = driver.find_elements_by_link_text(str(page))
        #     if len(elements) == 0:
        #         cont = False
        #     else:
        #         elements[0].click()

    except:
        driver.quit()
        raise ValueError('Closing after something broke')
    
def run_scraper():
    scraper(
        argv=[
            "--website", 
            "https://www.e-publishing.af.mil/Product-Index/#/?view=pubs&orgID=10141&catID=1&series=-1&modID=449&tabID=131", 
            "--save_loc", 
            "saved_op_pdfs", 
            "--driver_loc", 
            "/usr/bin/chromedriver"
        ]
    )

if __name__ == "__main__":
    run_scraper()