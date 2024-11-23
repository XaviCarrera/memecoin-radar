from datetime import datetime, timedelta
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Set the page configuration
st.set_page_config(page_title="Meme Coin Radar", layout="wide")

# Add custom CSS for the font
st.markdown("""
<style>
body {
    font-family: 'Helvetica Neue', Arial, sans-serif;
    background-color: #f0f8ff; /* Light blue background */
    color: #333; /* Darker text for better readability */
}
h1, h2, h3, h4, h5, h6 {
    color: #1f77b4; /* Blue for headings */
}
div.stButton > button {
    background-color: #e3f2fd; /* Light blue buttons */
    color: #0d47a1; /* Dark blue text on buttons */
    border: 1px solid #90caf9; /* Border around buttons */
}
div.stButton > button:hover {
    background-color: #bbdefb; /* Slightly darker on hover */
}
.sidebar .sidebar-content {
    background-color: #e3f2fd; /* Light blue sidebar */
}
footer {
    background-color: #f0f8ff; /* Light blue footer */
    color: #333; /* Darker text for footer */
}
</style>
""", unsafe_allow_html=True)

# Base URL for the FastAPI endpoints
base_url = "http://0.0.0.0:8080"

# Function to fetch data from an endpoint
@st.cache_data(ttl=3600)
def fetch_data(endpoint, params=None):
    response = requests.get(f"{base_url}/{endpoint}", params=params)
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Failed to fetch data from /{endpoint}")
        st.stop()

# Function to fetch Bitcoin traded volume over the last 7 days
@st.cache_data(ttl=3600)
def fetch_bitcoin_traded_volume():
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)
    # Convert to UNIX timestamps
    end_timestamp = int(end_date.timestamp())
    start_timestamp = int(start_date.timestamp())

    url = f"https://api.coingecko.com/api/v3/coins/bitcoin/market_chart/range"
    params = {
        'vs_currency': 'usd',
        'from': start_timestamp,
        'to': end_timestamp
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        total_volume = sum([volume[1] for volume in data['total_volumes']])
        return total_volume
    else:
        st.error("Failed to fetch Bitcoin traded volume")
        st.stop()

# Fetch data from the endpoints
top_coins_data = fetch_data("top-coins")
top_gainers_data = fetch_data("top-gainers")
top_losers_data = fetch_data("top-losers")
market_sentiment_data = fetch_data("market-sentiment")
bear_vs_bull_value = market_sentiment_data.get('bear_vs_bull_indicator')

# Calculate the date range for the last 7 days
end_date = datetime.utcnow()
start_date = end_date - timedelta(days=7)

# Format the dates as strings in 'YYYY-MM-DD' format
time_params = {
    "start_date": start_date.strftime('%Y-%m-%d'),
    "end_date": end_date.strftime('%Y-%m-%d')
}

# Fetch traded volume data for meme coins over the last 7 days
traded_volume_data_7d = fetch_data("traded-volume", params=time_params)

# Process the traded volume data
volume_over_time_7d = traded_volume_data_7d.get('volume_over_time', [])
df_volume_7d = pd.DataFrame(volume_over_time_7d)
df_volume_7d['date'] = pd.to_datetime(df_volume_7d['date'])
df_volume_7d['total_volume'] = pd.to_numeric(df_volume_7d['total_volume'], errors='coerce')
df_volume_7d = df_volume_7d.sort_values('date')

# Calculate total traded volume of meme coins over the last 7 days
total_meme_volume_7d = df_volume_7d['total_volume'].sum()

# Fetch Bitcoin's traded volume over the last 7 days
bitcoin_volume_7d = fetch_bitcoin_traded_volume()

# Ensure volumes are valid numbers
if not isinstance(total_meme_volume_7d, (int, float)) or not isinstance(bitcoin_volume_7d, (int, float)):
    st.error("Invalid traded volume data.")
    st.stop()

# Calculate the Bitcoin vs Meme Coins indicator based on traded volume
bitcoin_vs_meme_volume_value = (total_meme_volume_7d / (bitcoin_volume_7d + total_meme_volume_7d)) * 100
bitcoin_vs_meme_volume_value = min(max(bitcoin_vs_meme_volume_value, 0), 100)

# Extract total market cap and top coins data
total_market_cap = top_coins_data.get('total_market_cap', 0)
top_10_coins = top_coins_data.get('top_10_coins', [])

# Prepare data for the treemap
treemap_df = pd.DataFrame(top_10_coins)
treemap_df['market_cap'] = pd.to_numeric(treemap_df['market_cap'], errors='coerce')
treemap_df['last_price'] = pd.to_numeric(treemap_df['last_price'], errors='coerce')

# Calculate "Others" for treemap
others_market_cap = total_market_cap - treemap_df['market_cap'].sum()
if others_market_cap > 0:
    others_row = pd.DataFrame({'symbol': ['Others'], 'market_cap': [others_market_cap], 'last_price': [None]})
    treemap_df = pd.concat([treemap_df, others_row], ignore_index=True)

treemap_df['price_text'] = treemap_df['last_price'].apply(lambda x: f"<br>Price: ${x:,.6f}" if pd.notnull(x) else "")
treemap_df['display_text'] = treemap_df.apply(
    lambda row: f"<b>{row['symbol']}</b><br>Market Cap: ${row['market_cap']:,.2f}{row['price_text']}", axis=1
)

# Process the traded volume data for the last 30 days (for the line chart)
end_date_30d = datetime.utcnow() - timedelta(days=2)
start_date_30d = end_date_30d - timedelta(days=30)
time_params_30d = {
    "start_date": start_date_30d.strftime('%Y-%m-%d'),
    "end_date": end_date_30d.strftime('%Y-%m-%d')
}
traded_volume_data_30d = fetch_data("traded-volume", params=time_params_30d)
volume_over_time_30d = traded_volume_data_30d.get('volume_over_time', [])
df_line = pd.DataFrame(volume_over_time_30d)
df_line['date'] = pd.to_datetime(df_line['date'])
df_line['total_volume'] = pd.to_numeric(df_line['total_volume'], errors='coerce')
df_line = df_line.sort_values('date')

# # Sidebar filters
# with st.sidebar:
#     st.header("Filters")
#     selected_coin = st.selectbox("Select Meme Coin", ["Coin A", "Coin B", "Coin C"])
#     selected_period = st.selectbox("Select Period", ["Last 24 Hours", "Last Week", "Last Month"])

# Dashboard Layout
st.markdown("<h1 style='text-align: center;'>Meme Coin Radar</h1>", unsafe_allow_html=True)
st.subheader("Market Overview")

# Key Metrics
col1, col2 = st.columns([1, 1], gap="medium")

with col1:
    st.markdown("""
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1); text-align: center;">
        <h4 style="margin: 0; color: #343a40;">Total Market Cap</h4>
        <p style="margin: 0; font-size: 24px; font-weight: bold; color: #007bff;">${:,.2f}</p>
    </div>
    """.format(total_market_cap), unsafe_allow_html=True)

with col2:
    total_traded_volume = df_line['total_volume'].iloc[-1]  # Latest total volume
    st.markdown("""
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1); text-align: center;">
        <h4 style="margin: 0; color: #343a40;">Total Traded Volume (24 hrs)</h4>
        <p style="margin: 0; font-size: 24px; font-weight: bold; color: #007bff;">${:,.2f}</p>
    </div>
    """.format(total_traded_volume), unsafe_allow_html=True)

# Gauges
col3, col4 = st.columns(2)

with col3:
    st.markdown("""
    <h3 style='text-align: center;'>Bear vs Bull Market 
        <span title="The Bear vs Bull Indicator shows market sentiment. Higher values are bullish (positive), and lower values are bearish (negative).">
        ℹ️
        </span>
    </h3>
    """, unsafe_allow_html=True)
    fig_bear_bull = go.Figure(go.Indicator(
        mode="gauge+number",
        value=bear_vs_bull_value,
        number={'suffix': '%', 'valueformat': '.2f'},
        title={'text': ""},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1},
            'bar': {'color': "#1f77b4"},
            'steps': [
                {'range': [0, 50], 'color': '#cce5ff'},
                {'range': [50, 100], 'color': '#1f77b4'}
            ],
            'threshold': {
                'line': {'color': "black", 'width': 4},
                'thickness': 0.75,
                'value': bear_vs_bull_value
            }
        },
    ))
    fig_bear_bull.update_layout(
        height=250,
        margin=dict(t=20, b=20, l=0, r=0)
    )
    st.plotly_chart(fig_bear_bull, use_container_width=True)

with col4:
    st.markdown("""
    <h3 style='text-align: center;'>Bitcoin vs Meme Coins 
        <span title="This index compares the trading volume of meme coins to Bitcoin. Higher values mean meme coins are gaining market traction.">
        ℹ️
        </span>
    </h3>
    """, unsafe_allow_html=True)
    fig_bitcoin_vs_meme = go.Figure(go.Indicator(
        mode="gauge+number",
        value=bitcoin_vs_meme_volume_value,
        number={'suffix': '%', 'valueformat': '.2f'},
        title={'text': ""},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1},
            'bar': {'color': "#1f77b4"},
            'steps': [
                {'range': [0, 50], 'color': '#cce5ff'},
                {'range': [50, 100], 'color': '#1f77b4'}
            ],
            'threshold': {
                'line': {'color': "black", 'width': 4},
                'thickness': 0.75,
                'value': bitcoin_vs_meme_volume_value
            }
        },
    ))
    fig_bitcoin_vs_meme.update_layout(
        height=250,
        margin=dict(t=20, b=20, l=0, r=0)
    )
    st.plotly_chart(fig_bitcoin_vs_meme, use_container_width=True)

# Market Analysis
st.subheader("Market Analysis")
col5, col6 = st.columns(2)
with col5:
    # Treemap
    fig_treemap = px.treemap(
        treemap_df,
        path=['symbol'],
        values='market_cap',
        custom_data=['display_text'],
        color='market_cap',
        color_continuous_scale=px.colors.sequential.Blues
    )
    fig_treemap.update_traces(
        textinfo='label+value',
        texttemplate='%{customdata[0]}',
        hovertemplate='%{customdata[0]}<extra></extra>'
    )
    fig_treemap.update_layout(
        title="Top 10 Meme Coins by Market Cap",
        height=400,
        coloraxis_showscale=False,
        margin=dict(l=0, r=0, t=30, b=0)
    )
    st.plotly_chart(fig_treemap, use_container_width=True)
with col6:
    # Line Chart: Traded Volume Over Time
    fig_line = px.line(
        df_line,
        x='date',
        y='total_volume',
        title='Last Month Traded Volume'
    )
    fig_line.update_layout(
        height=400,
        yaxis_title="Total Volume",
        xaxis_title="Date",
        margin=dict(l=0, r=0, t=30, b=0)
    )
    st.plotly_chart(fig_line, use_container_width=True)

# Market Movers
st.subheader("Last Week Market Movers")
view_option = st.radio("Select View:", ["Top Gainers", "Top Losers"], horizontal=True)
if view_option == "Top Gainers":
    top_movers = top_gainers_data.get('top_movers', [])
else:
    top_movers = top_losers_data.get('top_movers', [])
movers_df = pd.DataFrame(top_movers)

# Create the bar chart without y-axis adjustments
fig_barchart = px.bar(
    movers_df,
    x='symbol',
    y='percentage_change',
    text='percentage_change',
    labels={'symbol': 'Meme Coin', 'percentage_change': 'Percentage Change (%)'},
    color='percentage_change',
    color_continuous_scale=[
        (0.0, "rgb(173, 216, 230)"),  # Light Blue for lower values
        (0.5, "rgb(36, 123, 160)"),  # Medium Blue
        (1.0, "rgb(0, 49, 83)")      # Dark Blue for higher values
    ],
    color_continuous_midpoint=0  # Optional: Adjust midpoint dynamically if needed
)
fig_barchart.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
fig_barchart.update_layout(
    title=view_option,
    height=400,
    yaxis_title="Percentage Change (%)",
    xaxis_title="Meme Coin",
    coloraxis_showscale=False,
    margin=dict(l=0, r=0, t=30, b=0)
)
st.plotly_chart(fig_barchart, use_container_width=True)


# # Trending Meme Coins
# st.subheader("Trending Meme Coins")
# st.info("This section is under development.")

st.markdown(
    """
    <style>
    .footer {
        position: fixed;
        bottom: 10px;
        right: 10px;
        font-size: 12px;
        color: #555;
        background-color: #f9f9f9;
        padding: 5px 10px;
        border-radius: 5px;
        box-shadow: 0 0 5px rgba(0, 0, 0, 0.1);
    }
    .footer a {
        color: #007bff;
        text-decoration: none;
    }
    .footer a:hover {
        text-decoration: underline;
    }
    </style>
    <div class="footer">
        Curated by <a href="https://www.linkedin.com/in/xavigrowth/" target="_blank">Xavier Carrera</a>
    </div>
    """,
    unsafe_allow_html=True
)
