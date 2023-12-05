from __future__ import annotations

import logging
import math
import sys
from datetime import datetime
from os.path import abspath, dirname
from typing import TYPE_CHECKING, Union

import numpy as np
import pandas as pd
from src.data.dataframes import Form, HomeAdvantages, TeamRatings

# Temp avoid circular import
if TYPE_CHECKING:
    from src.data.dataframes import Upcoming

# Required to access database module in parent folder
sys.path.append(dirname(dirname(dirname(dirname(abspath(__file__))))))

from database import Database


class Predictor:
    @staticmethod
    def _game_xg(
        team: str,
        goals: float,
        opp_team: str,
        home_advantage: float,
        team_ratings: TeamRatings,
    ):
        xg = goals
        # Scale by home advantage recieved by the home team
        xg *= 1 + home_advantage
        # Scale by strength of opposition team
        opp_team_rating = 0
        if opp_team in team_ratings.df.index:
            opp_team_rating = team_ratings.df.at[opp_team, "totalRating"]
        xg *= 1 + team_ratings.df.at[team, "totalRating"] - opp_team_rating

        return xg

    def _prev_match_xg(
        self,
        team: str,
        prev_matches: list[dict],
        team_ratings: TeamRatings,
        home_advantages: HomeAdvantages,
    ):
        xgs = []
        for prev_match in prev_matches:
            home_advantage = 0
            if prev_match["homeTeam"] in home_advantages.df.index:
                home_advantage = home_advantages.df.loc[
                    prev_match["homeTeam"], "totalHomeAdvantage"
                ][0]
            if team == prev_match["homeTeam"]:
                xg = self._game_xg(
                    team,
                    prev_match["homeGoals"],
                    prev_match["awayTeam"],
                    home_advantage,
                    team_ratings,
                )
            elif team == prev_match["awayTeam"]:
                xg = self._game_xg(
                    team,
                    prev_match["awayGoals"],
                    prev_match["homeTeam"],
                    -home_advantage,
                    team_ratings,
                )
            xgs.append(xg)

        team_xg = np.mean(xgs)
        return team_xg

    @staticmethod
    def _team_prev_matches(team: str, form: Form):
        prev_matches: list[dict] = []
        for season, matchday in form.df.droplevel(2, axis=1).columns.values:
            score = form.df.at[team, (season, matchday, "score")]
            if isinstance(score, dict):
                if form.df.at[team, (season, matchday, "atHome")]:
                    home_team = team
                    away_team = form.df.at[team, (season, matchday, "team")]
                else:
                    home_team = form.df.at[team, (season, matchday, "team")]
                    away_team = team
                prev_match = {
                    "homeTeam": home_team,
                    "awayTeam": away_team,
                    "homeGoals": score["homeGoals"],
                    "awayGoals": score["awayGoals"],
                }
                prev_matches.append(prev_match)

        return prev_matches

    @staticmethod
    def _combine_xgs(total_xg: float, prev_match_xg: float, prev_match_weight: float):
        xg = total_xg
        if not math.isnan(prev_match_xg):
            xg = (prev_match_xg * prev_match_weight + total_xg) / (
                1 + prev_match_weight
            )
        return xg

    def _score_prediction(
        self,
        team: str,
        upcoming: Upcoming,
        form: Form,
        team_ratings: TeamRatings,
        home_advantages: HomeAdvantages,
    ):
        at_home = upcoming.at[team, "atHome"]
        if at_home:
            home_team = team
            away_team = upcoming.at[home_team, "nextTeam"]
        else:
            away_team = team
            home_team = upcoming.at[away_team, "nextTeam"]

        # xG from prev matches between these two teams
        prev_matches = upcoming.at[team, "prevMatches"]
        home_prev_match_xg = self._prev_match_xg(
            home_team, prev_matches, team_ratings, home_advantages
        )
        away_prev_match_xg = self._prev_match_xg(
            away_team, prev_matches, team_ratings, home_advantages
        )

        # xG from all recorded matches for each team
        home_team_matches = self._team_prev_matches(home_team, form)
        away_team_matches = self._team_prev_matches(away_team, form)
        home_total_xg = self._prev_match_xg(
            home_team, home_team_matches, team_ratings, home_advantages
        )
        away_total_xg = self._prev_match_xg(
            away_team, away_team_matches, team_ratings, home_advantages
        )

        # Combine both xG measures to give a final xG
        home_goals = self._combine_xgs(
            home_total_xg, home_prev_match_xg, len(prev_matches) / 6
        )
        away_goals = self._combine_xgs(
            away_total_xg, away_prev_match_xg, len(prev_matches) / 6
        )

        logging.info(
            f"🔮 Prediction: {home_team} {round(home_goals, 2)} - {round(away_goals, 2)} {away_team}"
        )

        return home_goals, away_goals

    def score_predictions(
        self,
        form: Form,
        upcoming: Upcoming,
        team_ratings: TeamRatings,
        home_advantages: HomeAdvantages,
    ):
        predictions: dict[dict[str, Union[datetime, str, float]]] = {}
        team_names = form.df.index.values.tolist()

        # Check ALL teams as two teams can have different next games
        for team_name in team_names:
            prediction = None
            if upcoming is not None:
                home_goals, away_goals = self._score_prediction(
                    team_name, upcoming, form, team_ratings, home_advantages
                )

                prediction = {
                    "homeGoals": round(home_goals, 4),
                    "awayGoals": round(away_goals, 4),
                }

            predictions[team_name] = prediction

        return predictions


class Predictions:
    def __init__(self, current_season: int):
        self.predictor = Predictor()
        self.database = Database(current_season)
        self.prediction_file = f"data/predictions_{current_season}.json"

    @staticmethod
    def _predictions_to_df(predictions: dict[str, dict[str, float]]):
        d = {}
        for team, prediction in predictions.items():
            d[team] = {
                ("prediction", goals_type): goals
                for goals_type, goals in prediction.items()
            }

        df = pd.DataFrame.from_dict(d, orient="index")
        return df

    def build(
        self,
        form: Form,
        upcoming: Upcoming,
        team_ratings: TeamRatings,
        home_advantages: HomeAdvantages,
    ):
        predictions = self.predictor.score_predictions(
            form, upcoming, team_ratings, home_advantages
        )
        upcoming_predictions = self._predictions_to_df(predictions)
        return upcoming_predictions
