import pandas as pd
import numpy as np

df = pd.read_csv("app/data/kp_1220.csv")

df["Offense"] = pd.to_numeric(df["ORtg"], errors = 'coerce')
df["Defense"] = pd.to_numeric(df["DRtg"], errors = 'coerce')
df["Poss"] = pd.to_numeric(df["AdjT"], errors = 'coerce')

def exp_poss(home, away):
    if (df.loc[df['Team'] == home, 'Poss'].iloc[0] < 69) & (df.loc[df['Team'] == away, 'Poss'].iloc[0] < 69):
        return 69 - (69 - df.loc[df['Team'] == home, 'Poss'].iloc[0]) - (69 - df.loc[df['Team'] == away, 'Poss'].iloc[0])
    if (df.loc[df['Team'] == home, 'Poss'].iloc[0] > 69) & (df.loc[df['Team'] == away, 'Poss'].iloc[0] > 69):
        return 69 + (df.loc[df['Team'] == home, 'Poss'].iloc[0] - 69) + (df.loc[df['Team'] == away, 'Poss'].iloc[0] - 69)
    else:
        return (df.loc[df['Team'] == home, 'Poss'].iloc[0] + df.loc[df['Team'] == away, 'Poss'].iloc[0]) / 2
    
def predict_score(home, away, home_court):
    exponent = 2.5
    points_multiplier = 0.86

    home_scaled_off = (df.loc[df['Team'] == home, 'Offense'].iloc[0] / 100) ** exponent * exp_poss(home, away)
    away_scaled_off = (df.loc[df['Team'] == away, 'Offense'].iloc[0] / 100) ** exponent * exp_poss(home, away)
    home_scaled_def = (df.loc[df['Team'] == home, 'Defense'].iloc[0] / 100) ** exponent * exp_poss(home, away)
    away_scaled_def = (df.loc[df['Team'] == away, 'Defense'].iloc[0] / 100) ** exponent * exp_poss(home, away)

    if home_court == True:
        home_points = round((home_scaled_off + away_scaled_def)/2 * points_multiplier + 2, 2)
        away_points = round((away_scaled_off + home_scaled_def)/2 * points_multiplier - 2, 2)
    else:
        home_points = round((home_scaled_off + away_scaled_def)/2 * points_multiplier, 2)
        away_points = round((away_scaled_off + home_scaled_def)/2 * points_multiplier, 2)
    
    home_margin = round((home_points - away_points),2)
    away_margin = round((away_points - home_points),2)
    exp_total = round(home_points + away_points,2)

    if home_points >= away_points:
        return (f"{home} {home_points} - {away} {away_points} | Margin: {home_margin:.1f} | Total : {exp_total}")
    else:
        return (f"{away} {away_points} - {home} {home_points} | Margin: {abs(away_margin):.1f} | Total : {exp_total}")


    