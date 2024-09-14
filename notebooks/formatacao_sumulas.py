import pandas as pd
import numpy as np
import re
import os
import unicodedata

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
    

    def parse_team_changes(self, changes):

        if (not any('1T' in change for change in changes)) and (not any('2T' in change for change in changes)) and (not any('INT' in change for change in changes)):
            print(f'Substituições sem o tempo realizado: {self.home_team}, index: {self.n}')

        if not any('/' in change for change in changes) and '/' in self.new_df_players.iloc[0, 1]:
            pattern = re.compile(r'(\d{2}:\d{2}) (\d+T|INT)([\w\s]+) (\d+) - [^\d]+ (\d+) - [^\d]+')
        else:
            pattern = re.compile(r'(\d{2}:\d{2}) (INT|\d+T)([\w\s]+/\w+) (\d+) - [^\d]+ (\d+) - [^\d]+')

        parsed_data = []
        for change in changes:
            match = pattern.search(change)
            if match:
                time, half, team, player_out_number, player_in_number = match.groups()
                team = team.strip()
                parsed_data.append((time, half, team, player_out_number, player_in_number))
        
        return parsed_data
    
    def remove_accents(self, text):
        # Normalize the text to NFKD form and remove accents
        return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))


    def parse_goals(self, goals, home_team):
        pattern = re.compile(r'(\+?\d+)(:00)? (\d+T)([^\s]+)\s+([^\d]+?)\s+(.*)')
        parsed_goals = []

        for goal in goals:
            match = pattern.search(goal)

            if match:
                if '+' in (match.group(1)):
                    minute = 45
                else:
                    minute = int(match.group(1))

                half = match.group(3)

                scorer_info = match.group(4)
                player_name = match.group(5).strip()

                time_casa = self.df.iloc[self.n , 0]
                time_visitante = self.df.iloc[self.n, 1]

                # Remove texto após "/" em time_casa se não existir "/" em match.group(6)
                if '/' not in match.group(6) and '/' in time_casa:
                    time_casa = time_casa.split('/')[0].strip()
                    home_team = time_casa

                time_casa = time_casa.replace(' / ', '/')
                time_visitante = time_visitante.replace(' / ', '/')

                time_casa_except = self.tratar_excecoes_nomes_times_2(time_casa)
                time_casa_normalized = self.remove_accents(time_casa)
                time_casa_except_normalized = self.remove_accents(time_casa_except)

                if time_casa in  match.group(6) or time_casa_except in match.group(6) or time_casa_normalized in match.group(6) or time_casa_except_normalized in match.group(6):
                    team = time_casa
                else: 
                    team = time_visitante

                team = self.tratar_excecoes_nomes_times(team)
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
    

    def verifica_substring(self, substring, string):
        partes = substring.split()
        return all(parte in string for parte in partes)

    #as exceções são basicamente para se adequar ao padrão do arquivo de dados. A primeira função é usada para substituições, e a segunda para os gols. É a forma de comunicar entre as tabelas
    def tratar_excecoes_nomes_times(self, team):
        excecoes = {
            "Atlético/PR": "Athletico Paranaense/PR",
            "Atlético/MG": "Atlético Mineiro/MG",
            "Guarani de Juazeiro/CE": "Guarani/CE", #exceção copa do brasil
            "BOTAFOGO/RJ": "Botafogo/RJ", #excecao brasileirao 2014 index 93
        }
        return excecoes.get(team, team)
    

    def tratar_excecoes_nomes_times_2(self, team):
        excecoes = {
            "Athletico Paranaense/PR": "Atlético/PR",
            "Atlético Mineiro/MG": "Atlético/MG",
            "Guarani/CE": "Guarani de Juazeiro/CE", #exceção copa do brasil
        }
        return excecoes.get(team, team)

    def update_team_name(self, team):
        unique_teams = self.new_df_players['team'].unique().tolist()
        for unique_team in unique_teams:
            
            unique_team = self.remove_accents(unique_team)

            unique_team = unique_team.replace(' / ', '/')
            unique_team = self.tratar_excecoes_nomes_times_2(unique_team)

            if team in unique_team:

                return unique_team
        return team  

    def process_team_changes(self):
        self.parsed_changes = self.parse_team_changes(self.team_changes)

        for time, half, team, player_out_number, player_in_number in self.parsed_changes:
            
            team = self.update_team_name(team)
            team = self.tratar_excecoes_nomes_times(team)

            minute = int(time.split(':')[0])
            team = team.replace('/', ' / ')
            
            if '2T' in half:
                minute_entered = 45 + minute
                minute_exited = 45 + minute
            else:
                minute_entered = minute
                minute_exited = minute

            team = re.sub(r' \b[sS][aA][fF]\b', '', team).strip()

            # Atualizar o jogador que entrou
            mask_in = (self.new_df_players['player_name'].apply(lambda x: re.match(r'^' + player_in_number + r'\D', x) is not None) & 
                    self.new_df_players['team'].apply(lambda x: self.verifica_substring(self.remove_accents(team), self.remove_accents(x))))

            self.new_df_players.loc[mask_in, 'Minute Entered'] = minute_entered
            self.new_df_players.loc[mask_in, 'Minute Exited'] = 90  # O jogador que entra fica até o final do jogo

            # Atualizar o jogador que saiu
            mask_out = (self.new_df_players['player_name'].apply(lambda x: re.match(r'^' + player_out_number + r'\D', x) is not None) & 
                        self.new_df_players['team'].apply(lambda x: self.verifica_substring(self.remove_accents(team), self.remove_accents(x))))
            
            self.new_df_players.loc[mask_out, 'Minute Exited'] = minute_exited

        self.new_df_players['Minutes Played'] = self.new_df_players['Minute Exited'] - self.new_df_players['Minute Entered']
    
    def process_goals(self):
        self.parsed_goals = self.parse_goals(self.df.iloc[self.n, 4], self.home_team)

        
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
    
    def collect_unique_ids(self, data_folder, file_name, years):
        unique_ids = set()

        def process_dataframe(df):
            for column in df.columns:
                for cell in df[column]:
                    if isinstance(cell, dict):  
                        for key in ['Home', 'Away']:
                            team_info = cell.get(key, {})
                            squad_ids = team_info.get('Squad', [])
                            unique_ids.update(squad_ids)


        file_path = os.path.join(data_folder, f'{file_name}_{years}_squads.json')
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
        self.new_df_players['time_jogador'] = self.new_df_players['team']

        unique_player_ids = self.collect_unique_ids(data_folder, file_names, years)
        self.filter_players_by_unique_ids(unique_player_ids)

        return self.new_df_players