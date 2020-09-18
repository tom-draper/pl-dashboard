from gen_data_vis import GenDataVis
import pandas as pd
import numpy as np
import requests
import json
import pprint
from datetime import datetime


class Data:
    url = "https://api.football-data.org/v2/"
    api = "f6cead2f1c47791235586c2887a3e624599b62862b339749cfc0b10fcc83167c"
    headers = {'X-Auth-Token': 'cb159edc83824c21b6704e7ca18c2920'}

    def __init__(self, current_season):
        self.season = current_season
        
        # Number of games played in a season for season data to be used
        self.games_threshold = 0
                
        # List of current season teams, updated when updating standings 
        self.team_names = None  
        
        self.fixtures = pd.DataFrame()
        self.standings = pd.DataFrame()
        self.team_ratings = pd.DataFrame()
        self.home_advantages = pd.DataFrame()
        
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
    
    # -------- Functions For Page Load ------------
    # Functions that are called inside Flask page load functions
    # Returns data to used to display information on webpage
    # Functions require all dataframes to be filled first
    
    def getPosition(self, team_name):
        return self.standings.loc[team_name, f'{self.season}']['Position']

    def getForm(self, team_name):
        form = self.form.loc[team_name]['Form']
        if form == None:
            form = []
        form = list(form) + ['None'] * (5 - len(form))  # Pad list
        return form

    def getRecentTeamsPlayed(self, team_name):
        return self.form.loc[team_name]['Teams Played']
    
    def getCurrentFormRating(self, team_name):
        return self.form.loc[team_name]['Current Form Rating %'].round(1)
    
    def getWonAgainstStarTeam(self, team_name):
        won_against_star_team = self.form.loc[team_name]['Won Against Star Team']
        # Replace boolean values with CSS tag for super win image
        won_against_star_team = ["star-team" if x else "not-star-team" for x in won_against_star_team]
        return won_against_star_team
    
    def getTableSnippet(self, team_name):
        team_df_idx = self.standings.index.get_loc(team_name)
        
        low_idx = team_df_idx-3
        high_idx = team_df_idx+4
        if low_idx < 0:
            # Add overflow amount to the high_idx to ensure 7 teams 
            overflow = low_idx
            high_idx -= low_idx  # Subtracting a negative
            low_idx = 0
        if high_idx > self.standings.shape[0] - 1:
            # Subtract overflow amount from the low_idx to ensure 7 teams
            overflow = high_idx - (self.standings.shape[0] - 1)
            low_idx -= overflow
            high_idx = self.standings.shape[0] - 1
            
        rows = self.standings.iloc[low_idx:high_idx]
        # Get new index of this team, relative to section of rows dataframe
        team_idx = rows.index.get_loc(team_name)

        team_names = self.standings.index.values.tolist()[low_idx:high_idx]
        # Remove 'FC' from end of each team name
        team_names = list(map(lambda name: ' '.join(name.split(' ')[:-1]), team_names))
        
        # Discard irrelevant columns
        columns = ['Position', 'GD', 'Points']
        rows = rows[f'{self.season}'][columns]
        
        table_snippet = rows.values.tolist()
        for row_list, team_name in zip(table_snippet, team_names):
            row_list.insert(1, team_name)
            
        # Make CSS styles lists for team row background colour
        table_css_styles = [''] * 7
        table_css_styles[team_idx] = f"this-team {team_names[team_idx].lower().replace(' ', '-')}"
        print(table_css_styles)
            
        return table_snippet, table_css_styles
    
    
    # ------------- Form Dataframe ------------
    
    def starTeam(self, team_name, team_ratings):
        if team_name in team_ratings.index:
            if team_ratings.loc[team_name]['Total Rating'] > 0.8:
                return True
        return False
    
    def initialsToTeamNames(self, initials):
        if initials in self.initials_to_name.keys():
            return self.initials_to_name[initials]
    
    def teamNameToInitials(self, team_name):
        if team_name in self.name_to_initials.keys():
            return self.name_to_initials[team_name]
        else:
            return team_name[:3].upper()
        
    
    def createForm(self, fixtures, standings, team_ratings, display=False):
        print("Creating form dataframe...")
        
        form = pd.DataFrame()
        
        # Form column (string of W, L or D)
        form['Form'] = standings[f'{self.season}']['Form']
        
        # Five last teams played column (list of 5 team initials)
        df_team_names = fixtures.iloc[:, fixtures.columns.get_level_values(1)=='Team'].droplevel(level=1, axis=1)  # Drop Team column label
        df_scores = fixtures.iloc[:, fixtures.columns.get_level_values(1)=='Score'].droplevel(level=1, axis=1)  # Drop Score column label
        df_home_aways = fixtures.iloc[:, fixtures.columns.get_level_values(1)=='HomeAway'].droplevel(level=1, axis=1)  # Drop Score column label
        df_status = fixtures.iloc[:, fixtures.columns.get_level_values(1)=='Status'].droplevel(level=1, axis=1)  # Drop Status column label
        # Keep only columns of matchdays that have played
        df_team_names = df_team_names.where(df_status == "FINISHED")
        df_scores = df_scores.where(df_status == "FINISHED")
        df_home_aways = df_home_aways.where(df_status == "FINISHED")

        # Drop nan columns (columns of future matchdays)
        df_team_names.dropna(axis=1, how='all', inplace=True)
        df_scores.dropna(axis=1, how='all', inplace=True)
        df_home_aways.dropna(axis=1, how='all', inplace=True)
        df_team_names.replace(np.nan, '', inplace=True)
        df_scores.replace(np.nan, '', inplace=True)
        df_home_aways.replace(np.nan, '', inplace=True)
        
        df_team_names.index.name = "Team"
        df_scores.index.name = "Team"
        df_home_aways.index.name = "Team"
        # Give each dataframe the same index order
        df_scores.sort_index(inplace=True)
        df_team_names.sort_index(inplace=True)
        df_home_aways.sort_index(inplace=True)
        form.sort_index(inplace=True)
                        
        team_initials_col = df_team_names.values.tolist()
        scorelines_col = df_scores.values.tolist()
        home_aways_col = df_home_aways.values.tolist()
        
        for idx, team_played_list in enumerate(team_initials_col):
            # Convert all team names to initials
            team_initials_col[idx] = list(map(self.teamNameToInitials, team_played_list))
            # Only keep 5 most recent teams played
            if len(team_played_list) > 5:
                team_initials_col[idx] = team_played_list[:-5]
                scorelines_col[idx] = scorelines_col[:-5]
                home_aways_col[idx] = home_aways_col[:-5]
            else:
                # Pad list with blank strings to length of 5
                team_initials_col[idx] += [''] * (5 - len(team_played_list))
                scorelines_col[idx] += [''] * (5 - len(team_played_list))
                home_aways_col[idx] += [''] * (5 - len(team_played_list))
        form['Teams Played'] = team_initials_col
        form['Scorelines'] = scorelines_col
        form['HomeAways'] = home_aways_col
        
        # Goal difference column
        goal_differences_col = []
        for row_idx, scorelines in enumerate(form['Scorelines']):
            goal_differences = []
            for list_idx, scoreline in enumerate(scorelines):
                if scoreline != '':
                    home, _, away = scoreline.split(' ')
                    if form['HomeAways'][row_idx][list_idx] == 'Home':
                        gd = int(home) - int(away)
                    elif form['HomeAways'][row_idx][list_idx] == 'Away':
                        gd = int(away) - int(home)
                    goal_differences.append(gd)
                else:
                    goal_differences.append(0)
            goal_differences_col.append(goal_differences)
        form['GDs'] = goal_differences_col
        
        #Played star team column  (list of booleans for whether the team played was rated over 80%)
        played_star_team_col = []
        for row in form['Teams Played']:
            played_star_team_col.append([self.starTeam(team_name, team_ratings) for team_name in list(map(self.initialsToTeamNames, row))])
        form['Played Star Team'] = played_star_team_col

        # Won against star team column (list of booleans for whether the team won against a team rated over 80%)
        won_against_star_team_col = []
        for row_idx, row in enumerate(form['Played Star Team']):
            if form['Form'][row_idx] != None:  # Team has played games this season
                won_against_star_team_col.append([result == 'W' and pst == True for result in form['Form'][row_idx] for pst in form['Played Star Team'][row_idx]])
            else:
                won_against_star_team_col.append([False] * 5)
            
        form['Won Against Star Team'] = won_against_star_team_col
        
        # Current form column (difficuily rating of teams played)
        current_forms = []
        for row_idx, teams_played_list in enumerate(team_initials_col):
            form_percentage = 0
            for list_idx, team_initials in enumerate(teams_played_list):
                if team_initials != '':
                    team_played_name = self.initialsToTeamNames(team_initials)
                    # Increament form score based on rating of the team they've won or drawn against
                    if form['Form'][row_idx][list_idx] == 'W':
                        form_percentage += (team_ratings.loc[team_played_name]['Total Rating']) * 100 / len(list(filter(lambda x: x != '', teams_played_list))) * form['GDs'][row_idx][list_idx]
                    elif form['Form'][row_idx][list_idx] == 'D':
                        form_percentage += (team_ratings.loc[team_played_name]['Total Rating']) * 100 / len(list(filter(lambda x: x != '', teams_played_list))) * 0.5 * form['GDs'][row_idx][list_idx]
            # Cap at 100% rating
            if form_percentage > 100:
                form_percentage = 100
            current_forms.append(form_percentage)
        form['Current Form Rating %'] = current_forms
                       
        
        if display:
            print(form)
        return form
    
    
    
    # ---------- Home Advantage Data ------------
    
    def createHomeAdvantages(self, no_seasons, display=False, request_new=True):
        print("Creating home advantages dataframe...")
        
        home_advantages = pd.DataFrame()
        
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

            df = pd.DataFrame(d).T
            df.index.name = "Team"
            df = df[df.index.isin(self.team_names)]
            home_advantages = pd.concat([home_advantages, df], axis=1)
            # home_advantages = home_advantages.join(df, how="outer")
        
        # Clean up
        home_advantages.fillna(0, inplace=True)
        home_advantages = home_advantages.astype(int)
        
        
        # Create home advantage column
        for i in range(no_seasons):
            home_advantages[f'{self.season-i}', 'Played'] = home_advantages[f'{self.season-i}']['Home Wins'] + home_advantages[f'{self.season-i}']['Home Draws'] + home_advantages[f'{self.season-i}']['Home Loses'] + home_advantages[f'{self.season-i}']['Away Wins'] + home_advantages[f'{self.season-i}']['Away Draws'] + home_advantages[f'{self.season-i}']['Away Loses']
            home_advantages[f'{self.season-i}', 'Played at Home'] = home_advantages[f'{self.season-i}']['Home Wins'] + home_advantages[f'{self.season-i}']['Home Draws'] + home_advantages[f'{self.season-i}']['Home Loses']
            # Wins / Total Games Played
            home_advantages[f'{self.season-i}', 'Wins %'] = ((home_advantages[f'{self.season-i}']['Home Wins'] + home_advantages[f'{self.season-i}']['Away Wins']) / home_advantages[f'{self.season-i}']['Played']) * 100
            # Wins at Home / Total Games Played at Home 
            home_advantages[f'{self.season-i}', 'Home Wins %'] = (home_advantages[f'{self.season-i}']['Home Wins'] / home_advantages[f'{self.season-i}']['Played at Home']) * 100
            home_advantages[f'{self.season-i}', 'Home Advantage'] = (home_advantages[f'{self.season-i}']['Home Wins %'] - home_advantages[f'{self.season-i}']['Wins %']) / 100
        
        home_advantages = home_advantages.sort_index(axis=1)

        # Check whether all teams in current season have played enough home games to meet threshold for use
        if (home_advantages[f'{self.season}']['Played at Home'] <= self.games_threshold).all():
            print("Current season excluded from home advantages calculation -> haven't played enough games.")
            start_n = 1  # Start from previous season
        else:
            start_n = 0  # Include current season
            
        # List of all home advantege column names that will be used to calculate final column
        home_advantages['Total Home Advantage'] = home_advantages.iloc[:, home_advantages.columns.get_level_values(1)=='Home Advantage'].mean(axis=1).fillna(0)
        home_advantages.sort_values(by='Total Home Advantage', ascending=False, inplace=True)
        home_advantages.index.name = "Team"
        
        if display:
            print(home_advantages)
        return home_advantages



    # ---------- Standings Data ------------

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
            df.drop(columns=['Team'], level=1, inplace=True)
            
            if i == 0:  # If building current season table
                standings = standings.append(df)
                self.team_names = team_names
            else:
                # Drop team rows that are no longer in the current season
                df.drop(df[~df.index.isin(standings.index)].index, inplace=True)
                # Drop the Form column from previous seasons
                df.drop(columns=['Form'], level=1, inplace=True)
                # Add season standings to main standings dataframe 
                standings = pd.concat([standings, df], axis=1)
                # standings = standings.merge(df, on=f"({self.season-i+1}, Team)", how="outer")
            
        standings.index.name = "Team"
        # Sort by position in most recent season
        # standings.sort_values(by=([f'Position {self.season-i}' for i in range(no_seasons)]), 
        #                                inplace=True)
        
        if display:
            print(standings)
        return standings



    # ------------ Fixtures Data -------------

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

    def createFixtures(self, display=False, request_new=True):
        print("Creating fixtures dataframe...")
        data = self.fixturesData(self.season, request_new=request_new)
        
        fixtures = pd.DataFrame()
        
        d = {}
        matchday = pd.DataFrame()
        prev_match_matchday = 1
        for match in data:
            df_home = {(f'Matchday {match["matchday"]}', 'Date'): datetime.strptime(match['utcDate'][:10], "%Y-%m-%d"),
                       (f'Matchday {match["matchday"]}', 'HomeAway'): 'Home',
                       (f'Matchday {match["matchday"]}', 'Team'): match['awayTeam']['name'].replace('&', 'and'),
                       (f'Matchday {match["matchday"]}', 'Status'): match['status'],
                       (f'Matchday {match["matchday"]}', 'Score'): f"{match['score']['fullTime']['homeTeam']} - {match['score']['fullTime']['awayTeam']}",}
            df_away = {(f'Matchday {match["matchday"]}', 'Date'): datetime.strptime(match['utcDate'][:10], "%Y-%m-%d"),
                       (f'Matchday {match["matchday"]}', 'HomeAway'): 'Away',
                       (f'Matchday {match["matchday"]}', 'Team'): match['homeTeam']['name'].replace('&', 'and'),
                       (f'Matchday {match["matchday"]}', 'Status'): match['status'],
                       (f'Matchday {match["matchday"]}', 'Score'): f"{match['score']['fullTime']['homeTeam']} - {match['score']['fullTime']['awayTeam']}",}
            
            # If moved on to next matchday, reset matchday dataframe
            if prev_match_matchday < match['matchday']:
                fixtures = pd.concat([fixtures, matchday], axis=1)
                matchday = pd.DataFrame()
                prev_match_matchday = match['matchday']

            home_row = pd.Series(data=df_home, name=match['homeTeam']['name'].replace('&', 'and'))
            away_row = pd.Series(data=df_away, name=match['awayTeam']['name'].replace('&', 'and'))
            matchday = matchday.append([home_row, away_row])
                
        if display:
            print(fixtures)
        return fixtures
                   



    # ----------- Team Ratings Data -----------
    
    def calcRating(self, position, points, gd):
        rating = (20 - position) / 2
        if gd != 0:
            rating *= gd
        if points != 0:
            rating *= points
        return rating
    
    def getSeasonWeightings(self, no_seasons):
        weights = [0.7, 0.25, 0.05]
        weights = np.array(weights[:no_seasons])
        # Normalise list
        weights = list(weights / sum(weights))
        return weights
        
    
    def createTeamRatings(self, no_seasons, standings, display=False):
        print("Creating team ratings dataframe...")
        # If standings table not calculated, calculate
        if standings.empty:
            standings = self.getStandings(no_seasons)
        
        # Add current season team names to the object team dataframe
        team_ratings = pd.DataFrame(index=standings.index)

        # Create column for each included season
        for i in range(0, no_seasons):
            team_ratings[f'Rating {i}Y Ago'] = np.nan
                
        # Insert rating values for each row
        for team_name, row in standings.iterrows():
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
        if (standings[f'{self.season}']['Played'] <= self.games_threshold).all():  # If current season hasn't played enough games
            print("Current season excluded from team ratings calculation -> haven't played enough games.")
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
        team_ratings.sort_values(by="Total Rating", ascending=False, inplace=True)
        team_ratings.rename(columns={'Rating 0Y Ago': 'Rating Current', 'Normalised Rating 0Y Ago': 'Normalised Rating Current'}, inplace=True)
        
        if display:
            print(team_ratings)
        return team_ratings
        
    
    
    
    # ----------- Update Plotly Graph HTML Files ------------    
    
    def updateFixtures(self, no_seasons, standings, fixtures, team_ratings, home_advantages, display=False, team=None):
        # If required tables not calculated, calculate
        if standings.empty:
            standings = self.getStandings(no_seasons)
        if fixtures.empty:
            fixtures = self.getFixtures()
        if team_ratings.empty:
            team_ratings = self.getTeamRatings(no_seasons, standings)
        if home_advantages.empty:
            home_advantages = self.getHomeAdvantages(no_seasons)

        # Input team rating dataframe to grade upcoming fixtures
        gdv = GenDataVis()
        if team == None:
            print("Updating all team fixtures graphs...")
            for team_name in self.standings.index.values.tolist():
                gdv.genFixturesGraph(team_name, fixtures, team_ratings, home_advantages, display=display)
        else:
            print(f"Updating {team} fixture graph...")
            gdv.genFixturesGraph(team, fixtures, team_ratings, home_advantages, display=display)
    
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
        self.team_ratings = self.createTeamRatings(no_seasons, self.standings, display=display_tables)

        self.home_advantages = self.createHomeAdvantages(no_seasons, display=display_tables, request_new=request_new)
        
        self.form = self.createForm(self.fixtures, self.standings, self.team_ratings, display=display_tables)

        # ----- Update Graphs ------
        self.updateFixtures(no_seasons, self.standings, self.fixtures, self.team_ratings, self.home_advantages, display=display_graphs, team=team)




if __name__ == "__main__":
    data = Data(2020)
    
    data.updateAll(3, team='Liverpool FC', display_tables=True, display_graphs=True, request_new=False)

