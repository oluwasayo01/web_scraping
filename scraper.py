import re
import time
from argparse import ArgumentParser
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver import ActionChains
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from bs4 import BeautifulSoup
import pandas as pd

# Argument parser to parse arguments supplied from the command line
parser = ArgumentParser()
parser.add_argument("--zip-code", type=int, required=True)
parser.add_argument("--radius", type=int, required=True)
parser.add_argument("--webdriver-path", type=str, default="/Users/oluwasayo/webdrivers/chromedriver")

args, _ = parser.parse_known_args()

# Radii slider steps as is on the website https://www.edmunds.com/cars-for-sale-by-owner/
predefined_radii = [10, 25, 50, 75, 100, 200, 500]

def extract_data(page):
    """
    Extracts the desired data from a selenium driver page source

    Args:
        page (bs4.BeautifulSoup): The Beautiful Soup page source from which data can be extracted.

    Returns:
        list
    """
    time.sleep(3)
    heading = page.find("div", attrs={"name": "overview"})
    details = page.find("div", attrs={"name": "details"})

    name = heading.section.h1.text #extracts the name from the nested element in the overview div
    price = page.find("span", attrs={"data-test": "vdp-price-row"}).text #extracts price
    vin = heading.find(string=re.compile("^VIN: ")).parent.text.replace("VIN: ", "").strip() #extracts vin number

    vehicle_summary = details.find("section", attrs={"class": "vehicle-summary"})
    features_and_specs = details.find("section", attrs={"class": "features-and-specs"})

    # Gets a list of vehicle summary
    summary = list(vehicle_summary.div.stripped_strings)

    features_dict = dict()
    # Appends the feature and specs to a dictionary
    for child in features_and_specs.div.children:
        features_dict[child.div.text] = list(child.div.next_sibling.stripped_strings)

    # A list of all extracted data
    results = [name, price, vin, summary[:-1], features_dict]
    return results


driver_path = args.webdriver_path

# create selenium webdriver object and navigate to website
driver = webdriver.Chrome(f'{driver_path}')
time.sleep(2)
driver.maximize_window()
driver.get("https://www.edmunds.com/cars-for-sale-by-owner/")

# find zip code input element and sends the zip code value entered in the command line
driver.find_element(By.XPATH, "/html/body/div[1]/div/main/div[3]/div[1]/div[2]/div/div[1]/div[2]/div[1]/div/div/input").send_keys(args.zip_code)

radius_index = 0
search_radius = args.radius

# Determine the corresponding index for the supplied radius
for index in range(len(predefined_radii)):
    if predefined_radii[index] < search_radius < predefined_radii[index+1]:
        left_gap = search_radius - predefined_radii[index]
        right_gap = predefined_radii[index+1] - search_radius
        radius_index = index + 1 if left_gap < right_gap else index + 2
        break
    elif search_radius < predefined_radii[0]:
        radius_index = 1
        break
    elif search_radius > predefined_radii[6]:
        radius_index = 7
        break

actions = ActionChains(driver)

# find the input element of the slider radius
source = driver.find_element(By.XPATH, "/html/body/div[1]/div/main/div[3]/div[1]/div[2]/div/div[1]/div[2]/div[2]/div/div[2]/input")
# find the position that matches a value close to the value supplied for the radius
target = driver.find_element(By.XPATH, f"/html/body/div[1]/div/main/div[3]/div[1]/div[2]/div/div[1]/div[2]/div[2]/div/div[3]/p[{radius_index}]")
# move the radius slider to the selected position
actions.drag_and_drop(source=source, target=target).perform()

time.sleep(5)
WebDriverWait(driver,100).until(EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div/main/div[3]/div[1]/div[1]/div/ul/li[1]/div")))

# An empty list to store extracted data
res = list()

# Loop through 21 cards on the first page of the results
number_of_cards_per_page = 21
for i in range(number_of_cards_per_page):
    try:
        page_action = ActionChains(driver)
        # Wait to detect the presence of card i + 1
        WebDriverWait(driver,10).until(EC.presence_of_element_located((By.XPATH, f"/html/body/div[1]/div/main/div[3]/div[1]/div[1]/div/ul/li[{i+1}]/div")))
        card = driver.find_element(By.XPATH, f"/html/body/div[1]/div/main/div[3]/div[1]/div[1]/div/ul/li[{i+1}]/div")
        if(i > 1 and i % 2 == 0):
            driver.execute_script("arguments[0].scrollIntoView();", card)
            time.sleep(5)
        
        elem = driver.find_element(By.XPATH, f"/html/body/div[1]/div/main/div[3]/div[1]/div[1]/div/ul/li[{i+1}]/div/div[2]/div/h2/a")
        # move to card i + 1 and click on it
        page_action.move_to_element(to_element=elem).pause(3).click().perform()
        # Extract the page source on the resulting details page of clicking card i + 1
        page_source = BeautifulSoup(driver.page_source, "html.parser")
        # Extract data and append to the res list
        res.append(extract_data(page_source))
        driver.back()
        driver.implicitly_wait(3)
    except AttributeError:
        driver.back()
        pass
    except (NoSuchElementException, TimeoutException):
        break

time.sleep(2)
driver.close()
columns = ["Name", "Price", "VIN", "Vehicle Summary", "Top Features & Specs"]

# Supply array of extracted data to pandas dataframe
dataframe = pd.DataFrame(res, columns=columns)
print(dataframe)
# convert dataframe to excel format
dataframe.to_excel("edmunds.xlsx", sheet_name="Cars", index=False)
