import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# --- SETTINGS ---
st.set_page_config(page_title="F1 Flop & Surprise Tracker", layout="wide", page_icon="🏎️")
DNF_VALUE = 21
BASE_URL = "http://api.jolpi.ca/ergast/f1" 

MANUAL_BACKFILL = {
    'LIN': [9, 4, 6],    
    'PER': [21, 21, 10], 
    'BOT': [21, 11, 18]  
}

EXCLUDED_DRIVERS = ['TSU', 'MAG', 'ZHO']

TEAM_COLORS = {
    # Red Bull (Dark Blue)
    "Max Verstappen": "#3671C6", "Arvid Lindblad": "#3671C6", 
    # McLaren (Papaya Orange)
    "Lando Norris": "#FF8000", "Oscar Piastri": "#FF8000",    
    # Ferrari (Red)
    "Charles Leclerc": "#E80020", "Lewis Hamilton": "#E80020",
    # Mercedes (Teal/Silver)
    "George Russell": "#27F4D2", "Andrea Kimi Antonelli": "#27F4D2", 
    # Aston Martin (Racing Green)
    "Fernando Alonso": "#229971", "Lance Stroll": "#229971",  
    # Alpine (Pink)
    "Pierre Gasly": "#FF87BC", "Jack Doohan": "#FF87BC", "Franco Colapinto": "#FF87BC", 
    # Williams (Light Blue)
    "Alexander Albon": "#64C4FF", "Carlos Sainz": "#64C4FF",  
    # VCARB (Blue/White)
    "Yuki Tsunoda": "#6692FF", "Liam Lawson": "#6692FF", "Isack Hadjar": "#6692FF", 
    # Haas (White/Grey)
    "Esteban Ocon": "#B6BABD", "Oliver Bearman": "#B6BABD",   
    # Sauber (Neon Green)
    "Nico Hülkenberg": "#00E701", "Gabriel Bortoleto": "#00E701", 
    # Cadillac (Gold)
    "Sergio Pérez": "#D4AF37", "Valtteri Bottas": "#D4AF37"   
}

# Map for drivers who might not be natively in the API results yet
driver_names_map = {
    'LIN': 'Arvid Lindblad',
    'PER': 'Sergio Pérez', 
    'BOT': 'Valtteri Bottas'
}

def round_half_up(n):
    return int(n + 0.5)

@st.cache_data(ttl=3600)
def fetch_races_for_year(year):
    all_races_dict = {}
    offset = 0
    while True:
        try:
            url = f"{BASE_URL}/{year}/results.json?limit=100&offset={offset}"
            resp = requests.get(url, timeout=5).json()
            races = resp['MRData']['RaceTable']['Races']
            if not races:
                break
            
            for race in races:
                rnd = race['round']
                if rnd not in all_races_dict:
                    all_races_dict[rnd] = race
                else:
                    all_races_dict[rnd]['Results'].extend(race['Results'])
            
            total = int(resp['MRData']['total'])
            offset += 100
            if offset >= total:
                break
        except:
            break
            
    return list(all_races_dict.values())

# --- APP LAYOUT ---
st.title("🏎️ F1 Driver Dashboard")

if st.button('🔄 Refresh Live Data'):
    st.cache_data.clear()
    st.rerun()


# Fetch Data
with st.spinner("Fetching latest Jolpica F1 data..."):
    races_2026 = fetch_races_for_year(2026)
    races_2025 = fetch_races_for_year(2025)
    all_races = races_2025 + races_2026

tab1, tab2 = st.tabs(["🎯 Flop & Surprise Targets", "📈 Driver Progression Graph"])

with tab1:
    # Create dropdown options formatted as '2026 Chinese Grand Prix'
    race_options = [f"{r['season']} {r['raceName']}" for r in all_races]
    
    # Dropdown defaults to the most recent race (the last one in the list)
    selected_race_str = st.selectbox("⏳ Time Machine: Select End Race", reversed(race_options))
    
    # Find the index of the selected race and slice the last 3
    selected_index = race_options.index(selected_race_str)
    start_index = max(0, selected_index - 2)
    all_recent_races = all_races[start_index : selected_index + 1]

    st.subheader("Historical 3-Race Analysis")
    if not all_recent_races:
        st.error("API Error: Could not fetch data.")
    else:
        has_next_race = (selected_index + 1) < len(all_races)
        actual_results = {}
        if has_next_race:
            next_race = all_races[selected_index + 1]
            st.write(f"**Target Race for Verdict:** {next_race['season']} {next_race['raceName']}")
            for result in next_race['Results']:
                if result['Driver']['code'] not in EXCLUDED_DRIVERS:
                    actual_results[result['Driver']['code']] = int(result['positionText']) if result['positionText'].isnumeric() else DNF_VALUE
        else:
            st.write("**Target Race for Verdict:** Pending Details ⏳")

        st.write(f"**Analyzing:** {' ➔ '.join([r['raceName'] for r in all_recent_races])}")
        
        base_weights = [1, 2, 3][-len(all_recent_races):]
        driver_stats = {}
        
        for idx, race in enumerate(all_recent_races):
            weight = base_weights[idx]
            for result in race['Results']:
                if result['Driver']['code'] in EXCLUDED_DRIVERS: continue
                code = result['Driver']['code']
                
                # Dynamically map the full names from the API
                given = result['Driver']['givenName']
                family = result['Driver']['familyName']
                driver_names_map[code] = f"{given} {family}"
                
                pos = int(result['positionText']) if result['positionText'].isnumeric() else DNF_VALUE
                if code not in driver_stats: driver_stats[code] = []
                driver_stats[code].append({'pos': pos, 'weight': weight})

        table_data = []
        all_drivers = set(driver_stats.keys()) | set(MANUAL_BACKFILL.keys())
        
        for driver_code in all_drivers:
            real_results = driver_stats.get(driver_code, [])
            results_needed = 3 - len(real_results)
            
            if results_needed > 0 and driver_code in MANUAL_BACKFILL:
                manual_scores = MANUAL_BACKFILL[driver_code] 
                real_positions = [r['pos'] for r in real_results]
                
                if results_needed == 3: combined = [manual_scores[2], manual_scores[1], manual_scores[0]]
                elif results_needed == 2: combined = [manual_scores[1], manual_scores[0], real_positions[0]]
                else: combined = [manual_scores[0], real_positions[0], real_positions[1]]

                w_avg = ((combined[0]*1) + (combined[1]*2) + (combined[2]*3)) / 6
                formatted_history = [f"{p}*" if i < results_needed else str(p) for i, p in enumerate(combined)]
                pos_history_str = " - ".join(formatted_history)
            else:
                if not real_results: continue
                score_sum = sum(r['pos'] * r['weight'] for r in real_results)
                weight_sum = sum(r['weight'] for r in real_results)
                if weight_sum == 0: continue
                w_avg = score_sum / weight_sum
                pos_history_str = " - ".join([str(r['pos']) for r in real_results])

            raw_surp = w_avg * 0.70
            raw_flop = w_avg * 1.30
            surp_target = max(1, round_half_up(raw_surp))
            flop_target = min(DNF_VALUE, round_half_up(raw_flop))

            # Fetch the full name instead of the 3-letter code
            full_name = driver_names_map.get(driver_code, driver_code)

            actual_pos_str = "TBD"
            verdict_str = "Pending ⏳"

            if has_next_race:
                if driver_code in actual_results:
                    actual_pos = actual_results[driver_code]
                    actual_pos_str = str(actual_pos)
                    
                    if actual_pos <= surp_target:
                        verdict_str = "Surprise 🟢"
                    elif actual_pos >= flop_target:
                        verdict_str = "Flop 🔴"
                    else:
                        verdict_str = "Expected ⚪"

            table_data.append({
                "Driver": full_name,
                "Last 3": pos_history_str,
                "W.Avg": round(w_avg, 2),
                "Raw Surp": round(raw_surp, 2),
                "SURPRISE": f"P{surp_target} or ^",
                "Raw Flop": round(raw_flop, 2),
                "FLOP": f"P{flop_target} or v",
                "Actual Pos": actual_pos_str,
                "Verdict": verdict_str
            })

        df = pd.DataFrame(table_data).sort_values(by="W.Avg").reset_index(drop=True)
        # Dynamic height so every driver row fits without scrolling
        def apply_row_colors(row):
            driver = row['Driver']
            color = TEAM_COLORS.get(driver, '#FFFFFF').lstrip('#')
            r, g, b = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
            opacity = 0.45 if driver in ['Oscar Piastri', 'Lando Norris'] else 0.15
            return [f'background-color: rgba({r}, {g}, {b}, {opacity})'] * len(row)

        styled_df = (df.style
            .apply(apply_row_colors, axis=1)
            .set_properties(subset=['SURPRISE', 'FLOP', 'Verdict'], **{'font-weight': 'bold'})
            .format({'W.Avg': '{:.2f}', 'Raw Surp': '{:.2f}', 'Raw Flop': '{:.2f}'})
        )

        st.dataframe(styled_df, use_container_width=True, hide_index=True, height=(len(df) * 40) + 50)
        st.caption("* Asterisks indicate historical 2024/F2 data used for backfilling.")

with tab2:
    st.subheader("Season Spaghetti Graph")
    chart_races = races_2026 if races_2026 else races_2025
    year_label = "2026" if races_2026 else "2025"
    
    if not chart_races:
        st.info("No race data available to plot yet.")
    else:
        st.write(f"Showing progression for the **{year_label}** season.")
        graph_data = []
        for race in chart_races:
            race_name = race['raceName'].replace(" Grand Prix", "")
            for result in race['Results']:
                if result['Driver']['code'] in EXCLUDED_DRIVERS: continue
                code = result['Driver']['code']
                
                # Use full names for the graph legend too
                given = result['Driver']['givenName']
                family = result['Driver']['familyName']
                full_name = f"{given} {family}"
                
                pos = int(result['positionText']) if result['positionText'].isnumeric() else DNF_VALUE
                graph_data.append({"Race": race_name, "Driver": full_name, "Position": pos})
        
        df_graph = pd.DataFrame(graph_data)
        
        fig = px.line(df_graph, x="Race", y="Position", color="Driver", markers=True, template="plotly_dark", color_discrete_map=TEAM_COLORS)
        fig.update_yaxes(autorange="reversed", tickmode='linear', tick0=1, dtick=1) 
        fig.update_layout(height=850, legend_title="Drivers")
        
        st.plotly_chart(fig, use_container_width=True)