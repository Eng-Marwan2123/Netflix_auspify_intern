import os
import time
import uuid
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ---------------- ENVIRONMENT ----------------
# ---------------- ENVIRONMENT ----------------
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

from dotenv import dotenv_values

env_values = dotenv_values(ENV_FILE)
DATABASE_URL = env_values.get("postgresql://neondb_owner:npg_Nadqtv9fIY5T@ep-purple-water-b4nn74mm-pooler.c-6.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require")

print("ENV file exists:", ENV_FILE.is_file())
print("DATABASE_URL found in file:", bool(DATABASE_URL))

if not DATABASE_URL:
    raise ValueError(f"DATABASE_URL is missing or empty in {ENV_FILE}")

# ---------------- SETTINGS ----------------
DATA_TABLE = "netflix_cleaned"

THRESHOLD = 55

WEIGHTS = {
    "category": 35,
    "language": 20,
    "country": 15,
    "star": 10,
    "director": 10,
    "rating": 5,
    "type": 5
}

EXTRA_MAX = (
    WEIGHTS["star"]
    + WEIGHTS["director"]
    + WEIGHTS["rating"]
    + WEIGHTS["type"]
)


# ---------------- DATABASE ----------------
def connect_db():
    if not DATABASE_URL:
        raise ValueError(
            "DATABASE_URL is not set. "
            f"Check your .env file at: {BASE_DIR / '.env'}"
        )

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True
    )

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        print("Database connection successful.")
        return engine

    except Exception:
        engine.dispose()
        raise


def load_data(engine):
    df = pd.read_sql_table(DATA_TABLE, engine)

    if df.empty:
        raise ValueError(
            f"The table '{DATA_TABLE}' contains no data."
        )

    print(f"Loaded {len(df)} rows from '{DATA_TABLE}'.")

    return df


# ---------------- SIMPLE CLEANING ----------------
def clean_text(value):
    if pd.isna(value):
        return ""

    value = str(value).strip().lower()

    if value in ["", "nan", "none", "not given"]:
        return ""

    return value


def as_set(value):
    value = clean_text(value)

    if not value:
        return set()

    return {
        part.strip()
        for part in value.split(",")
        if part.strip()
    }


def get_value(row, column):
    if column not in row.index:
        return ""

    return clean_text(row[column])


def get_length(value):
    value = clean_text(value)

    try:
        return int(value.split()[0])
    except (ValueError, IndexError):
        return None


# ---------------- BUILD TITLE PROFILE ----------------
def make_profile(row):
    return {
        "category": as_set(row.get("listed_in", "")),
        "country": as_set(row.get("country", "")),
        "language": get_value(row, "language"),
        "star": as_set(row.get("star", "")),
        "director": as_set(row.get("director", "")),
        "rating": get_value(row, "rating"),
        "type": get_value(row, "type"),
        "length": get_length(row.get("duration", ""))
    }


# ---------------- FIND THE TITLE ----------------
def find_title(df, title):
    titles = (
        df["title"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    search = title.strip().lower()

    if not search:
        return None

    # Exact match first
    exact = df.index[titles == search]

    if len(exact):
        return exact[0]

    # Partial match second
    partial = df.index[
        titles.str.contains(search, regex=False)
    ]

    if len(partial):
        match_index = partial[0]

        print(
            f"Using closest match: "
            f"{df.loc[match_index, 'title']}"
        )

        return match_index

    return None


# ---------------- KPI SCORING ----------------
def overlap_score(user_values, candidate_values):
    if not user_values:
        return 0

    return (
        len(user_values & candidate_values)
        / len(user_values)
    )


def extra_score(user, candidate):
    score = 0

    # Matching cast / stars: 10 points
    if user["star"] and user["star"] & candidate["star"]:
        score += WEIGHTS["star"]

    # Matching director: 10 points
    if (
        user["director"]
        and user["director"] & candidate["director"]
    ):
        score += WEIGHTS["director"]

    # Matching rating: 5 points
    if (
        user["rating"]
        and user["rating"] == candidate["rating"]
    ):
        score += WEIGHTS["rating"]

    # Matching type and similar duration: 5 points
    if user["type"] and user["type"] == candidate["type"]:

        if (
            user["length"] is not None
            and candidate["length"] is not None
        ):
            tolerance = (
                30 if user["type"] == "movie" else 2
            )

            if (
                abs(
                    user["length"] - candidate["length"]
                ) <= tolerance
            ):
                score += WEIGHTS["type"]

    return score


def core_score(user, candidate):

    # Category similarity: maximum 35 points
    category_points = WEIGHTS["category"] * overlap_score(
        user["category"],
        candidate["category"]
    )

    # Language similarity: maximum 20 points
    language_points = 0

    if (
        user["language"]
        and user["language"] == candidate["language"]
    ):
        language_points = WEIGHTS["language"]

    # Country similarity: maximum 15 points
    country_points = WEIGHTS["country"] * overlap_score(
        user["country"],
        candidate["country"]
    )

    return (
        category_points
        + language_points
        + country_points
    )


# ---------------- RECOMMENDATION ENGINE ----------------
def recommend(df, profiles, selected_index):

    user_profile = profiles[selected_index]

    candidates = []

    # Calculate core scores for all other titles
    for index, candidate in enumerate(profiles):

        if index == selected_index:
            continue

        score = core_score(user_profile, candidate)

        candidates.append((score, index))

    # Sort candidates by core score
    candidates.sort(
        key=lambda item: item[0],
        reverse=True
    )

    results = []
    rows_scored = 0

    for core, index in candidates:

        # Stop when the remaining candidates cannot reach
        # the threshold, even with all extra points.
        if core + EXTRA_MAX < THRESHOLD:
            break

        rows_scored += 1

        score = core + extra_score(
            user_profile,
            profiles[index]
        )

        if score >= THRESHOLD:
            results.append((score, index))

    # Sort by final recommendation score
    results.sort(
        key=lambda item: item[0],
        reverse=True
    )

    # Prepare output and avoid duplicate titles
    output = []

    seen_titles = {
        clean_text(df.loc[selected_index, "title"])
    }

    for score, index in results:

        title = str(df.loc[index, "title"])
        normalized_title = clean_text(title)

        if normalized_title in seen_titles:
            continue

        seen_titles.add(normalized_title)

        output.append({
            "title": title,
            "type": df.loc[index].get("type", ""),
            "listed_in": df.loc[index].get(
                "listed_in", ""
            ),
            "score": round(score, 2)
        })

        # Return only the top 10
        if len(output) == 10:
            break

    recommendations = pd.DataFrame(
        output,
        columns=[
            "title",
            "type",
            "listed_in",
            "score"
        ]
    )

    return recommendations, rows_scored


# ---------------- SAVE RUN LOGS ----------------
def save_logs(
    engine,
    run_id,
    user_name,
    input_title,
    runtime,
    rows_scored,
    recommendations
):

    # Save the main run log
    run_log = pd.DataFrame([{
        "run_id": run_id,
        "user_name": user_name,
        "input_title": input_title,
        "run_time": pd.Timestamp.now(),
        "runtime_seconds": runtime,
        "rows_scored": rows_scored,
        "recommendation_count": len(recommendations)
    }])

    run_log.to_sql(
        "recommendation_run_logs",
        engine,
        if_exists="append",
        index=False
    )

    # Save individual recommendation results
    if not recommendations.empty:

        recommendation_log = recommendations.copy()

        recommendation_log.insert(0, "run_id", run_id)
        recommendation_log.insert(
            1, "user_name", user_name
        )
        recommendation_log.insert(
            2, "input_title", input_title
        )

        recommendation_log.to_sql(
            "recommendation_results_logs",
            engine,
            if_exists="append",
            index=False
        )


# ---------------- RUN THE PROGRAM ----------------
def main():

    start = time.perf_counter()
    engine = None

    try:
        # Connect to Neon PostgreSQL
        engine = connect_db()

        # Load the Netflix dataset
        df = load_data(engine)

        # Validate required column
        if "title" not in df.columns:
            raise ValueError(
                "The database table must contain "
                "a 'title' column."
            )

        # Collect user information
        user_name = input(
            "Enter your name: "
        ).strip()

        if not user_name:
            user_name = "Unknown user"

        movie_name = input(
            "Enter a movie or TV show you like: "
        ).strip()

        if not movie_name:
            print("A movie or TV show title is required.")
            return

        # Find the selected title
        selected_index = find_title(df, movie_name)

        if selected_index is None:
            print("Title not found in the dataset.")
            return

        # Build profiles
        print("\nPreparing title profiles...")

        profiles = [
            make_profile(row)
            for _, row in df.iterrows()
        ]

        # Generate recommendations
        recommendations, rows_scored = recommend(
            df,
            profiles,
            selected_index
        )

        runtime = time.perf_counter() - start

        selected_title = str(
            df.loc[selected_index, "title"]
        )

        # Display recommendations
        print(
            f"\nRecommendations for: {selected_title}"
        )

        print(
            f"Minimum score threshold: {THRESHOLD}/100"
        )

        if recommendations.empty:

            print(
                f"No recommendations reached "
                f"the {THRESHOLD}-point threshold."
            )

        else:

            print(
                recommendations.to_string(index=False)
            )

        # Save logs to PostgreSQL
        run_id = str(uuid.uuid4())

        save_logs(
            engine=engine,
            run_id=run_id,
            user_name=user_name,
            input_title=selected_title,
            runtime=runtime,
            rows_scored=rows_scored,
            recommendations=recommendations
        )

        # Display performance metrics
        print("\n--------------- PERFORMANCE ---------------")

        print(f"Run ID: {run_id}")
        print(f"Rows fully scored: {rows_scored}")

        print(
            f"Recommendations returned: "
            f"{len(recommendations)}"
        )

        print(f"Runtime: {runtime:.4f} seconds")

        print("Run and recommendation logs saved successfully.")

    except Exception as e:
        print(f"\nAn error occurred: {e}")

    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
