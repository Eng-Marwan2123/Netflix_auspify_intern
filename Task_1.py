import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests
from sqlalchemy import create_engine, text

# Put your NEW key in an environment variable, never in the code:
#   export TMDB_API_KEY="your_new_v3_api_key"
api_key = 'f696bd9fb67ac5edcb6f259f7da62c79'
api_url = 'https://api.themoviedb.org/3'
engine = create_engine("postgresql+psycopg://neondb_owner:npg_L78TmfsVoiWY@ep-damp-rice-zapgu6fx-pooler.c-2.eu-west-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require")


from sqlalchemy import create_engine, text
import pandas as pd
# ==========================================================
# LOAD DATA based on the provided paths
# after collect in the data from the cSV files, we will save the data in the PostgreSQL database (Neon)
# ==========================================================


    print(f"Data saved to {table_name} successfully!")

cache = {}  # so each title is searched only once

def get_details(title, content_type, year):
    # Movie -> /movie, TV Show -> /tv
    kind = 'movie' if content_type == 'Movie' else 'tv'
    key = (title, kind, year)
    if key in cache:
        return cache[key]

    details = None
    params = {'api_key': api_key, 'query': title}
    response = requests.get(f"{api_url}/search/{kind}", params=params)
    print(f"Searching for '{title}' - Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if data['results']:
            tmdb_id = data['results'][0]['id']
            # one call gives the details + the credits (cast and crew)
            params = {'api_key': api_key, 'append_to_response': 'credits'}
            response = requests.get(f"{api_url}/{kind}/{tmdb_id}", params=params)
            if response.status_code == 200:
                details = response.json()

    cache[key] = details
    return details

def get_director_name(title, content_type, year):
    details = get_details(title, content_type, year)
    if details:
        for person in details['credits']['crew']:
            if person['job'] == 'Director':
                return person['name']
        # TV shows usually have no director, so use the creator
        if details.get('created_by'):
            return details['created_by'][0]['name']
    return "Not Given"

def Add_star(title, content_type, year):
    details = get_details(title, content_type, year)
    if details and details['credits']['cast']:
        return details['credits']['cast'][0]['name']  # first billed actor
    return "Not Given"

def language(title, content_type, year):
    details = get_details(title, content_type, year)
    if details and details.get('original_language'):
        return details['original_language']
    return "Not Given"


# Load the dataset
data = pd.read_csv('/workspaces/Netflix_auspify_intern/Dataset.csv')
df = pd.DataFrame(data)

def clean_data(df):
    # remove duplicates by show_id
    df = df.drop_duplicates(subset='show_id', keep='first').copy()
    df['show_id'] = df['show_id'].astype(str)

    # Type Mapping # no need to map the type column as it is already in string format

    # remove duplicates by title and the same Director
    df = df.drop_duplicates(subset=['title', 'director'], keep='first')

    # country to string
    df['country'] = df['country'].astype(str)

    # bonus: if director is "Not Given" search TMDB for the director. If not found, keep it as "Not Given".
    director_name = df.apply(lambda row: get_director_name(row['title'], row['type'], row['release_year']) if row['director'] == 'Not Given' else row['director'], axis=1)
    df['director'] = director_name

    # Task 3: add the Star and Language columns (they are not in the dataset)
    df['star'] = df.apply(lambda row: Add_star(row['title'], row['type'], row['release_year']), axis=1)
    df['language'] = df.apply(lambda row: language(row['title'], row['type'], row['release_year']), axis=1)

    # Convert the 'date_added' column to datetime format
    df['date_added'] = pd.to_datetime(df['date_added'], errors='coerce')

    #release_year to int
    df['release_year'] = df['release_year'].astype(int)

    # Rating to string
    df['rating'] = df['rating'].astype(str)

    #Duration to string
    df['duration'] = df['duration'].astype(str)

    #listed_in to string
    df['listed_in'] = df['listed_in'].astype(str)

    return df

cleaned_df = clean_data(df)


print(cleaned_df.head())
cleaned_df.to_csv('/workspaces/Netflix_auspify_intern/Cleaned_Dataset.csv', index=False)
#push to Data base
