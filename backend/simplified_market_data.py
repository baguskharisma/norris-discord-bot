import os
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import mplfinance as mpf
from datetime import datetime, timedelta
import yfinance as yf
from pycoingecko import CoinGeckoAPI
from alpha_vantage.timeseries import TimeSeries
import requests
import io
import base64
from tempfile import NamedTemporaryFile

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants for data fetching
DEFAULT_TIMEFRAME = "1d"  # Daily candles
DEFAULT_PERIOD = "1mo"    # One month of data
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")

class MarketDataProvider:
    """
    Handles retrieving market data from various free APIs.
    Implements fallback mechanisms and optimizes API calls.
    """
    
    def __init__(self):
        """Initialize the data provider with API clients."""
        self.cg = CoinGeckoAPI()
        
    def get_stock_data(self, symbol, period=DEFAULT_PERIOD, interval=DEFAULT_TIMEFRAME):
        """
        Get stock market data using Yahoo Finance.
        
        Args:
            symbol (str): Stock symbol e.g., 'AAPL'
            period (str): Time period e.g., '1mo', '3mo', '6mo', '1y', '5y'
            interval (str): Candle interval e.g., '1d', '1h', '15m'
            
        Returns:
            pd.DataFrame: OHLCV data or None if failed
        """
        try:
            # Try Yahoo Finance first
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period, interval=interval)
            
            if data.empty:
                # If Yahoo Finance fails, try Alpha Vantage as backup
                data = self._get_stock_alpha_vantage(symbol, interval)
                
            if not data.empty:
                # Convert column names to lowercase for consistency
                data.columns = [col.lower() for col in data.columns]
                # Ensure we have the required columns
                if 'open' in data.columns and 'high' in data.columns and 'low' in data.columns and 'close' in data.columns:
                    return data
                    
            logger.warning(f"Failed to get data for stock {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting stock data for {symbol}: {str(e)}")
            return None
            
    def _get_stock_alpha_vantage(self, symbol, interval):
        """Fallback method to get stock data using Alpha Vantage."""
        try:
            ts = TimeSeries(key=ALPHA_VANTAGE_API_KEY, output_format='pandas')
            
            # Map interval to Alpha Vantage format
            if interval in ['1d', 'daily']:
                data, _ = ts.get_daily(symbol=symbol, outputsize='full')
            elif interval in ['1h', '60m', 'hourly']:
                data, _ = ts.get_intraday(symbol=symbol, interval='60min', outputsize='full')
            else:
                logger.warning(f"Unsupported interval {interval} for Alpha Vantage")
                return pd.DataFrame()
                
            # Rename columns to match Yahoo Finance format
            data.columns = ['open', 'high', 'low', 'close', 'volume']
            
            return data
            
        except Exception as e:
            logger.error(f"Error getting Alpha Vantage data for {symbol}: {str(e)}")
            return pd.DataFrame()
            
    def get_crypto_data(self, symbol, vs_currency='usd', days=30):
        """
        Get cryptocurrency market data using CoinGecko.
        
        Args:
            symbol (str): Cryptocurrency ID e.g., 'bitcoin'
            vs_currency (str): Quote currency e.g., 'usd'
            days (int): Number of days of data to fetch
            
        Returns:
            pd.DataFrame: OHLCV data or None if failed
        """
        try:
            # Get market data from CoinGecko
            ohlc = self.cg.get_coin_ohlc_by_id(id=symbol, vs_currency=vs_currency, days=days)
            
            # Convert to DataFrame
            df = pd.DataFrame(ohlc, columns=['timestamp', 'open', 'high', 'low', 'close'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Add volume data if available
            try:
                market_data = self.cg.get_coin_market_chart_by_id(id=symbol, vs_currency=vs_currency, days=days)
                volumes = market_data.get('total_volumes', [])
                if volumes:
                    vol_df = pd.DataFrame(volumes, columns=['timestamp', 'volume'])
                    vol_df['timestamp'] = pd.to_datetime(vol_df['timestamp'], unit='ms')
                    vol_df.set_index('timestamp', inplace=True)
                    
                    # Resample volume data to match OHLC data frequency
                    vol_df = vol_df.resample(df.index.to_series().diff().min()).last().fillna(0)
                    
                    # Join volume data with OHLC data
                    df = df.join(vol_df, how='left')
            except Exception as volume_error:
                logger.warning(f"Could not get volume data for {symbol}: {str(volume_error)}")
                df['volume'] = 0  # Add empty volume column
                
            return df
            
        except Exception as e:
            logger.error(f"Error getting crypto data for {symbol}: {str(e)}")
            return None
            
    def get_forex_data(self, symbol, period=DEFAULT_PERIOD, interval=DEFAULT_TIMEFRAME):
        """
        Get forex market data using Yahoo Finance.
        
        Args:
            symbol (str): Forex pair e.g., 'EURUSD=X'
            period (str): Time period
            interval (str): Candle interval
            
        Returns:
            pd.DataFrame: OHLCV data or None if failed
        """
        try:
            # For forex, Yahoo Finance requires =X suffix if not provided
            if not symbol.endswith('=X'):
                symbol = f"{symbol}=X"
                
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period, interval=interval)
            
            if not data.empty:
                # Convert column names to lowercase for consistency
                data.columns = [col.lower() for col in data.columns]
                return data
                
            logger.warning(f"Failed to get data for forex pair {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting forex data for {symbol}: {str(e)}")
            return None

class TechnicalAnalyzer:
    """
    Performs technical analysis on market data.
    Calculates indicators and identifies trading signals.
    """
    
    @staticmethod
    def add_indicators(df):
        """
        Add technical indicators to the dataframe.
        
        Args:
            df (pd.DataFrame): OHLCV data
            
        Returns:
            pd.DataFrame: Data with indicators
        """
        if df is None or df.empty:
            return None
            
        # Make a copy to avoid changing the original
        df = df.copy()
            
        try:
            # Moving Averages
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_50'] = df['close'].rolling(window=50).mean()
            df['sma_200'] = df['close'].rolling(window=200).mean()
            
            # Exponential Moving Averages
            df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
            df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()
            
            # MACD
            df['macd'] = df['ema_12'] - df['ema_26']
            df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
            df['macd_hist'] = df['macd'] - df['macd_signal']
            
            # RSI (Relative Strength Index)
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            
            avg_gain = gain.rolling(window=14).mean()
            avg_loss = loss.rolling(window=14).mean()
            
            # Calculate RS and RSI
            rs = avg_gain / avg_loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # Bollinger Bands
            df['bb_middle'] = df['close'].rolling(window=20).mean()
            df['bb_std'] = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
            df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']
            
            return df
            
        except Exception as e:
            logger.error(f"Error adding indicators: {str(e)}")
            return df
    
    @staticmethod
    def identify_candlestick_patterns(df):
        """
        Identify candlestick patterns in the data.
        
        Args:
            df (pd.DataFrame): OHLCV data
            
        Returns:
            dict: Identified patterns
        """
        if df is None or df.empty:
            return {}
            
        patterns = {}
        
        try:
            # Get the last 5 candles for pattern identification
            recent = df.tail(5)
            
            # Doji - open and close are very close
            doji_threshold = 0.001  # 0.1% difference between open and close
            recent['doji'] = (abs(recent['close'] - recent['open']) / recent['open']) < doji_threshold
            
            # Hammer - small body, long lower wick, small or no upper wick
            recent['body_size'] = abs(recent['close'] - recent['open'])
            recent['upper_wick'] = recent.apply(lambda x: x['high'] - max(x['open'], x['close']), axis=1)
            recent['lower_wick'] = recent.apply(lambda x: min(x['open'], x['close']) - x['low'], axis=1)
            
            # Hammer criteria
            recent['hammer'] = (
                (recent['body_size'] < (recent['high'] - recent['low']) * 0.4) &  # Small body
                (recent['lower_wick'] > recent['body_size'] * 2) &  # Long lower wick
                (recent['upper_wick'] < recent['body_size'] * 0.3)  # Small upper wick
            )
            
            # Engulfing patterns
            recent['bullish_engulfing'] = False
            recent['bearish_engulfing'] = False
            
            for i in range(1, len(recent)):
                # Bullish engulfing
                if (recent.iloc[i-1]['close'] < recent.iloc[i-1]['open'] and  # Previous candle is red
                    recent.iloc[i]['close'] > recent.iloc[i]['open'] and  # Current candle is green
                    recent.iloc[i]['open'] < recent.iloc[i-1]['close'] and  # Current open below previous close
                    recent.iloc[i]['close'] > recent.iloc[i-1]['open']):  # Current close above previous open
                    recent.loc[recent.index[i], 'bullish_engulfing'] = True
                
                # Bearish engulfing
                if (recent.iloc[i-1]['close'] > recent.iloc[i-1]['open'] and  # Previous candle is green
                    recent.iloc[i]['close'] < recent.iloc[i]['open'] and  # Current candle is red
                    recent.iloc[i]['open'] > recent.iloc[i-1]['close'] and  # Current open above previous close
                    recent.iloc[i]['close'] < recent.iloc[i-1]['open']):  # Current close below previous open
                    recent.loc[recent.index[i], 'bearish_engulfing'] = True
            
            # Morning Star
            morning_star = False
            if len(recent) >= 3:
                morning_star = (
                    recent.iloc[-3]['close'] < recent.iloc[-3]['open'] and  # First candle is red
                    abs(recent.iloc[-2]['close'] - recent.iloc[-2]['open']) < recent.iloc[-2]['high'] * 0.01 and  # Middle candle is doji
                    recent.iloc[-1]['close'] > recent.iloc[-1]['open'] and  # Last candle is green
                    recent.iloc[-1]['close'] > (recent.iloc[-3]['open'] + recent.iloc[-3]['close']) / 2  # Last close is above middle of first candle
                )
            
            # Evening Star
            evening_star = False
            if len(recent) >= 3:
                evening_star = (
                    recent.iloc[-3]['close'] > recent.iloc[-3]['open'] and  # First candle is green
                    abs(recent.iloc[-2]['close'] - recent.iloc[-2]['open']) < recent.iloc[-2]['high'] * 0.01 and  # Middle candle is doji
                    recent.iloc[-1]['close'] < recent.iloc[-1]['open'] and  # Last candle is red
                    recent.iloc[-1]['close'] < (recent.iloc[-3]['open'] + recent.iloc[-3]['close']) / 2  # Last close is below middle of first candle
                )
            
            # Compile patterns
            patterns = {
                'doji': recent['doji'].iloc[-1],
                'hammer': recent['hammer'].iloc[-1],
                'bullish_engulfing': recent['bullish_engulfing'].iloc[-1],
                'bearish_engulfing': recent['bearish_engulfing'].iloc[-1],
                'morning_star': morning_star,
                'evening_star': evening_star
            }
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error identifying candlestick patterns: {str(e)}")
            return {}
    
    @staticmethod
    def generate_trade_signals(df, patterns):
        """
        Generate trading signals based on technical analysis.
        
        Args:
            df (pd.DataFrame): OHLCV data with indicators
            patterns (dict): Identified candlestick patterns
            
        Returns:
            dict: Trading signals and recommendations
        """
        if df is None or df.empty:
            return {'signal': 'HOLD', 'confidence': 0, 'reasons': ['Insufficient data']}
            
        signals = []
        confidence_factors = []
        reasons = []
        
        try:
            # Get the most recent data point
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else None
            
            # Trend Analysis based on moving averages
            if 'sma_20' in df.columns and 'sma_50' in df.columns and not pd.isna(latest['sma_20']) and not pd.isna(latest['sma_50']):
                # Golden Cross (20 SMA crosses above 50 SMA)
                if prev is not None and prev['sma_20'] <= prev['sma_50'] and latest['sma_20'] > latest['sma_50']:
                    signals.append(('BUY', 2))
                    reasons.append("Golden Cross (20 SMA crossed above 50 SMA)")
                
                # Death Cross (20 SMA crosses below 50 SMA)
                elif prev is not None and prev['sma_20'] >= prev['sma_50'] and latest['sma_20'] < latest['sma_50']:
                    signals.append(('SELL', 2))
                    reasons.append("Death Cross (20 SMA crossed below 50 SMA)")
                    
                # Price above both MAs
                elif latest['close'] > latest['sma_20'] and latest['close'] > latest['sma_50']:
                    signals.append(('BUY', 1))
                    reasons.append("Price above both 20 and 50 SMAs, indicating bullish trend")
                    
                # Price below both MAs
                elif latest['close'] < latest['sma_20'] and latest['close'] < latest['sma_50']:
                    signals.append(('SELL', 1))
                    reasons.append("Price below both 20 and 50 SMAs, indicating bearish trend")
            
            # RSI Analysis
            if 'rsi' in df.columns and not pd.isna(latest['rsi']):
                if latest['rsi'] < 30:
                    signals.append(('BUY', 1))
                    reasons.append(f"RSI oversold at {latest['rsi']:.2f}")
                elif latest['rsi'] > 70:
                    signals.append(('SELL', 1))
                    reasons.append(f"RSI overbought at {latest['rsi']:.2f}")
            
            # MACD Analysis
            if all(k in df.columns for k in ['macd', 'macd_signal']) and not pd.isna(latest['macd']) and not pd.isna(latest['macd_signal']):
                if prev is not None and prev['macd'] <= prev['macd_signal'] and latest['macd'] > latest['macd_signal']:
                    signals.append(('BUY', 1.5))
                    reasons.append("MACD crossed above signal line")
                elif prev is not None and prev['macd'] >= prev['macd_signal'] and latest['macd'] < latest['macd_signal']:
                    signals.append(('SELL', 1.5))
                    reasons.append("MACD crossed below signal line")
                    
            # Bollinger Bands Analysis
            if all(k in df.columns for k in ['bb_upper', 'bb_lower']) and not pd.isna(latest['bb_upper']) and not pd.isna(latest['bb_lower']):
                if latest['close'] < latest['bb_lower']:
                    signals.append(('BUY', 1))
                    reasons.append("Price below lower Bollinger Band, potentially oversold")
                elif latest['close'] > latest['bb_upper']:
                    signals.append(('SELL', 1))
                    reasons.append("Price above upper Bollinger Band, potentially overbought")
                    
            # Candlestick Pattern Analysis
            if patterns:
                if patterns.get('bullish_engulfing', False) or patterns.get('morning_star', False):
                    signals.append(('BUY', 1.5))
                    pattern_names = []
                    if patterns.get('bullish_engulfing', False):
                        pattern_names.append("Bullish Engulfing")
                    if patterns.get('morning_star', False):
                        pattern_names.append("Morning Star")
                    reasons.append(f"Bullish candlestick pattern detected: {', '.join(pattern_names)}")
                    
                if patterns.get('bearish_engulfing', False) or patterns.get('evening_star', False):
                    signals.append(('SELL', 1.5))
                    pattern_names = []
                    if patterns.get('bearish_engulfing', False):
                        pattern_names.append("Bearish Engulfing")
                    if patterns.get('evening_star', False):
                        pattern_names.append("Evening Star")
                    reasons.append(f"Bearish candlestick pattern detected: {', '.join(pattern_names)}")
                    
                if patterns.get('doji', False):
                    signals.append(('HOLD', 0.5))
                    reasons.append("Doji candlestick pattern indicates indecision")
                    
                if patterns.get('hammer', False):
                    signals.append(('BUY', 1))
                    reasons.append("Hammer candlestick pattern indicates potential reversal")
            
            # Calculate overall signal
            if not signals:
                return {'signal': 'HOLD', 'confidence': 0, 'reasons': ['No clear signals detected']}
                
            # Tally the signals
            buy_confidence = sum(weight for signal, weight in signals if signal == 'BUY')
            sell_confidence = sum(weight for signal, weight in signals if signal == 'SELL')
            hold_confidence = sum(weight for signal, weight in signals if signal == 'HOLD')
            
            # Determine the final signal
            if buy_confidence > sell_confidence and buy_confidence > hold_confidence:
                signal = 'BUY'
                confidence = min(buy_confidence / (buy_confidence + sell_confidence + hold_confidence) * 100, 100)
            elif sell_confidence > buy_confidence and sell_confidence > hold_confidence:
                signal = 'SELL'
                confidence = min(sell_confidence / (buy_confidence + sell_confidence + hold_confidence) * 100, 100)
            else:
                signal = 'HOLD'
                confidence = min(hold_confidence / (buy_confidence + sell_confidence + hold_confidence) * 100 if (buy_confidence + sell_confidence + hold_confidence) > 0 else 50, 100)
            
            return {
                'signal': signal,
                'confidence': round(confidence, 1),
                'reasons': reasons
            }
            
        except Exception as e:
            logger.error(f"Error generating trade signals: {str(e)}")
            return {'signal': 'HOLD', 'confidence': 0, 'reasons': [f'Error in analysis: {str(e)}']}
    
    @staticmethod
    def calculate_risk_management(df, signal, entry_price=None):
        """
        Calculate optimal stop-loss and take-profit levels.
        
        Args:
            df (pd.DataFrame): OHLCV data
            signal (str): Trading signal (BUY, SELL, HOLD)
            entry_price (float, optional): Current entry price, defaults to last close
            
        Returns:
            dict: Risk management parameters
        """
        if df is None or df.empty or signal == 'HOLD':
            return {
                'entry_price': None,
                'stop_loss': None,
                'take_profit': None,
                'risk_reward_ratio': None
            }
            
        try:
            # Use the last close as entry price if none provided
            if entry_price is None:
                entry_price = df['close'].iloc[-1]
                
            # Calculate volatility (Average True Range)
            high_low = df['high'] - df['low']
            high_close = abs(df['high'] - df['close'].shift())
            low_close = abs(df['low'] - df['close'].shift())
            
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            atr = true_range.rolling(window=14).mean().iloc[-1]
            
            # Calculate support and resistance levels
            recent_lows = df['low'].rolling(window=20).min().iloc[-1]
            recent_highs = df['high'].rolling(window=20).max().iloc[-1]
            
            if signal == 'BUY':
                # For BUY signal, set stop loss below recent support
                stop_loss = max(entry_price - 2 * atr, recent_lows - 0.5 * atr)
                
                # Set take profit at multiple of risk
                risk = entry_price - stop_loss
                take_profit = entry_price + (risk * 2)  # 2:1 reward-to-risk ratio
                
            else:  # SELL signal
                # For SELL signal, set stop loss above recent resistance
                stop_loss = min(entry_price + 2 * atr, recent_highs + 0.5 * atr)
                
                # Set take profit at multiple of risk
                risk = stop_loss - entry_price
                take_profit = entry_price - (risk * 2)  # 2:1 reward-to-risk ratio
                
            # Calculate risk-reward ratio
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            risk_reward_ratio = round(reward / risk, 2) if risk > 0 else None
            
            return {
                'entry_price': round(entry_price, 4),
                'stop_loss': round(stop_loss, 4),
                'take_profit': round(take_profit, 4),
                'risk_reward_ratio': risk_reward_ratio
            }
            
        except Exception as e:
            logger.error(f"Error calculating risk management: {str(e)}")
            return {
                'entry_price': entry_price,
                'stop_loss': None,
                'take_profit': None,
                'risk_reward_ratio': None
            }

class ChartGenerator:
    """
    Creates visualizations for market data.
    """
    
    @staticmethod
    def generate_candlestick_chart(df, title="", indicators=True):
        """
        Generate a candlestick chart with technical indicators.
        
        Args:
            df (pd.DataFrame): OHLCV data with indicators
            title (str): Chart title
            indicators (bool): Whether to include indicators
            
        Returns:
            str: Base64 encoded image
        """
        if df is None or df.empty:
            return None
            
        try:
            # Select last 60 days of data to avoid overcrowding
            df = df.tail(60).copy()
            
            # Prepare plot configuration
            mc = mpf.make_marketcolors(
                up='green',
                down='red',
                edge='inherit',
                wick='inherit',
                volume='inherit'
            )
            s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':', y_on_right=False)
            
            # Prepare subplots for indicators
            subplots = {}
            plot_specs = {}
            
            # Add MACD subplot if available
            if 'macd' in df.columns and 'macd_signal' in df.columns and indicators:
                df['macd_hist_color'] = np.where(df['macd_hist'] > 0, 'g', 'r')
                subplots['MACD'] = indicators
                plot_specs['MACD'] = {
                    'macd': {'color': 'blue'},
                    'macd_signal': {'color': 'red'}
                }
                
            # Add RSI subplot if available
            if 'rsi' in df.columns and indicators:
                subplots['RSI'] = indicators
                plot_specs['RSI'] = {
                    'rsi': {'color': 'purple'}
                }
                
            # Add plot overlays for moving averages if available
            apds = []
            if 'sma_20' in df.columns and indicators:
                apds.append(mpf.make_addplot(df['sma_20'], color='blue'))
            if 'sma_50' in df.columns and indicators:
                apds.append(mpf.make_addplot(df['sma_50'], color='orange'))
                
            # Add Bollinger Bands if available
            if all(k in df.columns for k in ['bb_upper', 'bb_lower', 'bb_middle']) and indicators:
                apds.append(mpf.make_addplot(df['bb_upper'], color='gray', linestyle='--'))
                apds.append(mpf.make_addplot(df['bb_middle'], color='gray'))
                apds.append(mpf.make_addplot(df['bb_lower'], color='gray', linestyle='--'))
                
            # Create a temporary file to save the plot
            with NamedTemporaryFile(suffix='.png') as tmpfile:
                # Create the candlestick plot
                if subplots:
                    # Plot with subplots for indicators
                    mpf.plot(
                        df,
                        type='candle',
                        style=s,
                        title=title,
                        ylabel='Price',
                        volume=True if 'volume' in df.columns else False,
                        figsize=(10, 8),
                        savefig=tmpfile.name,
                        tight_layout=True,
                        addplot=apds if apds else None,
                        panel_ratios=(4, 1) if len(subplots) == 1 else (6, 1, 1) if len(subplots) == 2 else None,
                        **subplots
                    )
                else:
                    # Plot just the candlestick chart
                    mpf.plot(
                        df,
                        type='candle',
                        style=s,
                        title=title,
                        ylabel='Price',
                        volume=True if 'volume' in df.columns else False,
                        figsize=(10, 6),
                        savefig=tmpfile.name,
                        tight_layout=True,
                        addplot=apds if apds else None
                    )
                
                # Read the image and convert to base64
                with open(tmpfile.name, 'rb') as img_file:
                    img_data = base64.b64encode(img_file.read()).decode('utf-8')
                    
                return img_data
                
        except Exception as e:
            logger.error(f"Error generating candlestick chart: {str(e)}")
            return None
    
    @staticmethod
    def generate_interactive_chart(df, title=""):
        """
        Generate an interactive HTML candlestick chart using Plotly.
        
        Args:
            df (pd.DataFrame): OHLCV data with indicators
            title (str): Chart title
            
        Returns:
            str: HTML string with interactive chart
        """
        if df is None or df.empty:
            return None
            
        try:
            # Select last 90 days of data to avoid overcrowding
            df = df.tail(90).copy()
            
            # Create candlestick chart
            fig = go.Figure()
            
            # Add candlestick trace
            fig.add_trace(go.Candlestick(
                x=df.index,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='Price'
            ))
            
            # Add volume trace if available
            if 'volume' in df.columns:
                fig.add_trace(go.Bar(
                    x=df.index,
                    y=df['volume'],
                    name='Volume',
                    marker_color='rgba(0, 0, 255, 0.3)',
                    yaxis='y2'
                ))
                
            # Add moving average traces if available
            if 'sma_20' in df.columns:
                fig.add_trace(go.Scatter(
                    x=df.index,
                    y=df['sma_20'],
                    name='20 SMA',
                    line=dict(color='blue', width=1)
                ))
                
            if 'sma_50' in df.columns:
                fig.add_trace(go.Scatter(
                    x=df.index,
                    y=df['sma_50'],
                    name='50 SMA',
                    line=dict(color='orange', width=1)
                ))
                
            # Add Bollinger Bands if available
            if all(k in df.columns for k in ['bb_upper', 'bb_lower', 'bb_middle']):
                fig.add_trace(go.Scatter(
                    x=df.index,
                    y=df['bb_upper'],
                    name='BB Upper',
                    line=dict(color='gray', width=1, dash='dash')
                ))
                
                fig.add_trace(go.Scatter(
                    x=df.index,
                    y=df['bb_middle'],
                    name='BB Middle',
                    line=dict(color='gray', width=1)
                ))
                
                fig.add_trace(go.Scatter(
                    x=df.index,
                    y=df['bb_lower'],
                    name='BB Lower',
                    line=dict(color='gray', width=1, dash='dash')
                ))
                
            # Update layout
            fig.update_layout(
                title=title,
                xaxis_title='Date',
                yaxis_title='Price',
                height=600,
                template='plotly_dark',
                xaxis_rangeslider_visible=False,
                yaxis2=dict(
                    title='Volume',
                    overlaying='y',
                    side='right',
                    showgrid=False,
                    visible=False
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            # Convert to HTML
            html = fig.to_html(full_html=False, include_plotlyjs='cdn')
            return html
            
        except Exception as e:
            logger.error(f"Error generating interactive chart: {str(e)}")
            return None

class MarketAnalyzer:
    """
    Conducts comprehensive market analysis.
    Combines data retrieval, technical analysis, and chart generation.
    """
    
    def __init__(self):
        """Initialize the market analyzer."""
        self.data_provider = MarketDataProvider()
        
    def analyze_asset(self, asset_type, symbol, timeframe=DEFAULT_TIMEFRAME, period=DEFAULT_PERIOD):
        """
        Perform comprehensive analysis on an asset.
        
        Args:
            asset_type (str): Asset type ('stock', 'crypto', 'forex')
            symbol (str): Asset symbol
            timeframe (str): Time interval for candles
            period (str): Historical period to analyze
            
        Returns:
            dict: Analysis results
        """
        try:
            # Get market data based on asset type
            if asset_type.lower() == 'stock':
                df = self.data_provider.get_stock_data(symbol, period, timeframe)
            elif asset_type.lower() == 'crypto':
                # Convert period to days for crypto
                days = 30
                if period == '1mo':
                    days = 30
                elif period == '3mo':
                    days = 90
                elif period == '6mo':
                    days = 180
                elif period == '1y':
                    days = 365
                df = self.data_provider.get_crypto_data(symbol, days=days)
            elif asset_type.lower() == 'forex':
                df = self.data_provider.get_forex_data(symbol, period, timeframe)
            else:
                return {"error": f"Unsupported asset type: {asset_type}"}
                
            if df is None or df.empty:
                return {"error": f"Failed to retrieve data for {symbol}"}
                
            # Calculate last price and day change
            last_price = df['close'].iloc[-1]
            prev_price = df['close'].iloc[-2] if len(df) > 1 else last_price
            day_change = last_price - prev_price
            day_change_percent = (day_change / prev_price) * 100 if prev_price > 0 else 0
                
            # Add technical indicators
            df_with_indicators = TechnicalAnalyzer.add_indicators(df)
                
            # Identify candlestick patterns
            patterns = TechnicalAnalyzer.identify_candlestick_patterns(df_with_indicators)
                
            # Generate trading signals
            signals = TechnicalAnalyzer.generate_trade_signals(df_with_indicators, patterns)
                
            # Calculate risk management parameters
            risk_mgmt = TechnicalAnalyzer.calculate_risk_management(df, signals['signal'], last_price)
                
            # Generate chart image
            chart_img = ChartGenerator.generate_candlestick_chart(
                df_with_indicators,
                title=f"{symbol} - {timeframe} Timeframe"
            )
                
            # Create interactive HTML chart
            interactive_chart = ChartGenerator.generate_interactive_chart(
                df_with_indicators,
                title=f"{symbol} - {timeframe} Timeframe"
            )
                
            # Compile results
            analysis = {
                "symbol": symbol,
                "asset_type": asset_type,
                "timeframe": timeframe,
                "last_price": round(last_price, 4),
                "day_change": round(day_change, 4),
                "day_change_percent": round(day_change_percent, 2),
                "signal": signals['signal'],
                "confidence": signals['confidence'],
                "reasons": signals['reasons'],
                "risk_management": risk_mgmt,
                "patterns": patterns,
                "image": chart_img,
                "interactive_chart": interactive_chart,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
                
            return analysis
                
        except Exception as e:
            logger.error(f"Error analyzing {asset_type} {symbol}: {str(e)}")
            return {"error": f"Analysis failed: {str(e)}"}
    
    def get_market_overview(self):
        """
        Get an overview of major markets.
        
        Returns:
            dict: Market overview data
        """
        try:
            # Define major indices and assets to track
            indices = {
                'stocks': [
                    {'symbol': 'SPY', 'name': 'S&P 500 ETF'},
                    {'symbol': 'QQQ', 'name': 'Nasdaq 100 ETF'},
                    {'symbol': 'DIA', 'name': 'Dow Jones ETF'},
                    {'symbol': 'IWM', 'name': 'Russell 2000 ETF'}
                ],
                'crypto': [
                    {'symbol': 'bitcoin', 'name': 'Bitcoin'},
                    {'symbol': 'ethereum', 'name': 'Ethereum'},
                    {'symbol': 'solana', 'name': 'Solana'},
                    {'symbol': 'binancecoin', 'name': 'BNB'}
                ],
                'forex': [
                    {'symbol': 'EURUSD=X', 'name': 'EUR/USD'},
                    {'symbol': 'GBPUSD=X', 'name': 'GBP/USD'},
                    {'symbol': 'USDJPY=X', 'name': 'USD/JPY'},
                    {'symbol': 'AUDUSD=X', 'name': 'AUD/USD'}
                ]
            }
            
            results = {
                'stocks': [],
                'crypto': [],
                'forex': [],
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Analyze each stock index
            for index in indices['stocks']:
                try:
                    df = self.data_provider.get_stock_data(index['symbol'], '5d', '1d')
                    if df is not None and not df.empty:
                        last_price = df['close'].iloc[-1]
                        prev_price = df['close'].iloc[-2] if len(df) > 1 else last_price
                        day_change = last_price - prev_price
                        day_change_percent = (day_change / prev_price) * 100 if prev_price > 0 else 0
                        
                        # Add indicators
                        df_with_indicators = TechnicalAnalyzer.add_indicators(df)
                        
                        # Generate signals
                        patterns = TechnicalAnalyzer.identify_candlestick_patterns(df_with_indicators)
                        signals = TechnicalAnalyzer.generate_trade_signals(df_with_indicators, patterns)
                        
                        results['stocks'].append({
                            'name': index['name'],
                            'symbol': index['symbol'],
                            'last_price': round(last_price, 2),
                            'day_change_percent': round(day_change_percent, 2),
                            'signal': signals['signal']
                        })
                except Exception as e:
                    logger.error(f"Error analyzing stock index {index['symbol']}: {str(e)}")
            
            # Analyze cryptocurrencies
            for crypto in indices['crypto']:
                try:
                    df = self.data_provider.get_crypto_data(crypto['symbol'], days=7)
                    if df is not None and not df.empty:
                        last_price = df['close'].iloc[-1]
                        prev_price = df['close'].iloc[-2] if len(df) > 1 else last_price
                        day_change = last_price - prev_price
                        day_change_percent = (day_change / prev_price) * 100 if prev_price > 0 else 0
                        
                        # Add indicators
                        df_with_indicators = TechnicalAnalyzer.add_indicators(df)
                        
                        # Generate signals
                        patterns = TechnicalAnalyzer.identify_candlestick_patterns(df_with_indicators)
                        signals = TechnicalAnalyzer.generate_trade_signals(df_with_indicators, patterns)
                        
                        results['crypto'].append({
                            'name': crypto['name'],
                            'symbol': crypto['symbol'],
                            'last_price': round(last_price, 2),
                            'day_change_percent': round(day_change_percent, 2),
                            'signal': signals['signal']
                        })
                except Exception as e:
                    logger.error(f"Error analyzing crypto {crypto['symbol']}: {str(e)}")
            
            # Analyze forex pairs
            for pair in indices['forex']:
                try:
                    df = self.data_provider.get_forex_data(pair['symbol'], '5d', '1d')
                    if df is not None and not df.empty:
                        last_price = df['close'].iloc[-1]
                        prev_price = df['close'].iloc[-2] if len(df) > 1 else last_price
                        day_change = last_price - prev_price
                        day_change_percent = (day_change / prev_price) * 100 if prev_price > 0 else 0
                        
                        # Add indicators
                        df_with_indicators = TechnicalAnalyzer.add_indicators(df)
                        
                        # Generate signals
                        patterns = TechnicalAnalyzer.identify_candlestick_patterns(df_with_indicators)
                        signals = TechnicalAnalyzer.generate_trade_signals(df_with_indicators, patterns)
                        
                        results['forex'].append({
                            'name': pair['name'],
                            'symbol': pair['symbol'],
                            'last_price': round(last_price, 4),
                            'day_change_percent': round(day_change_percent, 2),
                            'signal': signals['signal']
                        })
                except Exception as e:
                    logger.error(f"Error analyzing forex pair {pair['symbol']}: {str(e)}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error generating market overview: {str(e)}")
            return {"error": f"Market overview failed: {str(e)}"}