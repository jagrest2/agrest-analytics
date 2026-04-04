import sqlite3
import random
import tkinter as tk
from tkinter import ttk, messagebox
import os
import json

DB_NAME = "basketball_sim.db"

# ==========================================
# 0. GLOBAL NAME POOL
# ==========================================
FIRST_NAMES = ["James", "John", "Robert", "Michael", "William"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones"]

def load_names_globally():
    global FIRST_NAMES, LAST_NAMES
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, 'names.json')
    try:
        with open(path, 'r') as f:
            data = json.load(f)
            FIRST_NAMES = data.get('first_names', FIRST_NAMES)
            LAST_NAMES = data.get('last_names', LAST_NAMES)
    except FileNotFoundError:
        pass 

def get_random_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

# ==========================================
# 1. DATABASE & CONFIGURATION
# ==========================================
def setup_database():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.executescript('''
        DROP TABLE IF EXISTS teams;
        DROP TABLE IF EXISTS players;
        DROP TABLE IF EXISTS games;
        DROP TABLE IF EXISTS box_scores;
        
        CREATE TABLE teams (id INTEGER PRIMARY KEY, name TEXT, conference TEXT, prestige INTEGER DEFAULT 50);
        CREATE TABLE players (
            id INTEGER PRIMARY KEY, team_id INTEGER, name TEXT, position TEXT,
            inside_shot INTEGER, outside_shot INTEGER, defense INTEGER,
            year INTEGER DEFAULT 1
        );
        CREATE TABLE games (
            id INTEGER PRIMARY KEY, home_team_id INTEGER, away_team_id INTEGER,
            home_score INTEGER, away_score INTEGER, conference_tag TEXT, is_playoff INTEGER DEFAULT 0
        );
        CREATE TABLE box_scores (
            id INTEGER PRIMARY KEY, game_id INTEGER, player_id INTEGER,
            team_id INTEGER, points INTEGER, minutes INTEGER
        );
    ''')
    conn.commit()
    return conn

def load_league_config():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, 'league.json')
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"conferences": [{"name": "Default", "teams": ["Team A", "Team B"]}]}

def create_player(c, team_id, year, force_pos=None):
    """Handles 5G/4F/3C roster caps and positional attribute archetypes."""
    if force_pos:
        pos = force_pos
    else:
        # Check current roster to enforce caps
        c.execute("SELECT position, COUNT(*) FROM players WHERE team_id=? GROUP BY position", (team_id,))
        counts = {row[0]: row[1] for row in c.fetchall()}
        
        avail = []
        if counts.get('G', 0) < 5: avail.append('G')
        if counts.get('F', 0) < 4: avail.append('F')
        if counts.get('C', 0) < 3: avail.append('C')
        pos = random.choice(avail) if avail else 'G'
        
    # Archetype logic: G (Outside), F (Balanced), C (Inside)
    if pos == 'G':
        ins, out, dfs = random.randint(40, 75), random.randint(70, 95), random.randint(60, 90)
    elif pos == 'F':
        ins, out, dfs = random.randint(60, 85), random.randint(60, 85), random.randint(60, 90)
    else: # Center
        ins, out, dfs = random.randint(70, 95), random.randint(40, 65), random.randint(60, 95)
        
    c.execute("""INSERT INTO players (team_id, name, position, inside_shot, outside_shot, defense, year) 
                 VALUES (?, ?, ?, ?, ?, ?, ?)""", 
              (team_id, get_random_name(), pos, ins, out, dfs, year))

def generate_league(conn):
    c = conn.cursor()
    config = load_league_config()
    load_names_globally() 

    for conf_data in config['conferences']:
        conf_name = conf_data['name']
        for team_name in conf_data['teams']:
            c.execute("INSERT INTO teams (name, conference) VALUES (?, ?)", (team_name, conf_name))
            team_id = c.lastrowid
            # Generate a balanced roster of 10
            for pos in ['G', 'G', 'G', 'G', 'F', 'F', 'F', 'F', 'C', 'C']:
                yr = random.randint(1, 4)
                create_player(c, team_id, yr, force_pos=pos)
    conn.commit()

def generate_schedule(conn, config):
    c = conn.cursor()
    for conf_data in config['conferences']:
        conf_name = conf_data['name']
        c.execute("SELECT id FROM teams WHERE conference=?", (conf_name,))
        team_ids = [r[0] for r in c.fetchall()]
        for h in team_ids:
            for a in team_ids:
                if h != a: play_game(conn, h, a)
                    
    NON_CONF_GAMES_PER_TEAM = 10
    c.execute("SELECT id, conference FROM teams")
    all_teams = c.fetchall()
    non_conf_counts = {t[0]: 0 for t in all_teams}
    
    for t_id, t_conf in all_teams:
        while non_conf_counts[t_id] < NON_CONF_GAMES_PER_TEAM:
            potentials = [opp[0] for opp in all_teams if opp[0] != t_id and opp[1] != t_conf and non_conf_counts[opp[0]] < NON_CONF_GAMES_PER_TEAM]
            if not potentials: break
            opp_id = random.choice(potentials)
            play_game(conn, t_id, opp_id)
            non_conf_counts[t_id] += 1
            non_conf_counts[opp_id] += 1

def initialize_team_prestige(conn):
    c = conn.cursor()
    # Set prestige to the average OVR of the players on that team
    c.execute("""
        UPDATE teams 
        SET prestige = (
            SELECT CAST(AVG((inside_shot + outside_shot + defense) / 3) AS INTEGER)
            FROM players 
            WHERE players.team_id = teams.id
        )
    """)
    conn.commit()

# ==========================================
# 2. SIMULATION MATH
# ==========================================
def resolve_possession(s, d):
    # s[3] = inside_shot, s[4] = outside_shot (shifted by position column)
    # d[5] = defense (shifted by position column)
    if random.random() > 0.4: # Outside shot
        return 3 if random.randint(1, 100) < (32 + (s[4] - d[5]) * 0.4) else 0
    return 2 if random.randint(1, 100) < (46 + (s[3] - d[5]) * 0.4) else 0

def play_game(conn, home_id, away_id, is_playoff=0):
    c = conn.cursor()
    c.execute("SELECT conference FROM teams WHERE id=?", (home_id,))
    h_conf = c.fetchone()[0]
    c.execute("SELECT conference FROM teams WHERE id=?", (away_id,))
    a_conf = c.fetchone()[0]
    conf_tag = "Playoffs" if is_playoff else (h_conf if h_conf == a_conf else "Non-Conf")

    def get_roster_with_minutes(t_id):
        c.execute("""SELECT id, name, position, inside_shot, outside_shot, defense, 
                     (inside_shot+outside_shot+defense)/3 as ovr 
                     FROM players WHERE team_id=? ORDER BY ovr DESC""", (t_id,))
        players = c.fetchall()
        
        starters, bench = [], []
        has_g = has_f = has_c = False
        
        # 1. Position-Locked Starters
        for p in players:
            pos = p[2]
            if pos == 'G' and not has_g: starters.append(p); has_g = True
            elif pos == 'F' and not has_f: starters.append(p); has_f = True
            elif pos == 'C' and not has_c: starters.append(p); has_c = True
            else: bench.append(p)
                
        starters.extend(bench[:2]) # Fill remaining 2 starter spots
        bench = bench[2:]
        
        # 2. Precise Minute Allocation
        mins = {}
        total_assigned = 0
        
        # Starters get a realistic bulk (avg 30 mins)
        for p in starters:
            m = random.randint(26, 34)
            mins[p[0]] = m
            total_assigned += m
            
        # 3. Calculate remaining pool for the 5 bench players
        remaining = 200 - total_assigned # Usually around 35-65 minutes
        
        # Distribute remaining minutes to the 5 bench players
        # We give the first 4 bench players a random slice, then the last one gets the remainder
        bench_players = bench[:5]
        for i, p in enumerate(bench_players):
            if i == len(bench_players) - 1:
                mins[p[0]] = remaining # Last player takes whatever is left to hit 200
            else:
                # Give them a slice but leave enough for others (min 2 mins each)
                slice_max = max(2, remaining - (2 * (len(bench_players) - 1 - i)))
                m = random.randint(2, min(12, slice_max))
                mins[p[0]] = m
                remaining -= m
                
        return starters + bench, mins

    h_players, h_mins = get_roster_with_minutes(home_id)
    a_players, a_mins = get_roster_with_minutes(away_id)
    h_pool = [p for p in h_players for _ in range(h_mins[p[0]])]
    a_pool = [p for p in a_players for _ in range(a_mins[p[0]])]
    
    p_pts = {p[0]: 0 for p in h_players + a_players}
    h_s, a_s = 0, 0
    
    for _ in range(90): # Slightly more possessions for 10-man roster
        shooter, defender = random.choice(h_pool), random.choice(a_pool)
        res = resolve_possession(shooter, defender)
        p_pts[shooter[0]] += res; h_s += res
        
        shooter, defender = random.choice(a_pool), random.choice(h_pool)
        res = resolve_possession(shooter, defender)
        p_pts[shooter[0]] += res; a_s += res

    c.execute("INSERT INTO games (home_team_id, away_team_id, home_score, away_score, conference_tag, is_playoff) VALUES (?,?,?,?,?,?)",
              (home_id, away_id, h_s, a_s, conf_tag, is_playoff))
    g_id = c.lastrowid
    
    for p_id, pts in p_pts.items():
        t_id = home_id if p_id in [px[0] for px in h_players] else away_id
        c.execute("INSERT INTO box_scores (game_id, player_id, team_id, points, minutes) VALUES (?,?,?,?,?)",
                  (g_id, p_id, t_id, pts, {**h_mins, **a_mins}[p_id]))
    

    c.execute("SELECT prestige FROM teams WHERE id=?", (home_id,))
    h_prestige = c.fetchone()[0]
    c.execute("SELECT prestige FROM teams WHERE id=?", (away_id,))
    a_prestige = c.fetchone()[0]

    if h_s > a_s: # Home Win
        h_change = max(1, a_prestige // 20)  # Gain more for beating good teams
        a_change = max(1, (100 - h_prestige) // 20) # Lose more for losing to bad teams
        new_h = min(99, h_prestige + h_change)
        new_a = max(0, a_prestige - a_change)
    else: # Away Win
        a_change = max(1, h_prestige // 20)
        h_change = max(1, (100 - a_prestige) // 20)
        new_a = min(99, a_prestige + a_change)
        new_h = max(0, h_prestige - h_change)

    c.execute("UPDATE teams SET prestige=? WHERE id=?", (new_h, home_id))
    c.execute("UPDATE teams SET prestige=? WHERE id=?", (new_a, away_id))
    conn.commit()
    return (home_id, h_s) if h_s > a_s else (away_id, a_s)

# ==========================================
# 3. GUI & DASHBOARDS
# ==========================================
class BlueprintBasketballGUI:
    def __init__(self, root, conn, config):
        self.root, self.conn, self.config = root, conn, config
        self.root.title("Blueprint Basketball: Dynasty Engine")
        self.root.geometry("1100x700")
        
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        for conf in self.config['conferences']:
            tab = tk.Frame(self.notebook)
            self.notebook.add(tab, text=f"{conf['name']} Schedule")
            self.setup_schedule_view(tab, conf['name'])
            
        self.standings_tab = tk.Frame(self.notebook)
        self.stats_tab = tk.Frame(self.notebook)
        self.team_profile_tab = tk.Frame(self.notebook)
        self.playoff_tab = tk.Frame(self.notebook)
        
        self.notebook.add(self.standings_tab, text="Standings")
        self.notebook.add(self.stats_tab, text="Player Stats")
        self.notebook.add(self.team_profile_tab, text="Team Profile")
        self.notebook.add(self.playoff_tab, text="Playoffs")
        
        self.setup_standings_view()
        self.setup_stats_view()
        self.setup_team_profile_view()
        self.setup_playoff_view()

    def treeview_sort_column(self, tv, col, reverse):
        l = [(tv.set(k, col), k) for k in tv.get_children('')]
        try: l.sort(key=lambda t: float(t[0]), reverse=reverse)
        except: l.sort(reverse=reverse)
        for index, (val, k) in enumerate(l): tv.move(k, '', index)
        tv.heading(col, command=lambda: self.treeview_sort_column(tv, col, not reverse))

    def setup_schedule_view(self, tab, conf_name):
        f = tk.Frame(tab); f.pack(fill="both", expand=True)
        lb = tk.Listbox(f, width=45); lb.pack(side="left", fill="y", padx=5, pady=5)
        # Added "Pos" to the columns list here
        cols = ("Player", "Pos", "Team", "MIN", "PTS")
        tv = ttk.Treeview(f, columns=cols, show="headings")
        for c in cols: 
            tv.heading(c, text=c)
            tv.column(c, width=80, anchor="center")
        tv.pack(side="right", fill="both", expand=True, padx=5, pady=5)
        
        c = self.conn.cursor()
        ids = []
        for row in c.execute("SELECT g.id, t1.name, g.home_score, t2.name, g.away_score FROM games g JOIN teams t1 ON g.home_team_id=t1.id JOIN teams t2 ON g.away_team_id=t2.id WHERE g.conference_tag=?", (conf_name,)).fetchall():
            lb.insert(tk.END, f"{row[3]} {row[4]} @ {row[1]} {row[2]}")
            ids.append(row[0])
        lb.bind('<<ListboxSelect>>', lambda e: self.show_box(lb, tv, ids))

    def show_box(self, lb, tv, ids):
        if not lb.curselection(): return
        g_id = ids[lb.curselection()[0]]
        for i in tv.get_children(): tv.delete(i)
        # Added p.position to the SELECT statement
        query = """
            SELECT p.name, p.position, t.name, b.minutes, b.points 
            FROM box_scores b 
            JOIN players p ON b.player_id=p.id 
            JOIN teams t ON b.team_id=t.id 
            WHERE b.game_id=? 
            ORDER BY t.name, b.minutes DESC
        """
        for row in self.conn.cursor().execute(query, (g_id,)).fetchall():
            tv.insert("", tk.END, values=row)

    def setup_standings_view(self):
        cols = ("Team", "Conf", "Prestige", "W", "L", "Win %")
        tv = ttk.Treeview(self.standings_tab, columns=cols, show="headings")
        for c in cols: tv.heading(c, text=c, command=lambda _c=c: self.treeview_sort_column(tv, _c, False)); tv.column(c, anchor="center")
        tv.pack(fill="both", expand=True, padx=20, pady=20)
        q = """SELECT t.name, t.conference, t.prestige,
               SUM(CASE WHEN (g.home_team_id=t.id AND g.home_score>g.away_score) OR (g.away_team_id=t.id AND g.away_score>g.home_score) THEN 1 ELSE 0 END) as W,
               SUM(CASE WHEN (g.home_team_id=t.id AND g.home_score<g.away_score) OR (g.away_team_id=t.id AND g.away_score<g.home_score) THEN 1 ELSE 0 END) as L
               FROM teams t LEFT JOIN games g ON (t.id=g.home_team_id OR t.id=g.away_team_id) AND g.is_playoff=0 
               GROUP BY t.id ORDER BY t.prestige DESC""" # Sort by prestige by default
        
        for r in self.conn.cursor().execute(q).fetchall():
            pct = f"{(r[3]/(r[3]+r[4])):.3f}" if (r[3]+r[4])>0 else ".000"
            # Indices: 0:Name, 1:Conf, 2:Prestige, 3:W, 4:L
            tv.insert("", tk.END, values=(r[0], r[1], r[2], r[3], r[4], pct))

    def setup_stats_view(self):
        cols = ("Name", "Team", "Pos", "Yr", "OVR", "PPG", "MPG")
        tv = ttk.Treeview(self.stats_tab, columns=cols, show="headings")
        for c in cols: tv.heading(c, text=c, command=lambda _c=c: self.treeview_sort_column(tv, _c, False)); tv.column(c, width=80, anchor="center")
        tv.pack(fill="both", expand=True, padx=10, pady=10)
        q = """SELECT p.name, t.name, p.position, p.year, (p.inside_shot+p.outside_shot+p.defense)/3, 
               AVG(b.points), AVG(b.minutes) FROM players p JOIN teams t ON p.team_id=t.id 
               JOIN box_scores b ON p.id=b.player_id GROUP BY p.id ORDER BY AVG(b.points) DESC"""
        for r in self.conn.cursor().execute(q).fetchall():
            yr_str = ["Fr", "So", "Jr", "Sr"][r[3]-1] if 1 <= r[3] <= 4 else str(r[3])
            tv.insert("", tk.END, values=(r[0], r[1], r[2], yr_str, r[4], f"{r[5]:.1f}", f"{r[6]:.1f}"))

    def setup_team_profile_view(self):
        top = tk.Frame(self.team_profile_tab); top.pack(fill="x", pady=10)
        tk.Label(top, text="Select Team:", font=("Arial", 10, "bold")).pack(side="left", padx=10)
        c = self.conn.cursor()
        team_names = [r[0] for r in c.execute("SELECT name FROM teams ORDER BY name").fetchall()]
        self.team_selector = ttk.Combobox(top, values=team_names, state="readonly")
        self.team_selector.pack(side="left", padx=5)
        self.team_selector.bind("<<ComboboxSelected>>", self.refresh_team_profile)
        disp = tk.Frame(self.team_profile_tab); disp.pack(fill="both", expand=True, padx=10, pady=5)
        r_frame = tk.LabelFrame(disp, text="Roster & Ratings"); r_frame.pack(side="left", fill="both", expand=True, padx=5)
        cols_r = ("Name", "Pos", "Yr", "OVR", "In", "Out", "Def")
        self.roster_tv = ttk.Treeview(r_frame, columns=cols_r, show="headings")
        for col in cols_r: self.roster_tv.heading(col, text=col); self.roster_tv.column(col, width=50, anchor="center")
        self.roster_tv.pack(fill="both", expand=True)
        s_frame = tk.LabelFrame(disp, text="Season Results"); s_frame.pack(side="right", fill="both", expand=True, padx=5)
        cols_s = ("Opponent", "Result", "Score", "Type")
        self.team_sched_tv = ttk.Treeview(s_frame, columns=cols_s, show="headings")
        for col in cols_s: self.team_sched_tv.heading(col, text=col); self.team_sched_tv.column(col, width=80, anchor="center")
        self.team_sched_tv.pack(fill="both", expand=True)

    def refresh_team_profile(self, event=None):
        t_name = self.team_selector.get()
        c = self.conn.cursor()
        for i in self.roster_tv.get_children(): self.roster_tv.delete(i)
        for i in self.team_sched_tv.get_children(): self.team_sched_tv.delete(i)
        t_id = c.execute("SELECT id FROM teams WHERE name=?", (t_name,)).fetchone()[0]
        # Query including position
        for r in c.execute("SELECT name, position, year, (inside_shot+outside_shot+defense)/3, inside_shot, outside_shot, defense FROM players WHERE team_id=? ORDER BY 4 DESC", (t_id,)).fetchall():
            yr_str = ["Fr", "So", "Jr", "Sr"][r[2]-1] if 1 <= r[2] <= 4 else str(r[2])
            self.roster_tv.insert("", tk.END, values=(r[0], r[1], yr_str, r[3], r[4], r[5], r[6]))
        q = """SELECT CASE WHEN home_team_id=? THEN (SELECT name FROM teams WHERE id=away_team_id) ELSE (SELECT name FROM teams WHERE id=home_team_id) END as opponent,
               CASE WHEN (home_team_id=? AND home_score>away_score) OR (away_team_id=? AND away_score>home_score) THEN 'WIN' ELSE 'LOSS' END as outcome,
               CASE WHEN home_team_id=? THEN home_score || '-' || away_score ELSE away_score || '-' || home_score END as formatted_score, conference_tag
               FROM games WHERE (home_team_id=? OR away_team_id=?) AND is_playoff=0"""
        for r in c.execute(q, (t_id, t_id, t_id, t_id, t_id, t_id)).fetchall():
            self.team_sched_tv.insert("", tk.END, values=r)

    def setup_playoff_view(self):
        self.playoff_teams, self.current_matchup_idx, self.next_round_teams = [], 0, []
        tk.Label(self.playoff_tab, text="Tournament Central", font=("Arial", 16, "bold")).pack(pady=10)
        bf = tk.Frame(self.playoff_tab); bf.pack(pady=5)
        tk.Button(bf, text="1. Bracket", command=self.init_bracket, bg="lightblue").pack(side="left", padx=5)
        self.btn_next = tk.Button(bf, text="2. Next Game", command=self.play_next, state="disabled", bg="lightgreen")
        self.btn_next.pack(side="left", padx=5)
        self.btn_stats = tk.Button(bf, text="3. Stats", command=self.show_stats, state="disabled", bg="orange")
        self.btn_stats.pack(side="left", padx=5)
        self.btn_new = tk.Button(bf, text="4. Start New Season", command=self.start_new_season, state="disabled", bg="pink")
        self.btn_new.pack(side="left", padx=5)
        self.res_txt = tk.Text(self.playoff_tab, height=20, width=70, font=("Courier", 11)); self.res_txt.pack(pady=10)

    def init_bracket(self):
        c, self.res_txt = self.conn.cursor(), self.res_txt
        self.res_txt.delete('1.0', tk.END)
        wins = []
        for conf in [c['name'] for c in self.config['conferences']]:
            r = c.execute("SELECT t.id, t.name FROM teams t JOIN games g ON (t.id=g.home_team_id OR t.id=g.away_team_id) AND g.is_playoff=0 WHERE t.conference=? GROUP BY t.id ORDER BY SUM(CASE WHEN (g.home_team_id=t.id AND g.home_score>g.away_score) OR (g.away_team_id=t.id AND g.away_score>g.home_score) THEN 1 ELSE 0 END) DESC LIMIT 1", (conf,)).fetchone()
            if r: wins.append(r)
        bs = 2
        while bs < len(wins): bs *= 2
        self.playoff_teams = list(wins)
        if bs - len(wins) > 0:
            w_ids = [w[0] for w in wins]
            wcs = c.execute(f"SELECT t.id, t.name FROM teams t JOIN games g ON (t.id=g.home_team_id OR t.id=g.away_team_id) AND g.is_playoff=0 WHERE t.id NOT IN ({','.join(['?']*len(w_ids))}) GROUP BY t.id ORDER BY SUM(CASE WHEN (g.home_team_id=t.id AND g.home_score>g.away_score) OR (g.away_team_id=t.id AND g.away_score>g.home_score) THEN 1 ELSE 0 END) DESC LIMIT ?", w_ids + [bs - len(wins)]).fetchall()
            self.playoff_teams.extend(wcs)
        random.shuffle(self.playoff_teams)
        self.next_round_teams, self.current_matchup_idx = [], 0
        self.res_txt.insert(tk.END, f"--- {bs} TEAM BRACKET SET ---\n")
        for i in range(0, len(self.playoff_teams), 2): self.res_txt.insert(tk.END, f"{self.playoff_teams[i][1]} vs {self.playoff_teams[i+1][1]}\n")
        self.btn_next.config(state="normal"); self.btn_stats.config(state="disabled"); self.btn_new.config(state="disabled")

    def play_next(self):
        i = self.current_matchup_idx
        t1, t2 = self.playoff_teams[i], self.playoff_teams[i+1]
        w_id, _ = play_game(self.conn, t1[0], t2[0], is_playoff=1)
        w_name = t1[1] if w_id == t1[0] else t2[1]
        self.res_txt.insert(tk.END, f"\nGAME: {t1[1]} vs {t2[1]} -> {w_name.upper()} ADVANCES\n")
        self.next_round_teams.append((w_id, w_name))
        self.current_matchup_idx += 2
        if self.current_matchup_idx >= len(self.playoff_teams):
            if len(self.next_round_teams) == 1:
                champ = self.next_round_teams[0][1]
                self.res_txt.insert(tk.END, f"\n*** {champ.upper()} CHAMPIONS! ***")
                self.btn_next.config(state="disabled"); self.btn_stats.config(state="normal"); self.btn_new.config(state="normal")
            else:
                self.res_txt.insert(tk.END, f"\n--- NEXT ROUND ---\n")
                self.playoff_teams, self.next_round_teams, self.current_matchup_idx = list(self.next_round_teams), [], 0

    def show_stats(self):
        w = tk.Toplevel(self.root); w.title("Tournament Leaders"); w.geometry("400x300")
        cols = ("Name", "Team", "PTS", "G")
        tv = ttk.Treeview(w, columns=cols, show="headings")
        for c in cols: tv.heading(c, text=c); tv.column(c, width=90, anchor="center")
        tv.pack(fill="both", expand=True, padx=10, pady=10)
        q = "SELECT p.name, t.name, SUM(b.points) as pts, COUNT(b.game_id) FROM box_scores b JOIN players p ON b.player_id=p.id JOIN teams t ON b.team_id=t.id JOIN games g ON b.game_id=g.id WHERE g.is_playoff=1 GROUP BY p.id ORDER BY pts DESC LIMIT 10"
        for r in self.conn.cursor().execute(q).fetchall(): tv.insert("", tk.END, values=r)

    def start_new_season(self):
        if not messagebox.askyesno("New Season", "Clear scores, graduate seniors, and develop players?"): 
            return
        c = self.conn.cursor()
        c.execute("DELETE FROM games")
        c.execute("DELETE FROM box_scores")
        
        # 1. Graduation
        c.execute("DELETE FROM players WHERE year = 4")
        
        # 2. Precision Development Loop (+1 to +3 Always)
        c.execute("SELECT id, inside_shot, outside_shot, defense FROM players")
        returning_players = c.fetchall()
        for p_id, i_shot, o_shot, d_stat in returning_players:
            new_i = min(99, i_shot + random.randint(1, 3))
            new_o = min(99, o_shot + random.randint(1, 3))
            new_d = min(99, d_stat + random.randint(1, 3))
            c.execute("UPDATE players SET inside_shot=?, outside_shot=?, defense=? WHERE id=?", 
                      (new_i, new_o, new_d, p_id))

        # 3. Aging
        c.execute("UPDATE players SET year = year + 1")
        
        # 4. Recruiting with Positional Balance
        for t_id in [r[0] for r in c.execute("SELECT id FROM teams").fetchall()]:
            count = c.execute("SELECT COUNT(*) FROM players WHERE team_id=?", (t_id,)).fetchone()[0]
            for _ in range(10 - count):
                create_player(c, t_id, 1)
                          
        self.conn.commit()
        generate_schedule(self.conn, self.config)
        messagebox.showinfo("Offseason Complete", "Players have developed and new Freshmen have enrolled!")
        self.root.destroy() 

# ==========================================
# 4. EXECUTION
# ==========================================
if __name__ == "__main__":
    config = load_league_config()
    conn = setup_database()
    generate_league(conn)
    generate_schedule(conn, config)
    
    while True:
        try:
            root = tk.Tk()
            app = BlueprintBasketballGUI(root, conn, config)
            root.mainloop()
            if not messagebox.askyesno("Reboot GUI?", "Boot up the new season dashboard?"):
                break
        except Exception:
            break