import os
import pandas as pd
from sqlalchemy import create_engine, text

engine = create_engine('postgresql://neondb_owner:npg_Nadqtv9fIY5T@ep-purple-water-b4nn74mm-pooler.c-6.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require')



Cleaned_after = pd.read_csv('/workspaces/Netflix_auspify_intern/Cleaned_Dataset.csv')
print("Rows in CSV:", len(Cleaned_after))

def save_data_to_db(df, table_name):
    df = df.copy()
    print(f"Saving {len(df)} rows to {table_name}...")

    with engine.begin() as conn:   # opens a transaction and commits it at the end
        df.to_sql(
            table_name,
            conn,
            schema="public",
            if_exists="replace",
            index=False,
            chunksize=500,
            method="multi"
        )

save_data_to_db(Cleaned_after, "netflix_cleaned")
print("Finished.")