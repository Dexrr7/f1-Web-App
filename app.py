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
    try:
        resp = requests.get(f"{BASE_URL}/{year}.json", timeout=5).json()
        races = resp['MRData']['RaceTable']['Races']
        completed_races = []
        if not races: return []
        current_round = int(races[-1]['round'])
        while current_round > 0:
            url = f"{BASE_URL}/{year}/{current_round}/results.json"
            try:
                r_resp = requests.get(url, timeout=2).json()
                if r_resp['MRData']['RaceTable']['Races']:
                    race_data = r_resp['MRData']['RaceTable']['Races'][0]
                    completed_races.append(race_data)
            except: pass
            
            if len(completed_races) >= 3: break
            current_round -= 1
        completed_races.reverse() 
        return completed_races 
    except: return []

# --- APP LAYOUT ---
st.title("🏎️ F1 Driver Dashboard")

# Fetch Data
with st.spinner("Fetching latest Jolpica F1 data..."):
    races_2026 = fetch_races_for_year(2026)
    races_2025 = fetch_races_for_year(2025) if len(races_2026) < 3 else []
    all_recent_races = (races_2025 + races_2026)[-3:]

tab1, tab2 = st.tabs(["🎯 Flop & Surprise Targets", "📈 Driver Progression Graph"])

with tab1:
    st.subheader("Last 3 Races Analysis")
    if not all_recent_races:
        st.error("API Error: Could not fetch data.")
    else:
        st.write(f"**Analyzing:** {' ➔ '.join([r['raceName'] for r in all_recent_races])}")
        
        base_weights = [1, 2, 3][-len(all_recent_races):]
        driver_stats = {}
        
        for idx, race in enumerate(all_recent_races):
            weight = base_weights[idx]
            for result in race['Results']:
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

            table_data.append({
                "Driver": full_name,
                "Last 3": pos_history_str,
                "W.Avg": round(w_avg, 2),
                "Raw Surp": round(raw_surp, 2),
                "SURPRISE": f"P{surp_target} or ^",
                "Raw Flop": round(raw_flop, 2),
                "FLOP": f"P{flop_target} or v"
            })

        df = pd.DataFrame(table_data).sort_values(by="W.Avg").reset_index(drop=True)
        # Added height=800 to stretch the table
        st.dataframe(df, use_container_width=True, hide_index=True, height=800)
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
                code = result['Driver']['code']
                
                # Use full names for the graph legend too
                given = result['Driver']['givenName']
                family = result['Driver']['familyName']
                full_name = f"{given} {family}"
                
                pos = int(result['positionText']) if result['positionText'].isnumeric() else DNF_VALUE
                graph_data.append({"Race": race_name, "Driver": full_name, "Position": pos})
        
        df_graph = pd.DataFrame(graph_data)
        
        fig = px.line(df_graph, x="Race", y="Position", color="Driver", markers=True, template="plotly_dark")
        fig.update_yaxes(autorange="reversed", tickmode='linear', tick0=1, dtick=1) 
        fig.update_layout(height=800, legend_title="Drivers") # Stretched the graph a bit too to match
        
        st.plotly_chart(fig, use_container_width=True)