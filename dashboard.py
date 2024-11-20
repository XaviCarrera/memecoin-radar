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

# Fetch data from the endpoints
top_coins_data = fetch_data("top-coins")
top_gainers_data = fetch_data("top-gainers")
top_losers_data = fetch_data("top-losers")

# Fetch traded volume data (last 30 days)
traded_volume_data = fetch_data("traded-volume")

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

# Process the traded volume data
volume_over_time = traded_volume_data.get('volume_over_time', [])
df_line = pd.DataFrame(volume_over_time)
df_line['date'] = pd.to_datetime(df_line['date'])
df_line['total_volume'] = pd.to_numeric(df_line['total_volume'], errors='coerce')
df_line = df_line.sort_values('date')

# Sidebar filters
with st.sidebar:
    st.header("Filters")
    selected_coin = st.selectbox("Select Meme Coin", ["Coin A", "Coin B", "Coin C"])
    selected_period = st.selectbox("Select Period", ["Last 24 Hours", "Last Week", "Last Month"])

# Dashboard Layout
st.markdown("<h1 style='text-align: center;'>Meme Coin Radar</h1>", unsafe_allow_html=True)
st.subheader("Market Overview")

# Key Metrics
col1, col2 = st.columns([1, 1], gap="medium")
with col1:
    st.markdown("<h3 style='text-align: center;'>Total Market Cap</h3>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; font-size: 24px;'>${total_market_cap:,.2f}</p>", unsafe_allow_html=True)
with col2:
    total_traded_volume = df_line['total_volume'].iloc[-1]  # Latest total volume
    st.markdown("<h3 style='text-align: center;'>Total Traded Volume (24 hrs)</h3>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; font-size: 24px;'>${total_traded_volume:,.2f}</p>", unsafe_allow_html=True)

# Gauges
col3, col4 = st.columns(2)
with col3:
    fig_bear_bull = go.Figure(go.Indicator(
        mode="gauge+number",
        value=50,  # Mock value or replace with real data
        title={'text': "Bear vs Bull Market"},
        gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "darkblue"}},
    ))
    fig_bear_bull.update_layout(height=400)
    st.plotly_chart(fig_bear_bull, use_container_width=True)
with col4:
    fig_bitcoin_vs_meme = go.Figure(go.Indicator(
        mode="gauge+number",
        value=20,  # Mock value or replace with real data
        title={'text': "Bitcoin vs Meme Coins"},
        gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "orange"}},
    ))
    fig_bitcoin_vs_meme.update_layout(height=400)
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
        title='Traded Volume Over Time'
    )
    fig_line.update_layout(
        height=400,
        yaxis_title="Total Volume",
        xaxis_title="Date",
        margin=dict(l=0, r=0, t=30, b=0)
    )
    st.plotly_chart(fig_line, use_container_width=True)

# Market Movers
st.subheader("Market Movers")
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
    color_continuous_scale=px.colors.sequential.Blues,
    color_continuous_midpoint=0
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

# Trending Meme Coins
st.subheader("Trending Meme Coins")
st.info("This section is under development.")
