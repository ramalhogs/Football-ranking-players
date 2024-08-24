import pandas as pd
import numpy as np
import re
import os

class FootballDataProcessor:
    def __init__(self, dataframe_campeonato, n):
        self.df = dataframe_campeonato
        self.n = n
        self.players_teams = self.df.iloc[self.n, 3]
        self.team_changes = self.df.iloc[self.n, 5]
        self.home_team = self.df.iloc[self.n, 0]
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
        self.parsed_goals = self.parse_goals(self.df.iloc[8, 4], self.home_team)

        
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
    

    def filter_players_by_unique_ids(self, unique_player_ids):
        self.new_df_players = self.new_df_players[self.new_df_players['player_id'].isin(unique_player_ids)]
    
    def collect_unique_ids(self, data_folder, file_names, years):
        unique_ids = set()

        def process_dataframe(df):
            for column in df.columns:
                for cell in df[column]:
                    if isinstance(cell, dict):  
                        for key in ['Home', 'Away']:
                            team_info = cell.get(key, {})
                            squad_ids = team_info.get('Squad', [])
                            unique_ids.update(squad_ids)

        for file_name in file_names:
            for year in years:
                file_path = os.path.join(data_folder, f'{file_name}_{year}_squads.json')
                if os.path.exists(file_path):
                    df = pd.read_json(file_path)
                    df_ = df.iloc[:,self.n]
                    df = pd.DataFrame(df_)
                    process_dataframe(df)
                else:
                    print(f'Arquivo não encontrado: {file_path}')

        return list(unique_ids)
    
    def process(self, data_folder, file_names, years):
        self.process_players()
        self.process_team_changes()
        self.set_status()
        self.process_goals()
        self.new_df_players.rename(columns={'player': 'nome_jogador'}, inplace=True)
        #self.new_df_players = self.new_df_players.drop(columns='player')

        unique_player_ids = self.collect_unique_ids(data_folder, file_names, years)
        self.filter_players_by_unique_ids(unique_player_ids)

        
        return self.new_df_players