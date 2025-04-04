import os
import logging
import pandas as pd
import numpy as np
import mplfinance as mpf
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from datetime import datetime, timedelta
import yfinance as yf
from pycoingecko import CoinGeckoAPI
from alpha_vantage.timeseries import TimeSeries
import requests
import io
import base64
from tempfile import NamedTemporaryFile
import pandas_ta as ta

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
DEFAULT_TIMEFRAME = '1d'
DEFAULT_PERIOD = '1mo'
DEFAULT_LIMIT = 100

class MarketDataProvider:
    """
    Handles retrieving market data from various free APIs.
    Implements fallback mechanisms and optimizes API calls.
    """
    
    def __init__(self):
        """Initialize the data provider with API clients."""
        self.cg = CoinGeckoAPI()
        # Initialize Alpha Vantage with free API key if available
        self.alpha_vantage_key = os.environ.get('ALPHA_VANTAGE_KEY', '')
        
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
            logger.info(f"Fetching stock data for {symbol} ({period}, {interval})")
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period, interval=interval)
            
            if data.empty:
                logger.warning(f"No data returned for {symbol}")
                return None
                
            # Ensure data has standard column names
            data = data.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            return data
            
        except Exception as e:
            logger.error(f"Error fetching stock data: {str(e)}")
            # Try Alpha Vantage as fallback if available
            if self.alpha_vantage_key:
                return self._get_stock_alpha_vantage(symbol, interval)
            return None
    
    def _get_stock_alpha_vantage(self, symbol, interval):
        """Fallback method to get stock data using Alpha Vantage."""
        try:
            logger.info(f"Using Alpha Vantage fallback for {symbol}")
            ts = TimeSeries(key=self.alpha_vantage_key, output_format='pandas')
            
            # Map intervals to Alpha Vantage format
            av_interval = '60min' if interval == '1h' else 'daily'
            
            if av_interval == 'daily':
                data, _ = ts.get_daily(symbol=symbol, outputsize='full')
            else:
                data, _ = ts.get_intraday(symbol=symbol, interval=av_interval, outputsize='full')
                
            # Rename columns to standard format
            data = data.rename(columns={
                '1. open': 'open',
                '2. high': 'high',
                '3. low': 'low',
                '4. close': 'close',
                '5. volume': 'volume'
            })
            
            return data
            
        except Exception as e:
            logger.error(f"Alpha Vantage fallback failed: {str(e)}")
            return None
    
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
            logger.info(f"Fetching crypto data for {symbol}/{vs_currency} for {days} days")
            # Get market data
            market_data = self.cg.get_coin_market_chart_by_id(id=symbol, vs_currency=vs_currency, days=days)
            
            # Extract price and volume data
            timestamps = [datetime.fromtimestamp(t/1000) for t, _ in market_data['prices']]
            prices = [p for _, p in market_data['prices']]
            volumes = [v for _, v in market_data['total_volumes']]
            
            # Create DataFrame
            df = pd.DataFrame({
                'timestamp': timestamps,
                'close': prices,
                'volume': volumes
            })
            
            # Set timestamp as index
            df.set_index('timestamp', inplace=True)
            
            # Since CoinGecko only provides close prices, we need to resample to get OHLC
            # This is a simplification as we're missing true OHLC data
            ohlc = df['close'].resample('1D').ohlc()
            volume = df['volume'].resample('1D').sum()
            
            # Combine OHLC and volume
            result = pd.concat([ohlc, volume], axis=1)
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching crypto data: {str(e)}")
            # Try alternative source if available
            # For now just return None
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
        # For forex, we simply use Yahoo Finance with appropriate symbol format
        if not symbol.endswith('=X'):
            symbol = f"{symbol}=X"
        
        return self.get_stock_data(symbol, period, interval)


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
            
        # Make a copy to avoid modifying the original
        df = df.copy()
        
        # Ensure we have the right column names
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        # Check if columns exist or need renaming
        for col in required_cols:
            if col not in df.columns and col.capitalize() in df.columns:
                df[col] = df[col.capitalize()]
        
        # If still missing required columns, can't proceed
        if not all(col in df.columns for col in ['open', 'high', 'low', 'close']):
            logger.error("DataFrame missing required OHLC columns")
            return None
        
        # Calculate moving averages
        df['sma20'] = df['close'].rolling(window=20).mean()
        df['sma50'] = df['close'].rolling(window=50).mean()
        df['sma200'] = df['close'].rolling(window=200).mean()
        
        # Calculate RSI
        try:
            df['rsi'] = ta.rsi(df['close'], length=14)
        except Exception as e:
            logger.warning(f"Error calculating RSI: {str(e)}")
            df['rsi'] = np.nan
        
        # Calculate MACD
        try:
            macd = ta.macd(df['close'])
            df['macd'] = macd['MACD_12_26_9']
            df['macd_signal'] = macd['MACDs_12_26_9']
            df['macd_hist'] = macd['MACDh_12_26_9']
        except Exception as e:
            logger.warning(f"Error calculating MACD: {str(e)}")
            df['macd'] = df['macd_signal'] = df['macd_hist'] = np.nan
        
        # Calculate Bollinger Bands
        try:
            bbands = ta.bbands(df['close'], length=20)
            df['bb_upper'] = bbands['BBU_20_2.0']
            df['bb_middle'] = bbands['BBM_20_2.0']
            df['bb_lower'] = bbands['BBL_20_2.0']
        except Exception as e:
            logger.warning(f"Error calculating Bollinger Bands: {str(e)}")
            df['bb_upper'] = df['bb_middle'] = df['bb_lower'] = np.nan
        
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
        if df is None or df.empty or len(df) < 5:
            return {}
        
        patterns = {}
        
        # Get the last 5 candles for pattern recognition
        recent = df.tail(5)
        
        # Doji pattern (open and close are very close)
        doji_threshold = 0.001  # 0.1% difference between open and close
        last_candle = recent.iloc[-1]
        if abs(last_candle['close'] - last_candle['open']) / last_candle['open'] < doji_threshold:
            patterns['doji'] = {
                'type': 'Doji',
                'description': 'Indecision in the market, potential reversal signal',
                'strength': 'moderate'
            }
        
        # Bullish Engulfing pattern
        if len(recent) >= 2:
            prev_candle = recent.iloc[-2]
            curr_candle = recent.iloc[-1]
            
            if (prev_candle['close'] < prev_candle['open'] and  # Previous candle is bearish
                curr_candle['close'] > curr_candle['open'] and  # Current candle is bullish
                curr_candle['open'] < prev_candle['close'] and  # Current open is below previous close
                curr_candle['close'] > prev_candle['open']):    # Current close is above previous open
                
                patterns['bullish_engulfing'] = {
                    'type': 'Bullish Engulfing',
                    'description': 'Potential bullish reversal pattern',
                    'strength': 'strong'
                }
        
        # Bearish Engulfing pattern
        if len(recent) >= 2:
            prev_candle = recent.iloc[-2]
            curr_candle = recent.iloc[-1]
            
            if (prev_candle['close'] > prev_candle['open'] and  # Previous candle is bullish
                curr_candle['close'] < curr_candle['open'] and  # Current candle is bearish
                curr_candle['open'] > prev_candle['close'] and  # Current open is above previous close
                curr_candle['close'] < prev_candle['open']):    # Current close is below previous open
                
                patterns['bearish_engulfing'] = {
                    'type': 'Bearish Engulfing',
                    'description': 'Potential bearish reversal pattern',
                    'strength': 'strong'
                }
        
        # Hammer pattern (bullish reversal)
        last_candle = recent.iloc[-1]
        body_size = abs(last_candle['close'] - last_candle['open'])
        lower_wick = min(last_candle['open'], last_candle['close']) - last_candle['low']
        upper_wick = last_candle['high'] - max(last_candle['open'], last_candle['close'])
        
        if (lower_wick > 2 * body_size and  # Lower wick is at least 2x the body
            upper_wick < 0.1 * body_size and  # Almost no upper wick
            last_candle['close'] > last_candle['open']):  # Bullish candle
            
            patterns['hammer'] = {
                'type': 'Hammer',
                'description': 'Potential bullish reversal after a downtrend',
                'strength': 'strong'
            }
        
        # Shooting star pattern (bearish reversal)
        if (upper_wick > 2 * body_size and  # Upper wick is at least 2x the body
            lower_wick < 0.1 * body_size and  # Almost no lower wick
            last_candle['close'] < last_candle['open']):  # Bearish candle
            
            patterns['shooting_star'] = {
                'type': 'Shooting Star',
                'description': 'Potential bearish reversal after an uptrend',
                'strength': 'strong'
            }
        
        return patterns
    
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
            return {
                'signal': 'NO_SIGNAL',
                'confidence': 0,
                'reason': 'Insufficient data'
            }
        
        signals = []
        confidence_scores = []
        reasons = []
        
        # Get the most recent data point with indicators
        latest = df.iloc[-1]
        
        # Check for trend based on moving averages
        try:
            if latest['sma20'] > latest['sma50'] and latest['sma50'] > latest['sma200']:
                signals.append('BUY')
                confidence_scores.append(0.7)
                reasons.append('Strong uptrend: SMA20 > SMA50 > SMA200')
            elif latest['sma20'] < latest['sma50'] and latest['sma50'] < latest['sma200']:
                signals.append('SELL')
                confidence_scores.append(0.7)
                reasons.append('Strong downtrend: SMA20 < SMA50 < SMA200')
        except:
            pass  # Moving averages might not be available for short timeframes
        
        # Check RSI conditions
        try:
            if latest['rsi'] < 30:
                signals.append('BUY')
                confidence_scores.append(0.6)
                reasons.append(f'Oversold: RSI = {latest["rsi"]:.2f}')
            elif latest['rsi'] > 70:
                signals.append('SELL')
                confidence_scores.append(0.6)
                reasons.append(f'Overbought: RSI = {latest["rsi"]:.2f}')
        except:
            pass
        
        # Check MACD
        try:
            # MACD line crosses above signal line (bullish)
            if (df.iloc[-2]['macd'] < df.iloc[-2]['macd_signal'] and 
                latest['macd'] > latest['macd_signal']):
                signals.append('BUY')
                confidence_scores.append(0.65)
                reasons.append('MACD crossed above signal line (bullish)')
            
            # MACD line crosses below signal line (bearish)
            elif (df.iloc[-2]['macd'] > df.iloc[-2]['macd_signal'] and 
                latest['macd'] < latest['macd_signal']):
                signals.append('SELL')
                confidence_scores.append(0.65)
                reasons.append('MACD crossed below signal line (bearish)')
        except:
            pass
        
        # Check Bollinger Bands
        try:
            if latest['close'] < latest['bb_lower']:
                signals.append('BUY')
                confidence_scores.append(0.6)
                reasons.append('Price below lower Bollinger Band (potential bounce)')
            elif latest['close'] > latest['bb_upper']:
                signals.append('SELL')
                confidence_scores.append(0.6)
                reasons.append('Price above upper Bollinger Band (potential reversal)')
        except:
            pass
        
        # Include candlestick pattern signals
        for pattern_name, pattern_info in patterns.items():
            if pattern_name in ['bullish_engulfing', 'hammer']:
                signals.append('BUY')
                confidence_scores.append(0.7 if pattern_info['strength'] == 'strong' else 0.5)
                reasons.append(f"{pattern_info['type']} pattern detected: {pattern_info['description']}")
            elif pattern_name in ['bearish_engulfing', 'shooting_star']:
                signals.append('SELL')
                confidence_scores.append(0.7 if pattern_info['strength'] == 'strong' else 0.5)
                reasons.append(f"{pattern_info['type']} pattern detected: {pattern_info['description']}")
            elif pattern_name == 'doji':
                # Doji alone doesn't give direction, look at previous trend
                try:
                    if df.iloc[-5:-1]['close'].mean() > df.iloc[-10:-5]['close'].mean():
                        # Previous trend was up, doji might signal reversal
                        signals.append('SELL')
                        confidence_scores.append(0.4)
                        reasons.append('Doji after uptrend (potential reversal)')
                    elif df.iloc[-5:-1]['close'].mean() < df.iloc[-10:-5]['close'].mean():
                        # Previous trend was down, doji might signal reversal
                        signals.append('BUY')
                        confidence_scores.append(0.4)
                        reasons.append('Doji after downtrend (potential reversal)')
                except:
                    pass
        
        # If no signals were generated, default to HOLD
        if not signals:
            return {
                'signal': 'HOLD',
                'confidence': 0.5,
                'reason': 'No clear signals detected'
            }
        
        # Count the signals to determine the final recommendation
        buy_count = signals.count('BUY')
        sell_count = signals.count('SELL')
        
        # Calculate confidence based on weighted average of confidence scores
        buy_confidence = sum([confidence_scores[i] for i in range(len(signals)) if signals[i] == 'BUY']) / max(1, buy_count)
        sell_confidence = sum([confidence_scores[i] for i in range(len(signals)) if signals[i] == 'SELL']) / max(1, sell_count)
        
        # Get buy and sell reasons separately
        buy_reasons = [reasons[i] for i in range(len(signals)) if signals[i] == 'BUY']
        sell_reasons = [reasons[i] for i in range(len(signals)) if signals[i] == 'SELL']
        
        # Determine final signal
        if buy_count > sell_count and buy_confidence > 0.5:
            return {
                'signal': 'BUY',
                'confidence': buy_confidence,
                'reason': ', '.join(buy_reasons),
                'conflicting_signals': sell_count > 0,
                'conflicting_reasons': ', '.join(sell_reasons) if sell_reasons else None
            }
        elif sell_count > buy_count and sell_confidence > 0.5:
            return {
                'signal': 'SELL',
                'confidence': sell_confidence,
                'reason': ', '.join(sell_reasons),
                'conflicting_signals': buy_count > 0,
                'conflicting_reasons': ', '.join(buy_reasons) if buy_reasons else None
            }
        else:
            return {
                'signal': 'HOLD',
                'confidence': 0.5,
                'reason': 'Mixed signals detected',
                'buy_reasons': ', '.join(buy_reasons) if buy_reasons else None,
                'sell_reasons': ', '.join(sell_reasons) if sell_reasons else None
            }
    
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
        if df is None or df.empty:
            return {}
        
        # Use the last close as entry price if not provided
        if entry_price is None:
            entry_price = df['close'].iloc[-1]
        
        # Calculate Average True Range (ATR) for stop loss placement
        try:
            df['tr1'] = abs(df['high'] - df['low'])
            df['tr2'] = abs(df['high'] - df['close'].shift(1))
            df['tr3'] = abs(df['low'] - df['close'].shift(1))
            df['true_range'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
            df['atr'] = df['true_range'].rolling(window=14).mean()
            
            # Get the most recent ATR value
            atr = df['atr'].iloc[-1]
            
            # Calculate risk-reward ratio based on volatility
            risk_factor = 2.0  # Default: 2x ATR for stop loss
            reward_ratio = 2.0  # Default: 1:2 risk-reward ratio
            
            # Adjust risk parameters based on the signal confidence and market condition
            volatility = df['close'].pct_change().std() * 100  # Percentage volatility
            
            if volatility > 2.0:  # High volatility
                risk_factor = 2.5  # More room for stop loss
                reward_ratio = 2.5  # Higher reward ratio required
            elif volatility < 0.5:  # Low volatility
                risk_factor = 1.5  # Tighter stop loss
                reward_ratio = 1.5  # Lower reward ratio acceptable
            
            if signal == 'BUY':
                stop_loss = entry_price - (atr * risk_factor)
                take_profit = entry_price + (atr * risk_factor * reward_ratio)
                risk_amount = entry_price - stop_loss
                reward_amount = take_profit - entry_price
            elif signal == 'SELL':
                stop_loss = entry_price + (atr * risk_factor)
                take_profit = entry_price - (atr * risk_factor * reward_ratio)
                risk_amount = stop_loss - entry_price
                reward_amount = entry_price - take_profit
            else:  # HOLD
                return {
                    'message': 'No risk management parameters for HOLD signal'
                }
            
            # Calculate risk percentage
            risk_percentage = (risk_amount / entry_price) * 100
            
            # Calculate position size based on risk management (1% account risk)
            account_risk_percentage = 1.0
            optimal_position_percentage = (account_risk_percentage / risk_percentage) * 100
            
            # Risk-reward ratio
            risk_reward_ratio = reward_amount / risk_amount
            
            return {
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'risk_amount': risk_amount,
                'reward_amount': reward_amount,
                'risk_percentage': risk_percentage,
                'optimal_position_percentage': optimal_position_percentage,
                'risk_reward_ratio': risk_reward_ratio,
                'atr': atr,
                'volatility': volatility
            }
            
        except Exception as e:
            logger.error(f"Error calculating risk management parameters: {str(e)}")
            return {
                'error': 'Failed to calculate risk management parameters',
                'message': str(e)
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
            logger.error("Cannot generate chart: empty dataframe")
            return None
        
        # Ensure df has expected columns
        required_cols = ['open', 'high', 'low', 'close']
        for col in required_cols:
            if col not in df.columns and col.capitalize() in df.columns:
                df[col] = df[col.capitalize()]
        
        # Create temporary file for the chart
        with NamedTemporaryFile(suffix='.png') as tmp:
            try:
                # Limit to last 30 data points for better visualization
                plot_df = df.tail(30).copy()
                
                # Set up plot style
                mc = mpf.make_marketcolors(
                    up='green', down='red',
                    wick={'up': 'green', 'down': 'red'},
                    edge={'up': 'green', 'down': 'red'},
                    volume={'up': 'green', 'down': 'red'}
                )
                s = mpf.make_mpf_style(marketcolors=mc, gridstyle='--', y_on_right=False)
                
                # Set up subplots for indicators
                if indicators and 'volume' in df.columns:
                    if 'rsi' in df.columns and 'macd' in df.columns:
                        fig, axes = mpf.plot(
                            plot_df, type='candle', style=s,
                            volume=True, title=title,
                            figsize=(12, 10),
                            panel_ratios=(6, 2, 2), 
                            main_panel=0, volume_panel=1,
                            returnfig=True
                        )
                        
                        # Add RSI to third panel
                        ax_rsi = axes[0][2]
                        ax_rsi.plot(plot_df.index, plot_df['rsi'], color='purple', linewidth=1.5)
                        ax_rsi.axhline(70, color='r', linestyle='--', alpha=0.5)
                        ax_rsi.axhline(30, color='g', linestyle='--', alpha=0.5)
                        ax_rsi.set_ylabel('RSI')
                        
                    else:
                        # Just volume panel
                        fig, axes = mpf.plot(
                            plot_df, type='candle', style=s,
                            volume=True, title=title,
                            figsize=(12, 8),
                            returnfig=True
                        )
                    
                    # Add moving averages
                    ax_main = axes[0][0]
                    if 'sma20' in plot_df.columns and not plot_df['sma20'].isna().all():
                        ax_main.plot(plot_df.index, plot_df['sma20'], color='blue', linewidth=1, label='SMA 20')
                    if 'sma50' in plot_df.columns and not plot_df['sma50'].isna().all():
                        ax_main.plot(plot_df.index, plot_df['sma50'], color='orange', linewidth=1, label='SMA 50')
                    
                    # Add Bollinger Bands
                    if all(x in plot_df.columns for x in ['bb_upper', 'bb_middle', 'bb_lower']):
                        if not plot_df['bb_upper'].isna().all():
                            ax_main.plot(plot_df.index, plot_df['bb_upper'], 'r--', linewidth=1, alpha=0.5)
                            ax_main.plot(plot_df.index, plot_df['bb_middle'], 'g--', linewidth=1, alpha=0.5)
                            ax_main.plot(plot_df.index, plot_df['bb_lower'], 'r--', linewidth=1, alpha=0.5)
                    
                    # Add legend
                    ax_main.legend()
                    
                else:
                    # Basic plot without indicators
                    fig, axes = mpf.plot(
                        plot_df, type='candle', style=s,
                        title=title, figsize=(12, 6),
                        returnfig=True
                    )
                
                # Save the figure to the temporary file
                fig.savefig(tmp.name, dpi=150, bbox_inches='tight')
                plt.close(fig)
                
                # Read the file and encode to base64
                with open(tmp.name, 'rb') as img_file:
                    img_data = base64.b64encode(img_file.read()).decode('utf-8')
                
                return img_data
                
            except Exception as e:
                logger.error(f"Error generating candlestick chart: {str(e)}", exc_info=True)
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
            logger.error("Cannot generate interactive chart: empty dataframe")
            return "<p>No data available for chart</p>"
        
        # Ensure df has expected columns
        required_cols = ['open', 'high', 'low', 'close']
        for col in required_cols:
            if col not in df.columns and col.capitalize() in df.columns:
                df[col] = df[col.capitalize()]
        
        try:
            # Limit to last 30 data points for better visualization
            plot_df = df.tail(30).copy()
            
            # Create the candlestick chart
            fig = go.Figure()
            
            # Add candlestick trace
            fig.add_trace(go.Candlestick(
                x=plot_df.index,
                open=plot_df['open'],
                high=plot_df['high'],
                low=plot_df['low'],
                close=plot_df['close'],
                name='Candlesticks'
            ))
            
            # Add volume as a bar chart at the bottom
            if 'volume' in plot_df.columns:
                fig.add_trace(go.Bar(
                    x=plot_df.index,
                    y=plot_df['volume'],
                    name='Volume',
                    marker=dict(color='rgba(0, 0, 255, 0.3)'),
                    opacity=0.3,
                    yaxis='y2'
                ))
            
            # Add moving averages
            if 'sma20' in plot_df.columns and not plot_df['sma20'].isna().all():
                fig.add_trace(go.Scatter(
                    x=plot_df.index,
                    y=plot_df['sma20'],
                    mode='lines',
                    line=dict(color='blue', width=1),
                    name='SMA 20'
                ))
            
            if 'sma50' in plot_df.columns and not plot_df['sma50'].isna().all():
                fig.add_trace(go.Scatter(
                    x=plot_df.index,
                    y=plot_df['sma50'],
                    mode='lines',
                    line=dict(color='orange', width=1),
                    name='SMA 50'
                ))
            
            # Add Bollinger Bands
            if all(x in plot_df.columns for x in ['bb_upper', 'bb_middle', 'bb_lower']):
                if not plot_df['bb_upper'].isna().all():
                    fig.add_trace(go.Scatter(
                        x=plot_df.index,
                        y=plot_df['bb_upper'],
                        mode='lines',
                        line=dict(color='red', width=1, dash='dash'),
                        name='BB Upper',
                        opacity=0.5
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=plot_df.index,
                        y=plot_df['bb_middle'],
                        mode='lines',
                        line=dict(color='green', width=1, dash='dash'),
                        name='BB Middle',
                        opacity=0.5
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=plot_df.index,
                        y=plot_df['bb_lower'],
                        mode='lines',
                        line=dict(color='red', width=1, dash='dash'),
                        name='BB Lower',
                        opacity=0.5
                    ))
            
            # Update layout
            fig.update_layout(
                title=title,
                yaxis_title='Price',
                xaxis_rangeslider_visible=False,
                height=600,
                yaxis2=dict(
                    title='Volume',
                    overlaying='y',
                    side='right',
                    showgrid=False
                )
            )
            
            # Convert to HTML
            return fig.to_html(full_html=False, include_plotlyjs='cdn')
            
        except Exception as e:
            logger.error(f"Error generating interactive chart: {str(e)}", exc_info=True)
            return f"<p>Error generating chart: {str(e)}</p>"


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
        # Get market data based on asset type
        if asset_type.lower() == 'stock':
            df = self.data_provider.get_stock_data(symbol, period, timeframe)
        elif asset_type.lower() == 'crypto':
            # Convert period to days for CoinGecko
            days = 30  # Default
            if period == '1d':
                days = 1
            elif period == '1wk':
                days = 7
            elif period == '1mo':
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
            return {
                'error': f"Unknown asset type: {asset_type}",
                'message': "Supported types are: 'stock', 'crypto', 'forex'"
            }
        
        if df is None or df.empty:
            return {
                'error': "No data available",
                'message': f"Could not retrieve data for {symbol} ({asset_type})"
            }
        
        # Add technical indicators
        df_with_indicators = TechnicalAnalyzer.add_indicators(df)
        
        # Identify candlestick patterns
        patterns = TechnicalAnalyzer.identify_candlestick_patterns(df_with_indicators)
        
        # Generate trading signals
        signals = TechnicalAnalyzer.generate_trade_signals(df_with_indicators, patterns)
        
        # Calculate risk management parameters if we have a directional signal
        risk_management = {}
        if signals['signal'] in ['BUY', 'SELL']:
            risk_management = TechnicalAnalyzer.calculate_risk_management(
                df_with_indicators, signals['signal']
            )
        
        # Generate chart image
        chart_image = ChartGenerator.generate_candlestick_chart(
            df_with_indicators, f"{symbol} ({asset_type}) - {timeframe}"
        )
        
        # Generate interactive chart HTML
        interactive_chart_html = ChartGenerator.generate_interactive_chart(
            df_with_indicators, f"{symbol} ({asset_type}) - {timeframe}"
        )
        
        # Prepare market summary
        last_price = df['close'].iloc[-1]
        day_change = ((df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]) * 100
        
        # Identify market trend
        trend = "Sideways"
        try:
            if (df_with_indicators['sma20'].iloc[-1] > df_with_indicators['sma50'].iloc[-1] and 
                df_with_indicators['sma50'].iloc[-1] > df_with_indicators['sma200'].iloc[-1]):
                trend = "Bullish (Uptrend)"
            elif (df_with_indicators['sma20'].iloc[-1] < df_with_indicators['sma50'].iloc[-1] and 
                df_with_indicators['sma50'].iloc[-1] < df_with_indicators['sma200'].iloc[-1]):
                trend = "Bearish (Downtrend)"
        except:
            # Moving averages might not be available for short timeframes
            # Use simple price comparison
            if df['close'].tail(10).mean() > df['close'].tail(20).mean():
                trend = "Short-term Bullish"
            elif df['close'].tail(10).mean() < df['close'].tail(20).mean():
                trend = "Short-term Bearish"
        
        # Calculate volatility
        volatility = df['close'].pct_change().std() * 100
        
        # Prepare comprehensive analysis result
        result = {
            'asset': {
                'type': asset_type,
                'symbol': symbol,
                'timeframe': timeframe,
                'period': period
            },
            'market_summary': {
                'last_price': last_price,
                'day_change_percent': day_change,
                'trend': trend,
                'volatility_percent': volatility
            },
            'technical_analysis': {
                'signal': signals['signal'],
                'confidence': signals['confidence'],
                'reasoning': signals['reason'],
                'patterns': patterns,
                'indicators': {
                    'rsi': df_with_indicators['rsi'].iloc[-1] if 'rsi' in df_with_indicators else None,
                    'macd': df_with_indicators['macd'].iloc[-1] if 'macd' in df_with_indicators else None,
                    'macd_signal': df_with_indicators['macd_signal'].iloc[-1] if 'macd_signal' in df_with_indicators else None,
                }
            },
            'risk_management': risk_management,
            'charts': {
                'image': chart_image,
                'interactive_html': interactive_chart_html
            },
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return result