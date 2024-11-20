import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Set the page configuration
st.set_page_config(page_title="Meme Coin Radar", layout="wide")

# Center the title above all plots
st.markdown("<h1 style='text-align: center;'>Meme Coin Radar</h1>", unsafe_allow_html=True)

# Base URL for the FastAPI endpoints
base_url = "http://0.0.0.0:8080"

# Function to fetch data from an endpoint
def fetch_data(endpoint):
    response = requests.get(f"{base_url}/{endpoint}")
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Failed to fetch data from /{endpoint}")
        st.stop()

# Fetch data from the endpoints
top_coins_data = fetch_data("top-coins")
top_gainers_data = fetch_data("top-gainers")
top_losers_data = fetch_data("top-losers")

# Extract total market cap
total_market_cap = top_coins_data.get('total_market_cap', 0)

# Extract top 10 coins data
top_10_coins = top_coins_data.get('top_10_coins', [])

# Prepare data for treemap
treemap_df = pd.DataFrame(top_10_coins)
treemap_df['market_cap'] = pd.to_numeric(treemap_df['market_cap'], errors='coerce')
treemap_df['last_price'] = pd.to_numeric(treemap_df['last_price'], errors='coerce')

# Calculate total market cap of others
others_market_cap = total_market_cap - treemap_df['market_cap'].sum()

# Add 'Others' row if market cap is positive
if others_market_cap > 0:
    others_row = pd.DataFrame({
        'symbol': ['Others'],
        'market_cap': [others_market_cap],
        'last_price': [None]  # No price for 'Others'
    })
    treemap_df = pd.concat([treemap_df, others_row], ignore_index=True)

# Create 'price_text' column for formatted price
def format_price_text(price):
    if pd.notnull(price):
        return f"<br>Price: ${price:,.6f}"
    else:
        return ""  # Empty string for 'Others'

treemap_df['price_text'] = treemap_df['last_price'].apply(format_price_text)

# Create the treemap
fig = px.treemap(
    treemap_df,
    path=['symbol'],
    values='market_cap',
    title='Top 10 Meme Coins by Market Cap',
    labels={'symbol': 'Coin'},
    custom_data=['price_text']
)

# Update the traces
fig.update_traces(
    textinfo='label+value',
    texttemplate='<b>%{label}</b><br>Market Cap: $%{value:,.2f}%{customdata[0]}',
    hovertemplate='<b>%{label}</b><br>Market Cap: $%{value:,.2f}%{customdata[0]}<extra></extra>'
)

# Create the layout with three columns on top
col1, col2, col3 = st.columns(3)

# Upper Left: Plotly Indicator for total market cap
with col1:
    fig1 = go.Figure(go.Indicator(
        mode="number",
        value=total_market_cap,
        number={'prefix': "$", 'valueformat': ',.2f'},
        title={'text': "Total Meme Coin Market Cap"},
        domain={'x': [0, 1], 'y': [0, 1]}
    ))
    fig1.update_layout(height=300)  # Adjust height to match other plots
    st.plotly_chart(fig1, use_container_width=True)

# Upper Center: Mock gauge plot of bear vs bull market
with col2:
    fig2 = go.Figure(go.Indicator(
        mode="gauge+number",
        value=50,  # Mock value
        title={'text': "Bear vs Bull Market"},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 50], 'color': "red"},
                {'range': [50, 100], 'color': "green"}
            ]
        },
        domain={'x': [0, 1], 'y': [0, 1]}
    ))
    fig2.update_layout(height=300)
    st.plotly_chart(fig2, use_container_width=True)

# Upper Right: Mock gauge plot of Bitcoin vs Meme Coins
with col3:
    fig3 = go.Figure(go.Indicator(
        mode="gauge+number",
        value=20,  # Mock value
        title={'text': "Bitcoin vs Meme Coins"},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 50], 'color': "orange"},
                {'range': [50, 100], 'color': "purple"}
            ]
        },
        domain={'x': [0, 1], 'y': [0, 1]}
    ))
    fig3.update_layout(height=300)
    st.plotly_chart(fig3, use_container_width=True)

# Create the layout with three columns in the center
col_left, col_center, col_right = st.columns(3)

# Center Left: Time series plot of top gainers
with col_left:
    if 'top_movers' in top_gainers_data and top_gainers_data['top_movers']:
        top_gainers = top_gainers_data.get('top_movers', [])
        gainers_dfs = []
        for coin in top_gainers:
            df = pd.DataFrame(coin['price_history'])
            df['symbol'] = coin['symbol']
            df['percentage_change'] = coin['percentage_change']
            gainers_dfs.append(df)
        if gainers_dfs:
            gainers_df = pd.concat(gainers_dfs, ignore_index=True)
            gainers_df['date'] = pd.to_datetime(gainers_df['date'])
            gainers_df.sort_values(['symbol', 'date'], inplace=True)
            # Calculate percentage change over time
            gainers_df['first_price'] = gainers_df.groupby('symbol')['price'].transform('first')
            gainers_df['percentage_change'] = ((gainers_df['price'] - gainers_df['first_price']) / gainers_df['first_price']) * 100
            fig4 = px.line(
                gainers_df,
                x='date',
                y='percentage_change',
                color='symbol',
                title='Top Gainers Over Last 7 Days',
                hover_data={'price': ':.6f'}
            )
            fig4.update_layout(yaxis_title='Percentage Change (%)')
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.write("No data available for top gainers.")
    else:
        st.write("No data available for top gainers.")

# Center Center: Treemap plot of top 10 meme coins
with col_center:
    if not treemap_df.empty:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.write("No data available for top 10 coins.")

# Center Right: Time series plot of top losers
with col_right:
    if 'top_movers' in top_losers_data and top_losers_data['top_movers']:
        top_losers = top_losers_data.get('top_movers', [])
        losers_dfs = []
        for coin in top_losers:
            df = pd.DataFrame(coin['price_history'])
            df['symbol'] = coin['symbol']
            df['percentage_change'] = coin['percentage_change']
            losers_dfs.append(df)
        if losers_dfs:
            losers_df = pd.concat(losers_dfs, ignore_index=True)
            losers_df['date'] = pd.to_datetime(losers_df['date'])
            losers_df.sort_values(['symbol', 'date'], inplace=True)
            # Calculate percentage change over time
            losers_df['first_price'] = losers_df.groupby('symbol')['price'].transform('first')
            losers_df['percentage_change'] = ((losers_df['price'] - losers_df['first_price']) / losers_df['first_price']) * 100
            fig5 = px.line(
                losers_df,
                x='date',
                y='percentage_change',
                color='symbol',
                title='Top Losers Over Last 7 Days',
                hover_data={'price': ':.6f'}
            )
            fig5.update_layout(yaxis_title='Percentage Change (%)')
            st.plotly_chart(fig5, use_container_width=True)
        else:
            st.write("No data available for top losers.")
    else:
        st.write("No data available for top losers.")

# Add the note in the bottom right corner
st.markdown(
    """
    <style>
    .fixed-footer {
        position: fixed;
        right: 0;
        bottom: 0;
        padding: 10px;
        background-color: rgba(255, 255, 255, 0.5);
        text-align: right;
        font-size: 12px;
    }
    </style>
    <div class="fixed-footer">
        Curated by <a href="https://www.linkedin.com/in/xavigrowth/" target="_blank">Xavier Carrera</a>
    </div>
    """,
    unsafe_allow_html=True
)
