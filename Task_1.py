import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests

api_key = 'f696bd9fb67ac5edcb6f259f7da62c79'  # Replace with your
api_access_token = 'eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJmNjk2YmQ5ZmI2N2FjNWVkY2I2ZjI1OWY3ZGE2MmM3OSIsIm5iZiI6MTc5MTI0MjI5MS45NDksInN1YiI6IjZhYzQzMDMzYTk0M2ZlMzIxMzJhNzE1ZSIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.ZkUKb6KYgZ18QmYKXek4Tm6NnZ9cyDFg5H9Bdh57mfA'  # Replace
api_url = 'https://api.themoviedb.org/3/search/person'

def get_director_name(title):
    params = {
        'api_key': api_key,
        'query': title
    }
    response = requests.get(api_url, params=params)
    print(f"Searching for director of '{title}' - Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if data['results']:
            return data['results'][0]['name']
    return "Not Given"

# Load the dataset
data = pd.read_csv('/workspaces/Netflix_auspify_intern/Data/Dataset.csv') 
df = pd.DataFrame(data)

def clean_data(df): 
    # remove duplicates by show_id
    df = df.drop_duplicates(subset='show_id', keep='first')
    df['show_id'] = df['show_id'].astype(str)

    # Type Mapping # no need to map the type column as it is already in string format 

    # remove duplicates by title and the same Director
    df = df.drop_duplicates(subset=['title', 'director'], keep='first')

    # country to string 
    df['country'] = df['country'].astype(str)

    # bounus if dirctor is "Not Given" Search for the director in Google and update the director column with the correct name. If not found, keep it as "Not Given". For now, we will just fill it with the first word of the title as a placeholder.

    director_name = df.apply(lambda row: get_director_name(row['title']) if row['director'] == 'Not Given' else row['director'], axis=1)
    df['director'] = director_name

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
cleaned_df.to_csv('/workspaces/Netflix_auspify_intern/Data/Cleaned_Dataset.csv', index=False)

#Auspify #AuspifyTechnologies
#AuspifyInternship #AuspifyProjects