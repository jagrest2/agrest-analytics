def simulate_possession(offense_team, defense_team):
    # 1. Did a turnover happen?
    to_prob = (df_stats.loc[df_stats['Team'] == offense_team, 'TOV%'].iloc[0] + 
               df_opp.loc[df_opp['Team'] == defense_team, 'TOV%'].iloc[0]) / 2
               
    if np.random.random() < to_prob:
        return 0, "Turnover"

    # 2. If no turnover, they take a shot. Did it go in?
    efg = df_stats.loc[df_stats['Team'] == offense_team, 'eFG%'].iloc[0]
    if np.random.random() < efg:
        return 2, "Made 2pt Basket" # Simplified for now
    
    # 3. If they missed, did they get the offensive board?
    or_rate = df_opp.loc[df_opp['Team'] == offense_team, 'ORB%'].iloc[0]
    if np.random.random() < or_rate:
        points, desc = simulate_possession(offense_team, defense_team) # Recursive reset
        return points, f"Missed Shot -> Off Rebound -> {desc}"
        
    return 0, "Missed Shot"

def run_full_game_pbp(team_h, team_a):
    total_poss = int(exp_poss(team_h, team_a))
    game_log = []
    score_h, score_a = 0, 0
    
    for p in range(total_poss):
        # Home Team Possession
        pts, desc = simulate_possession(team_h, team_a)
        score_h += pts
        game_log.append(f"Home: {desc} | Score: {score_h}-{score_a}")
        
        # Away Team Possession
        pts, desc = simulate_possession(team_a, team_h)
        score_a += pts
        game_log.append(f"Away: {desc} | Score: {score_h}-{score_a}")
        
    return score_h, score_a, game_log