import pandas as pd
import numpy as np
import re

class FootballDataProcessor:
    def __init__(self, json_path):
        self.df = pd.read_json(json_path)
        self.df_transposed = self.df.transpose()
        self.players_teams = self.df_transposed.iloc[1, 3]
        self.team_changes = self.df_transposed.iloc[1, 5]
        self.home_team = self.df_transposed.iloc[1, 0]
        self.new_df_players = pd.DataFrame(self.players_teams, columns=['player', 'team'])
        self.parsed_changes = []
        self.parsed_goals = []
    
    @staticmethod
    def extract_id(player_string):
        match = re.search(r'T\(g\)?P(\d+)|RP(\d+)|TP(\d+)', player_string, re.IGNORECASE)
        if match:
            return next((m for m in match.groups() if m), None)
        return None
    
    @staticmethod
    def clean_player_name(player):
        clean_name = re.sub(r'\s+T.*|\s+TP.*|\s+RP.*|\s+T(g).*', '', player)
        return clean_name
    
    @staticmethod
    def parse_team_changes(changes):
        pattern = re.compile(r'(\d{2}:\d{2}) (INT|\d+T)([\w\s]+/\w+) (\d+) - [^\d]+ (\d+) - [^\d]+')
        parsed_data = []
        for change in changes:
            match = pattern.search(change)
            if match:
                time, half, team, player_out_number, player_in_number = match.groups()
                team = team.strip()
                parsed_data.append((time, half, team, player_out_number, player_in_number))
        return parsed_data
    
    @staticmethod
    def parse_goals(goals, home_team):
        pattern = re.compile(r'(\d+):00 (\d+T)([\d\w]+)([A-Za-z ]+) ([\w\s/]+)')
        parsed_goals = []
        for goal in goals:
            match = pattern.search(goal)
            if match:
                minute = int(match.group(1))
                half = match.group(2)
                scorer_info = match.group(3)
                player_name = match.group(4).strip()
                team = match.group(5).strip()
                team = team.replace('/', ' / ')
                
                if '2T' in half and minute != 45:
                    minute += 45
                
                if 'CT' in scorer_info:
                    team_status = 'Away' if team == home_team else 'Home'
                else:
                    team_status = 'Home' if team == home_team else 'Away'
                
                parsed_goals.append((minute, team_status))
        return parsed_goals
    
    def process_players(self):
        self.new_df_players['player_id'] = self.new_df_players['player'].apply(self.extract_id)
        self.new_df_players['player_name'] = self.new_df_players['player'].apply(self.clean_player_name)
        self.new_df_players['Minutes Played'] = 90
        self.new_df_players['Minute Entered'] = 0
        self.new_df_players['Minute Exited'] = 90
    
    def process_team_changes(self):
        self.parsed_changes = self.parse_team_changes(self.team_changes)
        
        for time, half, team, player_out_number, player_in_number in self.parsed_changes:
            minute = int(time.split(':')[0])
            team = team.replace('/', ' / ')
            
            minute_entered = 45 + minute if '2T' in half else minute
            minute_exited = minute_entered
            
            mask_in = (
                self.new_df_players['player_name'].apply(
                    lambda x: re.match(r'^' + player_in_number + r'\D', x) is not None
                ) & (self.new_df_players['team'] == team)
            )
            self.new_df_players.loc[mask_in, 'Minute Entered'] = minute_entered
            self.new_df_players.loc[mask_in, 'Minute Exited'] = 90
            
            mask_out = (
                self.new_df_players['player_name'].apply(
                    lambda x: re.match(r'^' + player_out_number + r'\D', x) is not None
                ) & (self.new_df_players['team'] == team)
            )
            self.new_df_players.loc[mask_out, 'Minute Exited'] = minute_exited
        
        self.new_df_players['Minutes Played'] = self.new_df_players['Minute Exited'] - self.new_df_players['Minute Entered']
    
    def process_goals(self):
        self.parsed_goals = self.parse_goals(self.df_transposed.iloc[1, 4], self.home_team)
        
        self.new_df_players['Goals For'] = 0
        self.new_df_players['Goals Against'] = 0
        
        for minute, team in self.parsed_goals:
            mask = (self.new_df_players['Minute Entered'] <= minute) & (self.new_df_players['Minute Exited'] >= minute)
            mask_for = mask & (self.new_df_players['status'] == team)
            self.new_df_players.loc[mask_for, 'Goals For'] += 1
            
            mask_against = mask & (self.new_df_players['status'] != team)
            self.new_df_players.loc[mask_against, 'Goals Against'] += 1
    
    def set_status(self):
        self.new_df_players['status'] = np.where(self.new_df_players['team'] == self.home_team, 'Home', 'Away')
    
    def process(self):
        self.process_players()
        self.process_team_changes()
        self.set_status()
        self.process_goals()
        self.new_df_players = self.new_df_players.drop(columns='player')
        return self.new_df_players