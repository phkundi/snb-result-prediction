import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from datetime import datetime
import json

current_athlete = "http://www.worldsnowboarding.org/riders/ryan-stassel/"
current_event = "http://www.worldsnowboarding.org/events/fis-world-cup-2020-4/"

res = requests.get(current_event)
soup = BeautifulSoup(res.content, 'html.parser')

header = soup.find(class_="detailed-header")
ce_name = header.find(class_="event-label").get_text().strip()

details = header.find(class_="icon-group")
ce_disciplines = details.find_all(class_="icon-discipline-large")
ce_disciplines = [d.get_text().strip() for d in ce_disciplines]
ce_genders = details.find(class_="icon-type-large").get_text().strip()
ce_genders = [ce_genders[i:i+1] for i in range(0, len(ce_genders), 1)]

ce_start_date = None
ce_info = header.find(class_="plain-list")
items = ce_info.find_all("li")

for item in items:
    item_text = item.get_text()
    if "Date:" in item_text:
        date = item_text.strip().replace("Date: ", "")
        if " - " in date:
            date_range = date.split(" - ")
            ce_start_date = date_range[0]
            ce_start_date = datetime.strptime(ce_start_date, "%d.%m.%y")
        else:
            ce_start_date = datetime.strptime(date, "%d.%m.%y")


ranking_table = soup.find("table", class_="rank-results")
ranks = ranking_table.find_all(class_="rank")
ce_number_competitors = len(ranks)

points_sum = 0

for result in ranks:
    cells = result.find_all("td")
    athlete_profile = cells[1].find("a")['href']
    res = requests.get("http://worldsnowboarding.org" + athlete_profile)
    profile = BeautifulSoup(res.content, 'html.parser')
    ss_details = profile.find(id="result-table-points-list-ss").find_all("li")

    for i in ss_details:
        if "Current Points" in i.get_text().strip():
            profile_ss_points = float(i.find("strong").get_text())
            points_sum += profile_ss_points

ce_points_average = round((points_sum / ce_number_competitors),2)

print(f"Event Name: {ce_name}")
print(f"Event Disciplines: {ce_disciplines}")
print(f"Event Competitions: {ce_genders}" )
print(f"Event Start Date: {ce_start_date}")
print(f"Number of Competitors: {ce_number_competitors}")
print(f"Average WSPL Points: {ce_points_average}")

def diff_month(date):
    now = datetime.now()
    return (now.year - date.year) * 12 + now.month - date.month

res = requests.get(current_athlete)
soup = BeautifulSoup(res.content, 'html.parser')
results_table = soup.find(id="result-table-all-results-all-results").find(class_="rank-results")
results = results_table.find_all(class_="rank")

rider_results = []
for result in results:
    cells = result.find_all("td")
    result_discipline = cells[-1].find(class_="icon-discipline-medium").get_text().strip()
    if result_discipline == "SS":
        event_date = cells[0].get_text().strip()
        event_date = datetime.strptime(event_date, "%d.%m.%y")
        
        if diff_month(event_date) < 48 and event_date < ce_start_date:
            rank = cells[1].get_text().strip().replace("st", "").replace("nd", "").replace("rd", "").replace("th", "")
            rank = int(rank)
            event_name = cells[3].find("a").get_text().strip()
            event_link = cells[3].find("a")['href']
            event_link = "http://worldsnowboarding.org" + event_link
            
            # Make sure we don't consider the event we want to predict
            if event_link != current_event:
                rider_results.append({
                    "event_name": event_name,
                    "event_date": event_date.date(),
                    "event_link": event_link,
                    "rider_rank": rank
                })

with open("points_cache.json", "r") as file:
    points_cache = json.load(file)
    file.close()

for event in rider_results:
    res = requests.get(event['event_link'])
    soup = BeautifulSoup(res.content, 'html.parser')
    ranking_table = soup.find("table", class_="rank-results")
    if ranking_table:
	    ranks = ranking_table.find_all(class_="rank")
	    number_competitors = len(ranks)

	    points_sum = 0
	    missed_riders = 0
	    for result in ranks:
	        cells = result.find_all("td")
	        athlete_profile = cells[1].find("a")['href']

	        if athlete_profile in points_cache.keys():
	            points_sum += points_cache[athlete_profile]
	        else:
	            res = requests.get("http://worldsnowboarding.org" + athlete_profile)
	            profile = BeautifulSoup(res.content, 'html.parser')

	            try:
	                ss_details = profile.find(id="result-table-points-list-ss").find_all("li")
	            except AttributeError:
	                ss_details = None
	                missed_riders += 1

	            if ss_details:
	                for i in ss_details:
	                    if "Current Points" in i.get_text().strip():
	                        profile_ss_points = float(i.find("strong").get_text())
	                        points_sum += profile_ss_points
	                        points_cache[athlete_profile] = profile_ss_points

	    counted_riders = number_competitors - missed_riders
	    points_average = round((points_sum / counted_riders),2)

	    event['event_competitors'] = number_competitors
	    event['points_average'] = points_average

with open("points_cache.json", "w") as file:
	json.dump(points_cache, file)
	file.close()

rider_results = [event for event in rider_results if 'event_competitors' in event.keys()]

for event in rider_results:
    event['rank_percentile'] = event['rider_rank'] / event['event_competitors']

for event in rider_results:
    months_passed = diff_month(event['event_date'])
    if months_passed <= 6:
        event['time_multiplier'] = 1
    elif months_passed <= 12:
        event['time_multiplier'] = 0.8
    elif months_passed <= 24:
        event['time_multiplier'] = 0.5
    elif months_passed <= 36:
        event['time_multiplier'] = 0.3
    else:
        event['time_multiplier'] = 0.1

weight_sum = 0
weighted_percentile_sum = 0

for event in rider_results:
    weighted_percentile_sum += (event['rank_percentile'] * event['time_multiplier'])
    weight_sum += event['time_multiplier']

time_weighted_average = weighted_percentile_sum / weight_sum
# print(time_weighted_average)

prediction1 = round(ce_number_competitors*time_weighted_average)
print(f"PREDICTION 1: {prediction1}. place")

for event in rider_results:
    average_wspl = event['points_average']
    deviation = abs((average_wspl / ce_points_average) * 100 - 100)
    if deviation <= 10:
        event['level_multiplier'] = 1
    else:
        event['level_multiplier'] = 0.5

weight_sum = 0
weighted_percentile_sum = 0

for event in rider_results:
    weighted_percentile_sum += (event['rank_percentile'] * event['level_multiplier'])
    weight_sum += event['level_multiplier']

level_weighted_average = weighted_percentile_sum / weight_sum

prediction2 = round(level_weighted_average * ce_number_competitors)
print(f"PREDICTION 2: {prediction2}. place")

weight_sum = 0
weighted_percentile_sum = 0

for event in rider_results:
    combined_multiplier = event['level_multiplier'] + event['time_multiplier']
    weighted_percentile_sum += (event['rank_percentile'] * combined_multiplier)
    weight_sum += combined_multiplier

combined_weighted_average = weighted_percentile_sum / weight_sum

prediction3 = round(combined_weighted_average * ce_number_competitors)
print(f"PREDICTION 3: {prediction3}. place")


















