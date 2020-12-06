from graph_data import GraphData
import pandas as pd
from collections import deque
from timebudget import timebudget
import numpy as np
import requests
import json
from datetime import datetime


class Data:
    url = "https://api.football-data.org/v2/"
    api = "f6cead2f1c47791235586c2887a3e624599b62862b339749cfc0b10fcc83167c"
    headers = {'X-Auth-Token': 'cb159edc83824c21b6704e7ca18c2920'}

    def __init__(self, current_season):
        self.season = current_season
        
        # Number of games played in a season for season data to be used
        self.games_threshold = 4
        self.home_games_threshold = 5
        self.star_team_threshold = 75
                        
        # List of current season teams, updated when updating standings 
        self.team_names = None  
        
        # Dataframes to build
        self.fixtures = pd.DataFrame()
        self.standings = pd.DataFrame()
        self.team_ratings = pd.DataFrame()
        self.home_advantages = pd.DataFrame()
        self.form = pd.DataFrame()
        self.position_over_time = pd.DataFrame()
        
        self.name_to_initials = {
            'Brighton and Hove Albion FC': 'BHA',
            'West Ham United FC': 'WHU',
            'Manchester City FC': 'MCI',
            'Manchester United FC': 'MUN',
            'Sheffield United FC': 'SHU',
            'Aston Villa FC': 'AVL',
            'West Bromwich Albion FC': 'WBA',
        }
        self.initials_to_name = {
            'ARS': 'Arsenal FC',
            'AVL': 'Aston Villa FC',
            'BHA': 'Brighton and Hove Albion FC',
            'BUR': 'Burnley FC',
            'CHE': 'Chelsea FC',
            'CRY': 'Crystal Palace FC',
            'EVE': 'Everton FC',
            'FUL': 'Fulham FC',
            'LEE': 'Leeds United FC',
            'LEI': 'Leicester City FC',
            'LIV': 'Liverpool FC',
            'MCI': 'Manchester City FC',
            'MUN': 'Manchester United FC',
            'NEW': 'Newcastle United FC',
            'SHU': 'Sheffield United FC',
            'SOU': 'Southampton FC',
            'TOT': 'Tottenham Hotspur FC',
            'WBA': 'West Bromwich Albion FC',
            'WHU': 'West Ham United FC',
            'WOL': 'Wolverhampton Wanderers FC',
            
        }
    
    def getCurrentMatchday(self):
        # Returns "Matchday X"
        return list(self.form.columns.unique(level=0))[-1]

    
    # -------- Functions for loading pages ------------
    # Functions that are called inside Flask page load functions
    # Returns data to used to display information on webpage
    # All require dataframes to be filled first
    def getPosition(self, team_name):
        return self.standings.loc[team_name, f'{self.season}']['Position']

    def getForm(self, team_name):
        latest_matchday = self.getCurrentMatchday()
        form = self.form[latest_matchday].loc[team_name]['Form']
        
        # If team hasn't yet played in current matchday, use previous matchday's form
        if len(form) != 5:
            previous_matchday = list(self.form.columns.unique(level=0))[-2]
            form = self.form[previous_matchday].loc[team_name]['Form']
        
        if form == None:
            form = []
        else:
            form = list(form.replace(',', ''))
        form = form + ['None'] * (5 - len(form))  # Pad list
        return form

    def getRecentTeamsPlayed(self, team_name):
        latest_matchday = self.getCurrentMatchday()
        latest_teams_played = self.form[latest_matchday].loc[team_name]['Teams Played']
        
        if len(latest_teams_played) == 5:
            # If team has already played this game week
            return latest_teams_played
        else:
            # Use previous matchday's games played list
            previous_matchday = list(self.form.columns.unique(level=0))[-2]
            return self.form[previous_matchday].loc[team_name]['Teams Played']
    
    def getCurrentFormRating(self, team_name):
        matchday = self.getCurrentMatchday()# Latest matchday
        latest_teams_played = self.form[matchday].loc[team_name]['Teams Played']
        
        # If team hasn't yet played this matchday use previous matchday data
        if len(latest_teams_played) != 5:
            matchday = list(self.form.columns.unique(level=0))[-2]
        
        return self.form[matchday].loc[team_name]['Form Rating %'].round(1)
    
    def getWonAgainstStarTeam(self, team_name):
        latest_matchday = self.getCurrentMatchday()
        won_against_star_team = self.form[latest_matchday].loc[team_name]['Won Against Star Team']
        
        # If team hasn't yet played this matchday use previous matchday data
        if len(won_against_star_team) != 5:
            previous_matchday = list(self.form.columns.unique(level=0))[-2]
            won_against_star_team = self.form[previous_matchday].loc[team_name]['Won Against Star Team']
            
        # Replace boolean values with CSS tag for super win image
        won_against_star_team = ["star-team" if x else "not-star-team" for x in won_against_star_team]
        return won_against_star_team
    
    def getTableSnippet(self, team_name):
        team_df_idx = self.standings.index.get_loc(team_name)
        
        # Get range of table the snippet should cover
        # Typically 3 teams below + 3 teams above, unless near either end of the table
        low_idx = team_df_idx-3
        high_idx = team_df_idx+4
        if low_idx < 0:
            # Add overflow amount to the high_idx to ensure 7 teams 
            overflow = low_idx
            high_idx -= low_idx  # Subtracting a negative
            low_idx = 0
        if high_idx > self.standings.shape[0] - 1:
            # Subtract overflow amount from the low_idx to ensure 7 teams
            overflow = high_idx - (self.standings.shape[0])
            low_idx -= overflow
            high_idx = self.standings.shape[0]
            
        rows = self.standings.iloc[low_idx:high_idx]
        team_names = rows.index.values.tolist()
        # Remove 'FC' from end of each team name (nicer to display)
        team_names = list(map(lambda name: ' '.join(name.split(' ')[:-1]), team_names))
        # Get new index of this team, relative to section of rows dataframe
        team_idx = rows.index.get_loc(team_name)

        # Only keep relevant columns
        rows = rows[f'{self.season}'][['Position', 'GD', 'Points']]
        
        # List of table rows: [ [pos, name, gd, points] ... ]
        table_snippet = rows.values.tolist()
        # Add the team name into position 1 of each table row
        for row_list, team_name in zip(table_snippet, team_names):
            row_list.insert(1, team_name)
            
        # Make CSS styles lists for team row background colour
        # table_css_styles = [''] * 7
        # Make current team the table focus when using css styles 
        # table_css_styles[team_idx] = f"this-team var(--{team_names[team_idx].lower().replace(' ', '-')})"
            
        return table_snippet, team_idx

    def getNextTeamToPlay(self, team_name):
        team_name = self.next_games['Next Game'].loc[team_name]
        return team_name
    
    
    
    # ---------------------- Next games dataframe ---------------------------
    
    def createNextGames(self, display=False):
        if self.fixtures.empty:
            raise ValueError('Error when creating next_games dataframe: fixtures dataframe empty')
        if self.form.empty:
            raise ValueError('Error when creating next_games dataframe: form dataframe empty')
        
        next_games = pd.DataFrame()
        
        matchday = self.getCurrentMatchday()
        matchday_no = int(matchday.split(' ')[-1])
        
        next_team_col = []
        for idx, row in self.fixtures[matchday].iterrows():
            if row['Status'] == 'SCHEDULED':  # If not yet played matchday game
                team_name = row['Team']
            else:
                team_name = self.fixtures[f'Matchday {matchday_no+1}'].loc[idx]['Team']
            next_team_col.append(team_name)
        
        next_games['Next Game'] = next_team_col
        
        next_games.index = self.fixtures.index
                
        if display:
            print(next_games)
        
        return next_games
    
    
    # ------------------------- Form dataframe -------------------------------
    
    def initialsToTeamNames(self, initials):
        if initials in self.initials_to_name.keys():
            return self.initials_to_name[initials]
    
    def teamNameToInitials(self, team_name):
        if team_name in self.name_to_initials.keys():
            return self.name_to_initials[team_name]
        else:
            return team_name[:3].upper()
    
    def lastNGames(self, n_games, matchday_no, fixtures):
        teams_played_col = []
        scores_col = []
        home_away_col = []
                
        for _, row in fixtures.iterrows():
            teams_played = []
            scores = []
            home_away = []
            # At each column, group previous 5 columns
            for n in range(matchday_no-n_games+1, matchday_no+1):
                if n > 0:
                    matchday_result = row[f'Matchday {n}']
                    if matchday_result['Score'] != "None - None":
                        teams_played.append(matchday_result['Team'])
                        scores.append(matchday_result['Score'])
                        home_away.append(matchday_result['HomeAway'])
            teams_played_col.append(teams_played)
            scores_col.append(scores)
            home_away_col.append(home_away)

        # Convert full team names to team initials
        teams_played_col = [list(map(lambda team_name : self.teamNameToInitials(team_name), teams_played))
                                 for teams_played in teams_played_col]
        
        # Convert queues back to lists
        teams_played_col = list(map(list, teams_played_col))
        scores_col = list(map(list, scores_col))
        home_away_col = list(map(list, home_away_col))
        
        return teams_played_col, scores_col, home_away_col
    
    def formString(self, scores, home_aways):
        form_str = []
        
        for score, homeAway in zip(scores, home_aways):
            home, _, away = score.split(' ')
            if home != 'None' and away != 'None':
                if int(home) == int(away):
                    form_str.append('D')
                elif int(home) > int(away) and homeAway == 'Home' or int(home) < int(away) and homeAway == 'Away':
                    form_str.append('W')
                else:
                    form_str.append('L')
                    
        form_str = ','.join(form_str)  # Convert to string
        return form_str

    def calcFormRating(self, teams_played, form_str, gds, team_ratings):
        form_percentage = 50  # Default percentage, moves up or down based on performance
        
        if form_str != None:  # If games have been played this season
            #print(form_str)
            #print(teams_played)
            form_str = form_str.replace(',', '')
            for form_idx, result in enumerate(form_str):
                # Convert opposition team initials to their name 
                team_name = self.initialsToTeamNames(teams_played[form_idx])

                #print("ON ", form_percentage)
                # Increament form score based on rating of the team they've won, drawn or lost against
                if result == 'W':
                    #print("W PLUS", (team_ratings.loc[team_name]['Total Rating']) * 100,  "/", len(form_str), "  X  ", abs(gds[form_idx]), "=", ((team_ratings.loc[team_name]['Total Rating']) * 100 / len(form_str)) * abs(gds[form_idx]))
                    form_percentage += ((team_ratings.loc[team_name]['Total Rating']) * 100 / len(form_str)) * abs(gds[form_idx])
                elif result == 'D':
                    #print("D PLUS", team_ratings.loc[team_name]['Total Rating'], "-", (team_ratings.loc[team_name]['Total Rating']), "=", ((team_ratings.loc[team_name]['Total Rating'] - (team_ratings.loc[team_name]['Total Rating'])) * 100) / len(form_str))
                    form_percentage +=  ((team_ratings.loc[team_name]['Total Rating'] - (team_ratings.loc[team_name]['Total Rating'])) * 100) / len(form_str)
                elif result == 'L':
                    #print("L MINUS", (team_ratings.iloc[0]['Total Rating'] * 100), "-", (team_ratings.loc[team_name]['Total Rating']) * 100, "/", len(form_str), " X ", abs(gds[form_idx]), "= -", ((team_ratings.iloc[0]['Total Rating'] - team_ratings.loc[team_name]['Total Rating']) * 100 / len(form_str) * abs(gds[form_idx])))
                    form_percentage -= ((team_ratings.iloc[0]['Total Rating'] - team_ratings.loc[team_name]['Total Rating']) * 100 / len(form_str) * abs(gds[form_idx]))
                    
        # Cap rating
        if form_percentage > 100:
            form_percentage = 100
        elif form_percentage < 0:
            form_percentage = 0
        
        return form_percentage
    
    @timebudget
    def createForm(self, no_seasons, display=False):
        print("Creating form over time dataframe...")
                
        if self.fixtures.empty:
            raise ValueError('Error when creating form dataframe: fixtures dataframe empty')
        if self.standings.empty:
            raise ValueError('Error when creating form dataframe: standings dataframe empty')
        if self.team_ratings.empty:
            raise ValueError('Error when creating form dataframe: team_ratings dataframe empty')
            
        score = self.fixtures.iloc[:, self.fixtures.columns.get_level_values(1)=='Score']
        date = self.fixtures.iloc[:, self.fixtures.columns.get_level_values(1)=='Date']
        
        # Remove cols for matchdays that haven't played yet
        score = score.replace("None - None", np.nan)
        score = score.dropna(axis=1, how='all')
        no_cols = score.shape[1]
        # Drop those same columns
        form = date.drop(date.iloc[:, no_cols:], axis=1)
                            
        for col_idx in range(no_cols):
            teams_played_col, scores_col, home_aways_col = self.lastNGames(5, col_idx+1, self.fixtures)
            form[f'Matchday {col_idx+1}', 'Teams Played'] = teams_played_col
            form[f'Matchday {col_idx+1}', 'Scores'] = scores_col
            form[f'Matchday {col_idx+1}', 'HomeAway'] = home_aways_col
            
            # Form string and goal differences column
            form_str_col = []
            goal_differences_col = []
            for scores, home_aways in zip(scores_col, home_aways_col):
                form_str_col.append(self.formString(scores, home_aways))
                
                # Build goal differences of last games played from perspective of current team
                goal_differences = []
                for score, home_away in zip(scores, home_aways):
                    home, _, away = score.split(' ')
                    if home != 'None' and away != 'None':
                        diff = int(home) - int(away)
                        if diff > 0 and home_away == 'Home' or diff < 0 and home_away == 'Home':
                            goal_differences.append(diff)
                        elif diff < 0 and home_away == 'Away' or diff > 0 and home_away == 'Away':
                            goal_differences.append(diff*-1)
                        else:
                            goal_differences.append(0)
                goal_differences_col.append(goal_differences)
            form[f'Matchday {col_idx+1}', 'Form'] = form_str_col
            form[f'Matchday {col_idx+1}', 'GDs'] = goal_differences_col

            form_rating_col = []
            for teams_played, form_str, gds in zip(teams_played_col, form_str_col, goal_differences_col):
                rating = self.calcFormRating(teams_played, form_str, gds, self.team_ratings)
                form_rating_col.append(rating)
            form[f'Matchday {col_idx+1}', 'Form Rating %'] = form_rating_col
            
            # Column (list of booleans) for whether last 5 games have been against 
            # a team with a long term (multiple season) rating over a certain 
            # threshold (a star team)
            played_star_team_col = []
            for teams_played in teams_played_col:
                ratings = [self.team_ratings['Total Rating'][team_name] for team_name in list(map(self.initialsToTeamNames, teams_played))]
                played_star_team_col.append([team_rating > self.star_team_threshold for team_rating in ratings])
            form[f'Matchday {col_idx+1}', 'Played Star Team'] = played_star_team_col
            
            # Column (list of booleans) for whether last 5 games have won against a star team
            won_against_star_team_col = []
            for played_star_team, form_str in zip(played_star_team_col, form_str_col):  # Team has played games this season
                won_against_star_team_col.append([(result == 'W' and pst == True) for result, pst in zip(form_str.replace(',', ''), played_star_team)])
            form[f'Matchday {col_idx+1}', 'Won Against Star Team'] = won_against_star_team_col
            
        form = form.sort_values((f'Matchday {no_cols}','Form Rating %'), ascending=False)
        form = form.sort_index(level=1)
                            
        if display: 
            print(form)
        
        return form
    
    
    
    
    # ------------ Position over time dataframe ------------
    
    def getGDAndPts(self, score, home_away):
        if type(score) == str:  # If score exists and game has been played
            home, _, away = score.split(' ')
            home, away = int(home), int(away)
            
            pts, gd = 0, 0
            if home == away:
                pts = 1
            if home_away == 'Home':
                gd = home - away
                if home > away:
                    pts = 3
            elif home_away == 'Away':
                gd = away - home
                if home < away:
                    pts = 3
            return gd, pts
        return 0, 0
    
    @timebudget
    def createPositionOverTime(self, display=False):
        print("Creating position over time dataframe...")

        if self.fixtures.empty:
            raise ValueError('Error when creating position_over_time dataframe: fixtures dataframe empty')
        if self.standings.empty:
            raise ValueError('Error when creating position_over_time dataframe: standings dataframe empty')
                
        position_over_time = pd.DataFrame()
        
        score = self.fixtures.iloc[:, self.fixtures.columns.get_level_values(1)=='Score']
        home_away = self.fixtures.iloc[:, self.fixtures.columns.get_level_values(1)=='HomeAway']
        date = self.fixtures.iloc[:, self.fixtures.columns.get_level_values(1)=='Date']
        
        # Remove cols for matchdays that haven't played yet
        score = score.replace("None - None", np.nan).dropna(axis=1, how='all')
        no_cols = score.shape[1]
        # Drop those same columns
        home_away = home_away.drop(home_away.iloc[:, no_cols:], axis=1) 
        date = date.drop(date.iloc[:, no_cols:], axis=1)
        
        position_over_time = pd.concat([score, home_away, date], axis=1)
                        
        for col_idx in range(no_cols):
            gd_col = []
            pts_col = []
            
            col_data = position_over_time[f'Matchday {col_idx+1}']
            for row_idx, row in col_data.iterrows():
                gd = 0
                pts = 0
                if col_idx != 0:
                    # Add previous weejs cumulative gd 
                    new_gd, new_pts = self.getGDAndPts(position_over_time.loc[row_idx][f'Matchday {col_idx}', 'Score'], position_over_time.loc[row_idx][f'Matchday {col_idx}', 'HomeAway'])
                    gd += new_gd
                    pts += new_pts
                new_gd, new_pts = self.getGDAndPts(row['Score'], row['HomeAway'])
                gd += new_gd
                pts += new_pts
                
                gd_col.append(gd)
                pts_col.append(pts)
            
            position_over_time[f'Matchday {col_idx+1}', 'GD'] = gd_col
            position_over_time[f'Matchday {col_idx+1}', 'Points'] = pts_col
            
            position_over_time.sort_values(by=[(f'Matchday {col_idx+1}', 'Points'), (f'Matchday {col_idx+1}', 'GD')], ascending=False, inplace=True)
            # If on the last and most recent column, ensure matchday positions is 
            # exactly the same order as from API standings data 
            if col_idx == no_cols - 1:
                # Reorder to the order as standings data
                position_over_time = position_over_time.reindex(self.standings.index)

            position_over_time[f'Matchday {col_idx+1}', 'Position'] = np.arange(1, 21)
            
        position_over_time = position_over_time.sort_index(level=1)
                
        if display:
            print(position_over_time)
        return position_over_time
    
    
    
    
    
    # ------------- Home advantage dataframe ---------------
    
    @timebudget
    def createHomeAdvantages(self, no_seasons, display=False, request_new=True):
        print("Creating home advantages dataframe...")
        
        home_advantages = pd.DataFrame()
        
        dfs = []
        for i in range(no_seasons):
            data = self.fixturesData(self.season-i, request_new=request_new)
            
            d = {}
            for match in data:
                home_team = match['homeTeam']['name'].replace('&', 'and')
                away_team = match['awayTeam']['name'].replace('&', 'and')

                if home_team not in d.keys():
                    d[home_team] = {(f'{self.season-i}', 'Home Wins'): 0, 
                                    (f'{self.season-i}', 'Home Draws'): 0,
                                    (f'{self.season-i}', 'Home Loses'): 0,
                                    (f'{self.season-i}', 'Away Wins'): 0,
                                    (f'{self.season-i}', 'Away Draws'): 0,
                                    (f'{self.season-i}', 'Away Loses'): 0}                
                if away_team not in d.keys():
                    d[away_team] = {(f'{self.season-i}', 'Home Wins'): 0, 
                                    (f'{self.season-i}', 'Home Draws'): 0,
                                    (f'{self.season-i}', 'Home Loses'): 0,
                                    (f'{self.season-i}', 'Away Wins'): 0,
                                    (f'{self.season-i}', 'Away Draws'): 0,
                                    (f'{self.season-i}', 'Away Loses'): 0}   
                
                if match['score']['winner'] != None:
                    if match['score']['fullTime']['homeTeam'] > match['score']['fullTime']['awayTeam']:
                        # Home team wins
                        d[home_team][(f'{self.season-i}', 'Home Wins')] += 1
                        d[away_team][(f'{self.season-i}', 'Away Loses')] += 1
                    elif match['score']['fullTime']['homeTeam'] < match['score']['fullTime']['awayTeam']:
                        # Away team wins
                        d[home_team][(f'{self.season-i}', 'Home Loses')] += 1
                        d[away_team][(f'{self.season-i}', 'Away Wins')] += 1
                    else:  # Draw
                        d[home_team][(f'{self.season-i}', 'Home Draws')] += 1
                        d[away_team][(f'{self.season-i}', 'Away Draws')] += 1
            
            df = pd.DataFrame(d)
            # Drop teams that are not in current season
            df = df.drop(df.columns[~df.columns.isin(self.team_names)].values.tolist(), axis=1)
            dfs.append(df)
        
        home_advantages = pd.concat(dfs).T
        home_advantages.index.name = "Team"
        # Clean up
        home_advantages = home_advantages.fillna(0)
        home_advantages = home_advantages.astype(int)
        
        
        # Create home advantage column
        for i in range(no_seasons):
            home_advantages[f'{self.season-i}', 'Played'] = home_advantages[f'{self.season-i}']['Home Wins'] + home_advantages[f'{self.season-i}']['Home Draws'] + home_advantages[f'{self.season-i}']['Home Loses'] + home_advantages[f'{self.season-i}']['Away Wins'] + home_advantages[f'{self.season-i}']['Away Draws'] + home_advantages[f'{self.season-i}']['Away Loses']
            home_advantages[f'{self.season-i}', 'Played at Home'] = home_advantages[f'{self.season-i}']['Home Wins'] + home_advantages[f'{self.season-i}']['Home Draws'] + home_advantages[f'{self.season-i}']['Home Loses']
            # Percentage wins = total wins / total games played
            home_advantages[f'{self.season-i}', 'Wins %'] = ((home_advantages[f'{self.season-i}']['Home Wins'] + home_advantages[f'{self.season-i}']['Away Wins']) / home_advantages[f'{self.season-i}']['Played']) * 100
            # Percentage wins at home = total wins at home / total games played at home 
            home_advantages[f'{self.season-i}', 'Home Wins %'] = (home_advantages[f'{self.season-i}']['Home Wins'] / home_advantages[f'{self.season-i}']['Played at Home']) * 100
            # Home advantage = percentage wins at home - percentage wins 
            home_advantages[f'{self.season-i}', 'Home Advantage'] = (home_advantages[f'{self.season-i}']['Home Wins %'] - home_advantages[f'{self.season-i}']['Wins %']) / 100
        
        home_advantages = home_advantages.sort_index(axis=1)


        home_advantages_cols = home_advantages.iloc[:, home_advantages.columns.get_level_values(1)=='Home Advantage']
        # Check whether all teams in current season have played enough home games to meet threshold for use
        if (home_advantages[f'{self.season}']['Played at Home'] <= self.home_games_threshold).all():
            print(f"Current season excluded from home advantages calculation -> haven't all played {self.home_games_threshold} home games.")
            # Drop this seasons column, start from previous season
            home_advantages_cols = home_advantages_cols.iloc[:, :-1]
                    
        # List of all home advantege column names that will be used to calculate final column
        home_advantages['Total Home Advantage'] = home_advantages_cols.mean(axis=1).fillna(0)
        home_advantages = home_advantages.sort_values(by='Total Home Advantage', ascending=False)
        home_advantages.index.name = "Team"
                
        if display:
            print(home_advantages)
        return home_advantages



    # ------------- Standings dataframe ---------------
    
    def standingsData(self, season, request_new=True):
        if request_new:
            response = requests.get(self.url + 'competitions/PL/standings/?season={}'.format(season), 
                                    headers=self.headers)
            print("Code:", response.status_code)
            response = response.json()['standings'][0]['table']
            
            with open(f'data/standings_{season}.json', 'w') as json_file:
                json.dump(response, json_file)
                
            return response
        else:
            with open(f'data/standings_{season}.json', 'r') as json_file:
                return json.load(json_file)

    @timebudget
    def createStandings(self, no_seasons, display=False, request_new=True):
        """Get the Premier League table standings from the last specified number of 
           seasons. Compile each of these standings into a single dataframe to return.
           Dataframe contains only teams that are members of the current season.

        Args:
            no_seasons (int): number of previous seasons to fetch and include. 

        Returns:
            DataFrame: dataframe containing all standings.
        """

        print("Creating standings dataframe...")
        
        standings = pd.DataFrame()
        
        # Loop from current season to the season 2 years ago
        for i in range(no_seasons):
            data = self.standingsData(self.season-i, request_new=request_new)
            # pprint.pprint(data)
            df = pd.DataFrame(data)
            
            # Rename teams to their team name
            team_names = pd.Series([name.replace('&', 'and') for name in [df['team'][x]['name'] for x in range(len(df))]])
            df['team'] = team_names


            df.columns = pd.MultiIndex.from_tuples(((f'{self.season-i}', 'Position'), 
                                                   (f'{self.season-i}', 'Team'),
                                                   (f'{self.season-i}', 'Played'),
                                                   (f'{self.season-i}', 'Form'),
                                                   (f'{self.season-i}', 'Won'),
                                                   (f'{self.season-i}', 'Draw'),
                                                   (f'{self.season-i}', 'Lost'),
                                                   (f'{self.season-i}', 'Points'),
                                                   (f'{self.season-i}', 'GF'),
                                                   (f'{self.season-i}', 'GA'), 
                                                   (f'{self.season-i}', 'GD'),))

            df.index = df[f'{self.season-i}']['Team']
            df = df.drop(columns=['Team'], level=1)
            
            if i == 0:  # If building current season table
                standings = standings.append(df)
                self.team_names = team_names
            else:
                # Drop team rows that are no longer in the current season
                df = df.drop(df[~df.index.isin(standings.index)].index)
                # Drop the Form column from previous seasons
                df = df.drop(columns=['Form'], level=1)
                # Add season standings to main standings dataframe 
                standings = pd.concat([standings, df], axis=1)
        standings.index.name = "Team"
        
        if display:
            print(standings)
        return standings



    # ------------ Fixtures dataframe -------------

    def fixturesData(self, season, request_new=True):
        if request_new:
            response = requests.get(self.url + 'competitions/PL/matches/?season={}'.format(season),
                                        headers=self.headers)
            print("Code:", response.status_code)
            response = response.json()['matches']
            
            # Save new data
            with open(f'data/fixtures_{season}.json', 'w') as json_file:
                json.dump(response, json_file)
            
            return response
        else:
            with open(f'data/fixtures_{season}.json', 'r') as json_file:
                return json.load(json_file)

    @timebudget
    def createFixtures(self, display=False, request_new=True):
        print("Creating fixtures dataframe...")
        
        data = self.fixturesData(self.season, request_new=request_new)
                
        fixtures = pd.DataFrame()
        team_names = []
        matchday = {}
        prev_matchday = 0
        for match in data:
            # If moved on to data for the next matchday 
            if prev_matchday < match['matchday']:
                # Package matchday dictionary into dataframe to concatenate into main fixtures dataframe
                df_matchday= pd.DataFrame(matchday)
                df_matchday.index = team_names
                fixtures = pd.concat([fixtures, df_matchday], axis=1)
                
                # If just finished matchday 1 data, take team name list order as main fixtures dataframe index
                if prev_matchday == 1:
                    fixtures.index = team_names[:]
                    fixtures.index.name = "Team"
                
                # Reset for next matchday
                matchday = {(f'Matchday {match["matchday"]}', 'Date'): [],
                            (f'Matchday {match["matchday"]}', 'HomeAway'): [],
                            (f'Matchday {match["matchday"]}', 'Team'): [],
                            (f'Matchday {match["matchday"]}', 'Status'): [],
                            (f'Matchday {match["matchday"]}', 'Score'): []}
                prev_matchday = match['matchday']
                team_names = []
            
            # Home team row
            matchday[(f'Matchday {match["matchday"]}', 'Date')].append(datetime.strptime(match['utcDate'][:10], "%Y-%m-%d"))
            matchday[(f'Matchday {match["matchday"]}', 'HomeAway')].append('Home')
            matchday[(f'Matchday {match["matchday"]}', 'Team')].append(match['awayTeam']['name'].replace('&', 'and'))
            matchday[(f'Matchday {match["matchday"]}', 'Status')].append(match['status']),
            matchday[(f'Matchday {match["matchday"]}', 'Score')].append(f"{match['score']['fullTime']['homeTeam']} - {match['score']['fullTime']['awayTeam']}")
            team_names.append(match['homeTeam']['name'].replace('&', 'and'))
            # Away team row
            matchday[(f'Matchday {match["matchday"]}', 'Date')].append(datetime.strptime(match['utcDate'][:10], "%Y-%m-%d"))
            matchday[(f'Matchday {match["matchday"]}', 'HomeAway')].append('Away')
            matchday[(f'Matchday {match["matchday"]}', 'Team')].append(match['homeTeam']['name'].replace('&', 'and'))
            matchday[(f'Matchday {match["matchday"]}', 'Status')].append(match['status']),
            matchday[(f'Matchday {match["matchday"]}', 'Score')].append(f"{match['score']['fullTime']['homeTeam']} - {match['score']['fullTime']['awayTeam']}")
            team_names.append(match['awayTeam']['name'].replace('&', 'and'))
        # Add matchday 38 to fixtures
        df_matchday= pd.DataFrame(matchday)
        df_matchday.index = team_names
        fixtures = pd.concat([fixtures, df_matchday], axis=1)
                
        if display:
            print(fixtures)
        return fixtures
                   



    # ----------- Team ratings dataframe -----------
    
    def calcRating(self, position, points, gd):
        rating = (20 - position) / 2
        if gd != 0:
            rating *= gd
        if points != 0:
            rating *= points
        return rating
    
    def getSeasonWeightings(self, no_seasons):
        weights = [0.75, 0.20, 0.05]
        weights = np.array(weights[:no_seasons])
        # Normalise list
        weights = list(weights / sum(weights))
        return weights
    
    @timebudget
    def createTeamRatings(self, no_seasons, display=False):
        print("Creating team ratings dataframe...")
        
        if self.standings.empty:
            raise ValueError('Error when creating team_ratings dataframe: standings dataframe empty')
        
        # Add current season team names to the object team dataframe
        team_ratings = pd.DataFrame(index=self.standings.index)

        # Create column for each included season
        for i in range(0, no_seasons):
            team_ratings[f'Rating {i}Y Ago'] = np.nan
                
        # Insert rating values for each row
        for team_name, row in self.standings.iterrows():
            for i in range(no_seasons):
                rating = self.calcRating(row[f'{self.season-i}']['Position'], row[f'{self.season-i}']['Points'], row[f'{self.season-i}']['GD'])
                team_ratings.loc[team_name, 'Rating {}Y Ago'.format(i)] = rating

        # Replace any NaN with the lowest rating in the same column
        for col in team_ratings.columns:
            team_ratings[col].replace(np.nan, team_ratings[col].min(), inplace=True)

        # Create normalised versions of the three ratings columns
        for i in range(0, no_seasons):
            team_ratings[f'Normalised Rating {i}Y Ago'] = (team_ratings[f'Rating {i}Y Ago'] - team_ratings[f'Rating {i}Y Ago'].min()) / (team_ratings[f'Rating {i}Y Ago'].max() - team_ratings[f'Rating {i}Y Ago'].min())

        # Check whether current season data should be included in each team's total rating
        if (self.standings[f'{self.season}']['Played'] <= self.games_threshold).all():  # If current season hasn't played enough games
            print(f"Current season excluded from team ratings calculation -> haven't all played {self.games_threshold} games.")
            include_current_season = False
        else:
            include_current_season = True

        # Calculate total rating column
        team_ratings['Total Rating'] = 0
        if include_current_season:
            start_n = 0  # Include current season when calculating total rating
            w = self.getSeasonWeightings(no_seasons) # Column weights
        else:
            start_n = 1  # Exclude current season when calculating total rating
            w = self.getSeasonWeightings(no_seasons-1) # Column weights

        for i in range(start_n, no_seasons):
            team_ratings['Total Rating'] += w[i-start_n] * team_ratings[f'Normalised Rating {i}Y Ago']

        # Tidy dataframe
        team_ratings = team_ratings.sort_values(by="Total Rating", ascending=False)
        team_ratings = team_ratings.rename(columns={'Rating 0Y Ago': 'Rating Current', 'Normalised Rating 0Y Ago': 'Normalised Rating Current'})
        
        if display:
            print(team_ratings)
        return team_ratings
        
    
    
    
    # ----------- Update Plotly graph HTML files ------------    
    
    @timebudget
    def updateFixtures(self, display=False, team=None):
        if self.standings.empty:
            raise ValueError('Error when creating fixtures dataframe: standings dataframe empty')
        if self.fixtures.empty:
            raise ValueError('Error when creating fixtures dataframe: fixtures dataframe empty')
        if self.team_ratings.empty:
            raise ValueError('Error when creating fixtures dataframe: team_ratings dataframe empty')
        if self.home_advantages.empty:
            raise ValueError('Error when creating fixtures dataframe: home_advantages dataframe empty')

        # Input team rating dataframe to grade upcoming fixtures
        graph = GraphData()
        if team == None:
            print("Updating all team fixtures graphs...")
            for team_name in self.fixtures.index.values.tolist():
                graph.genFixturesGraph(team_name, self.fixtures, self.team_ratings, self.home_advantages, display=display)
        else:
            print(f"Updating {team} fixture graph...")
            graph.genFixturesGraph(team, self.fixtures, self.team_ratings, self.home_advantages, display=display)
    
    @timebudget
    def updateFormOverTime(self, star_team_threshold, display=False, team=None):
        if self.standings.empty:
            raise ValueError('Error when creating form_over_time dataframe: standings dataframe empty')
        if self.fixtures.empty:
            raise ValueError('Error when creating form_over_time dataframe: fixtures dataframe empty')
        if self.team_ratings.empty:
            raise ValueError('Error when creating form_over_time dataframe: team_ratings dataframe empty')
        if self.form.empty:
            raise ValueError('Error when creating form_over_time dataframe: form dataframe empty')
            
        graph = GraphData()
        if team == None:
            print("Updating all teams form over time graphs...")
            for team_name in self.form.index.values.tolist():
                graph.genFormOverTimeGraph(team_name, self.form, star_team_threshold, display=display)
        else:
            print(f"Updating {team} form over time graph...")
            graph.genFormOverTimeGraph(team, self.form, star_team_threshold, display=display)
    
    @timebudget
    def updatePositionOverTime(self, display=False, team=None):
        if self.fixtures.empty:
            raise ValueError('Error when creating position_over_time dataframe: fixtures dataframe empty')
        if self.position_over_time.empty:
            raise ValueError('Error when creating position_over_time dataframe: position_over_time dataframe empty')
                        
        graph = GraphData()
        if team == None:
            print("Updating all teams positions over time graphs...")
            for team_name in self.position_over_time.index.values.tolist():
                graph.genPositionOverTimeGraph(team_name, self.position_over_time, display=display)
        else:
            print(f"Updating {team} positions over time graph...")
            graph.genPositionOverTimeGraph(team, self.position_over_time, display=display)

    @timebudget
    def updateGoalsScoredAndConceded(self, display=False, team=None):
        if self.position_over_time.empty:
            print("Error")
            
        graph = GraphData()
        if team == None:
            print("Updating all teams goals scored and conceded over time graphs...")
            for team_name in self.position_over_time.index.values.tolist():
                graph.genGoalsScoredAndConceded(team_name, self.position_over_time, display=display)
        else:
            print(f"Updating {team} goals scored and conceded over time graph...")
            graph.genGoalsScoredAndConceded(team, self.position_over_time, display=display)
        
    @timebudget
    def updateAll(self, no_seasons, team=None, display_tables=False, display_graphs=False, request_new=True):
        """Update all graph files at once.

        Args:
            no_seasons (int): number of seasons of data to include.
        """
        # ------ Create Dataframes -------
        # Standings for the last "n_seasons" seasons
        self.standings = self.createStandings(no_seasons, display=display_tables, request_new=request_new)
        # Fixtures for each team
        self.fixtures = self.createFixtures(display=display_tables, request_new=request_new)
        # Ratings for each team, based on last "no_seasons" seasons standings table
        self.team_ratings = self.createTeamRatings(no_seasons, display=display_tables)
        self.home_advantages = self.createHomeAdvantages(no_seasons, display=display_tables, request_new=request_new)
        #self.form = self.createForm(no_seasons, self.fixtures, self.standings, self.team_ratings, display=display_tables)
        self.form = self.createForm(no_seasons, display=display_tables)
        self.position_over_time = self.createPositionOverTime(display=display_tables)
        self.next_games = self.createNextGames(display=display_tables)

        # ----- Update Graphs ------
        self.updateFixtures(display=display_graphs, team=team)
        self.updateFormOverTime(self.star_team_threshold, display=display_graphs, team=team)
        self.updatePositionOverTime(display=display_graphs, team=team)
        self.updateGoalsScoredAndConceded(display=display_graphs, team=team)




if __name__ == "__main__":
    data = Data(2020)
    data.updateAll(3, team='Liverpool FC', display_tables=False, display_graphs=False, request_new=False)

