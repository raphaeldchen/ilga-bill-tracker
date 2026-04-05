# python tracker.py "C:\Users\rapha\Box"

import requests
import argparse
from bs4 import BeautifulSoup
import pandas as pd
import csv
import os
import schedule
import time

print('Retrieving Directory Path...')
parser = argparse.ArgumentParser()
parser.add_argument('folder_path', type = str, help = 'Path to the file')
args = parser.parse_args()
def get_path(file_name, start_dir = '/'):
    for root, dirs, files in os.walk(start_dir):
        if file_name in files or file_name in dirs:
            return os.path.join(root, file_name)
    return None
box_folder = args.folder_path
folder = get_path('updated tracker', start_dir = box_folder)
url_list = get_path('Legislative Tracker Bills.txt', start_dir = folder)
with open(url_list, 'rt', encoding='utf-8-sig') as infile:
    lines = [line.strip() for line in infile]

def fetch_new_actions(url, cutoff_date = None):
    actions_list = []
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    bill_name = soup.find('title').text.strip() if soup.find('title') else "Unknown Bill"
    actions_heading = soup.find('span', class_='heading2', string='Actions')
    actions_table = actions_heading.find_next_sibling('table') if actions_heading else None
    if not actions_table:
        actions_list.append({
            'Bill': bill_name[-6:],
            'Date': "N/A",
            'Chamber': "N/A",
            'Action': "N/A",
            'Webpage Title': bill_name
        })
        return actions_list
    td_elements = actions_table.find_all('td')
    for i in range(0, len(td_elements), 3):
        if i + 2 < len(td_elements):
            date_str = td_elements[i].text.strip()
            try:
                parsed_date = pd.to_datetime(date_str, errors='coerce')
                if parsed_date is not pd.NaT and (cutoff_date is None or parsed_date > pd.to_datetime(cutoff_date)):
                    actions_list.append({
                        'Bill': bill_name[-6:],
                        'Date': date_str,
                        'Chamber': td_elements[i + 1].text.strip(),
                        'Action': td_elements[i + 2].text.strip(),
                        'Webpage Title': bill_name
                    })
            except ValueError:
                continue
    return actions_list

file_name = 'legislative_tracker_updates.csv'
file_path = os.path.join(folder, file_name)
print('Fetching csv file...')
with open(file_path, mode = 'w', newline = '', encoding = 'utf-8') as file:
    fieldnames = ['Bill', 'Date', 'Chamber', 'Action', 'Webpage Title']
    writer = csv.DictWriter(file, fieldnames = fieldnames)
    writer.writeheader()
    print('Fetching Actions...')
    for url in lines:
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            print(f"Skipping invalid URL: {url}")
            continue
        try:
            actions = fetch_new_actions(url)
            writer.writerows(actions)
        except requests.exceptions.RequestException as e:
            print(f"Request failed for {url}: {e}")
print(f"Scraped bill actions have been saved to {file_name}.")

command = 'python tracker.py "' + args.folder_path + '"'
def runtracker():
    os.system(command)
schedule.every().monday.at('08:00').do(runtracker)
print('Tracker scheduled to run weekly. Press Ctrl+C to stop.')
while True:
    schedule.run_pending()
    time.sleep(60)