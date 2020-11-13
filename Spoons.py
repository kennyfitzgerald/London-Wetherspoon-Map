##############
# Libraries  #
##############

import os
import re
import time
import pandas as pd
import numpy as np
import geopandas as gp
import matplotlib.pyplot as plt
from selenium import webdriver 
from adjustText import adjust_text

#########################
# Set working directory #
#########################

os.chdir('C:\\USERS\\KFITZ\\DOCUMENTS\\PYTHON PROJECTS\\WETHERSPOON')

############################
# Import required datasets #
############################

# London borough code mapping
BoroughCodes = pd.read_csv('london-borough-profiles.csv', encoding = 'unicode_escape')

# Keeping only relevant columns 
BoroughCodes = BoroughCodes[['Code', 'Area_name', 'GLA_Population_Estimate_2017']]

# And london postcodes with borough codes
LondonPostcodes = pd.read_csv('london_postcodes-ons-postcodes-directory-MAY20.csv',
                              encoding = 'unicode_escape')

# Filtering relevant columns 
LondonPostcodes = LondonPostcodes[['pcd', 'oslaua', 'lat', 'long']] 

# Mapping file for borough boundaries
map = gp.read_file("borough boundaries/London_Borough_Excluding_MHW.shp")

######################################
# Extract wetherspoon data from site #
######################################

driver = webdriver.Chrome("C:/Users/kfitz/.conda/chromedriver.exe")

driver.get("https://www.jdwetherspoon.com/pubs/all-pubs")

time.sleep(10)

SpoonsWE = driver.find_element_by_id(id_="angularResults")

Spoons = str(SpoonsWE.text)

Spoons = Spoons.splitlines()[2:]

def SymbolToFront(string, symbol):
    
    SplitString = re.split('(' + symbol + ')', string)
    
    if(len(SplitString) == 1):
        return(string)
    else:
        NewString = SplitString[1] + ' ' + string.replace(symbol, '')
        NewString = re.sub("\s\s+", " ", NewString)
        return(NewString)


SpoonsList = map(lambda x : SymbolToFront(x, symbol = '>'), Spoons)

SpoonsList = list(SpoonsList)

Wetherspoon = pd.DataFrame(SpoonsList, columns = ['All'])

Wetherspoon['Grouping'] = np.cumsum(np.where(Wetherspoon['All'].str[0] == '>', 1, 0))

Wetherspoon['All'] = Wetherspoon['All'].str.strip('> ')

Wetherspoon['LineCount'] = Wetherspoon.groupby('Grouping', as_index=False).cumcount()+1

Wetherspoon['Region'] = np.where((Wetherspoon.LineCount == 4) | (Wetherspoon.LineCount == 5), Wetherspoon.All, None)

Wetherspoon['Region'][0] = Wetherspoon['All'][0]

Wetherspoon['Region'] = Wetherspoon['Region'].fillna(method='ffill')

Wetherspoon = Wetherspoon[~Wetherspoon.LineCount.isin([4, 5])]

Wetherspoon = Wetherspoon.drop(0)

Wetherspoon['Label'] = np.select(
    [
        Wetherspoon['LineCount'] == 1, 
        Wetherspoon['LineCount'] == 2,
        Wetherspoon['LineCount'] == 3
    ], 
    [
        'Name', 
        'Address',
        'Postcode'
    ], 
    default='Unknown'
)


Wetherspoon = Wetherspoon.pivot_table(index = ['Region', 'Grouping'], 
                                      columns='Label',
                                      values='All',
                                      fill_value=0,
                                      aggfunc = 'first')


Wetherspoon['new'] = Wetherspoon.Postcode.str.split()

Wetherspoon = Wetherspoon[Wetherspoon.new.map(len)>2]

Wetherspoon['Postcode'] = Wetherspoon.new.str[-2:]

Wetherspoon['Postcode'] = [' '.join(map(str, l)) for l in Wetherspoon['Postcode']]

Wetherspoon['Town'] = Wetherspoon.new.str[:-2]

Wetherspoon['Town'] = [' '.join(map(str, l)) for l in Wetherspoon['Town']]

# Selecting final columns for wetherspoon data

Wetherspoon = Wetherspoon.reset_index()

Wetherspoon = Wetherspoon[['Name', 'Address', 'Town', 'Region', 'Postcode']]


#################################
# Preparing London borough data #
#################################

# Rename columns

LondonPostcodes = LondonPostcodes.rename(columns = {'pcd':'PostcodeJoin', 
                                                    'oslaua':'BoroughCode',
                                                    'lat' : 'Latitude',
                                                    'long': 'Longitude'})

BoroughCodes = BoroughCodes.rename(columns = {'Code':'BoroughCode', 
                                              'Area_name':'LondonBorough',
                                              'GLA_Population_Estimate_2017':'Population'})

# Joining london borough codes to postcode dataframe

LondonPostcodes = pd.merge(LondonPostcodes, 
                           BoroughCodes,
                           on = 'BoroughCode')

# Preparing columns for join by removing white spaces from postcodes

LondonPostcodes['PostcodeJoin'] = LondonPostcodes['PostcodeJoin'].str.replace(' ', '')

Wetherspoon['PostcodeJoin'] = Wetherspoon['Postcode'].str.replace(' ', '')

# Joining london boroughs to postcodes 

Wetherspoon = pd.merge(Wetherspoon, 
                       LondonPostcodes, 
                       left_on='PostcodeJoin',
                       right_on='PostcodeJoin')

# Retaining only relevant columns 

Wetherspoon = Wetherspoon[['Name', 'Address', 'Town', 'Region', 'Postcode', 
                           'Latitude', 'Longitude', 'LondonBorough', 'Population']]

# Dropping duplicate pubs (By postcode)

Wetherspoon = Wetherspoon.drop_duplicates(subset="Postcode").reset_index()

#######################
### Mapping  Points ###
#######################

map.crs = 'EPSG:27700'

map = map.to_crs("EPSG:4326")

LondonPlot = map.plot(color='white', edgecolor='black', linewidth=0.8,
                      figsize = (80, 80))

SpoonsPoints = gp.GeoDataFrame(Wetherspoon, geometry=gp.points_from_xy(
    Wetherspoon.Longitude, 
    Wetherspoon.Latitude))

SpoonsPoints.crs = 'EPSG:4326'

SpoonsPoints = SpoonsPoints.to_crs(map.crs)

plot1 = SpoonsPoints.plot(ax=LondonPlot, color='red', marker = 'o', markersize = 10)

plot1 = LondonPlot.axis('off')

# for x, y, label in zip(SpoonsPoints.geometry.x, SpoonsPoints.geometry.y, SpoonsPoints.Name):
#     LondonPlot.annotate(label, xy=(x, y), xytext=(3, 3), textcoords="offset points")

texts = [plt.text(SpoonsPoints.geometry.x[i], SpoonsPoints.geometry.y[i], SpoonsPoints.Name[i]) for i in range(len(SpoonsPoints.geometry.x))]

adjust_text(texts)

plt.savefig("London Wetherspoon Map.svg")



