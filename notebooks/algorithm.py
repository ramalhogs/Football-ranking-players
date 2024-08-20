
import numpy as np


class FootballMatchRating:
    def __init__(self, match_data, team_1_name, team_2_name):
        self.match_data = match_data.copy()
        self.team_1_name = team_1_name
        self.team_2_name = team_2_name

        self.team_1 = self.match_data[self.match_data['team'] == self.team_1_name]
        self.team_2 = self.match_data[self.match_data['team'] == self.team_2_name]

    def update_k_q_values(self, player):
        if (player['games_played'] < 30 or player['age'] < 18) and player['rating'] < 2300:
            player['k_value'] = 40
        elif player['rating'] < 2400:
            player['k_value'] = 20
        elif player['games_played'] >= 30 and player['rating'] >= 2400:
            player['k_value'] = 10
        else:
            player['k_value'] = 10  

        player['q_value'] = 0.5
        return player

    def calculate_team_rating(self, team):
        total_minutes = team['Minutes Played'].sum()
        return np.sum(team['rating'] * team['Minutes Played']) / total_minutes

    def expected_score(self, ra, rb):
        return 1 / (1 + 10 ** ((rb - ra) / 400))

    def calculate_individual_changes(self, team_1, team_2, w=1, q=0.5):
        Rb = self.calculate_team_rating(team_2)

        Mmax = 90
        for index, player in team_1.iterrows():
            Ea = self.expected_score(player['rating'], Rb)
            Da = player['goals_for'] - player['goals_against']

            Sa = 1 if Da > 0 else 0.5 if Da == 0 else 0

            if Da != 0:
                Ca = w * (Sa - Ea) * np.cbrt(abs(Da))
            else:
                Ca = w * (Sa - Ea) * player['Minutes Played'] / Mmax

            player = self.update_k_q_values(player)
            team_1.loc[index, 'k_value'] = player['k_value']
            new_rating = player['rating'] + player['k_value'] * ((q * Ca) + ((1 - q) * Ca * (player['Minutes Played'] / 90)))
            team_1.loc[index, 'rating'] = new_rating
            team_1.loc[index, 'games_played'] += 1

        return team_1

    def update_ratings(self):
        self.team_1 = self.calculate_individual_changes(self.team_1, self.team_2)
        self.team_2 = self.calculate_individual_changes(self.team_2, self.team_1)
        
        # Atualiza os dados no DataFrame original
        self.match_data.update(self.team_1)
        self.match_data.update(self.team_2)

        return self.match_data
