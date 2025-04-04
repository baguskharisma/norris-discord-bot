import discord
from discord import app_commands
import logging
import os
import tempfile
import base64
from datetime import datetime
from market_data import MarketAnalyzer

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
SUPPORTED_ASSET_TYPES = ['stock', 'crypto', 'forex']
DEFAULT_TIMEFRAME = '1d'
DEFAULT_PERIOD = '1mo'

# Alpha Vantage API key (for stocks and forex)
ALPHA_VANTAGE_KEY = os.environ.get('ALPHA_VANTAGE_KEY', '')

class TradingCommands:
    """
    Discord bot commands for trading and market analysis.
    """
    
    def __init__(self, bot):
        """
        Initialize trading commands.
        
        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        self.analyzer = MarketAnalyzer()
        
    def register_commands(self):
        """Register all trading-related commands with the bot."""
        
        @self.bot.tree.command(name="analyze", description="Analyze a financial asset and provide trading recommendations")
        @app_commands.describe(
            asset_type="Type of asset (stock, crypto, forex)",
            symbol="Asset symbol (e.g., AAPL, bitcoin, EURUSD)",
            timeframe="Candle timeframe (1d, 1h, 15m, etc.)",
            period="Historical period to analyze (1d, 1wk, 1mo, 3mo, 6mo, 1y)"
        )
        @app_commands.choices(asset_type=[
            app_commands.Choice(name="Stock", value="stock"),
            app_commands.Choice(name="Cryptocurrency", value="crypto"),
            app_commands.Choice(name="Forex", value="forex")
        ])
        @app_commands.choices(timeframe=[
            app_commands.Choice(name="1 Day", value="1d"),
            app_commands.Choice(name="1 Hour", value="1h"),
            app_commands.Choice(name="15 Minutes", value="15m")
        ])
        @app_commands.choices(period=[
            app_commands.Choice(name="1 Day", value="1d"),
            app_commands.Choice(name="1 Week", value="1wk"),
            app_commands.Choice(name="1 Month", value="1mo"),
            app_commands.Choice(name="3 Months", value="3mo"),
            app_commands.Choice(name="6 Months", value="6mo"),
            app_commands.Choice(name="1 Year", value="1y")
        ])
        async def slash_analyze(
            interaction: discord.Interaction,
            asset_type: str,
            symbol: str,
            timeframe: str = DEFAULT_TIMEFRAME,
            period: str = DEFAULT_PERIOD
        ):
            """
            Command to analyze an asset and provide trading recommendations.
            """
            # Defer the response as this might take a while
            await interaction.response.defer(thinking=True)
            
            # Normalize the symbol
            symbol = symbol.strip().upper()
            
            # Special handling for cryptocurrency symbols
            if asset_type == 'crypto':
                # Convert common symbols to CoinGecko IDs
                crypto_mapping = {
                    'BTC': 'bitcoin',
                    'ETH': 'ethereum',
                    'SOL': 'solana',
                    'DOGE': 'dogecoin',
                    'XRP': 'ripple',
                    'ADA': 'cardano',
                    'DOT': 'polkadot',
                    'AVAX': 'avalanche-2',
                    'MATIC': 'matic-network',
                    'LINK': 'chainlink'
                }
                symbol = crypto_mapping.get(symbol, symbol.lower())
            
            # Special handling for forex pairs
            if asset_type == 'forex' and '/' in symbol:
                # Convert format from EUR/USD to EURUSD
                symbol = symbol.replace('/', '')
            
            # Add =X suffix for forex if using Yahoo Finance and not already there
            if asset_type == 'forex' and not symbol.endswith('=X'):
                symbol = f"{symbol}=X"
            
            try:
                # Send an initial message
                await interaction.followup.send(f"Analyzing {asset_type} {symbol} ({timeframe})... Please wait.")
                
                # Perform the analysis
                analysis = self.analyzer.analyze_asset(asset_type, symbol, timeframe, period)
                
                if 'error' in analysis:
                    # Handle error case
                    await interaction.followup.send(
                        f"⚠️ **Error analyzing {symbol}**: {analysis['error']}\n"
                        f"{analysis.get('message', 'No additional information available.')}"
                    )
                    return
                
                # Prepare the report
                report = self._format_analysis_report(analysis)
                
                # Send the text report
                await interaction.followup.send(embed=report)
                
                # Check if we have a chart image to send
                chart_image = analysis['charts']['image']
                if chart_image:
                    # Decode the base64 image and save to a temporary file
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                        tmp.write(base64.b64decode(chart_image))
                        tmp.flush()
                        
                        # Send the chart as a file attachment
                        await interaction.followup.send(
                            file=discord.File(tmp.name, filename=f"{symbol}_chart.png")
                        )
                        
                        # Clean up the temporary file
                        try:
                            os.unlink(tmp.name)
                        except:
                            pass
                
            except Exception as e:
                logger.error(f"Error in analyze command: {str(e)}", exc_info=True)
                await interaction.followup.send(f"⚠️ An error occurred while analyzing {symbol}: {str(e)}")

        @self.bot.tree.command(name="markets", description="Get a summary of major markets")
        async def slash_markets(interaction: discord.Interaction):
            """
            Command to get a summary of major markets.
            """
            await interaction.response.defer(thinking=True)
            
            try:
                # Define major assets to check
                assets = [
                    {'type': 'stock', 'symbol': 'SPY', 'name': 'S&P 500 ETF'},
                    {'type': 'stock', 'symbol': 'QQQ', 'name': 'NASDAQ 100 ETF'},
                    {'type': 'stock', 'symbol': 'DIA', 'name': 'Dow Jones ETF'},
                    {'type': 'crypto', 'symbol': 'bitcoin', 'name': 'Bitcoin'},
                    {'type': 'crypto', 'symbol': 'ethereum', 'name': 'Ethereum'},
                    {'type': 'forex', 'symbol': 'EURUSD=X', 'name': 'EUR/USD'},
                    {'type': 'forex', 'symbol': 'USDJPY=X', 'name': 'USD/JPY'}
                ]
                
                # Send an initial message
                await interaction.followup.send("Fetching market data... This might take a moment.")
                
                # Create an embed for the market summary
                embed = discord.Embed(
                    title="🌐 Global Market Summary",
                    description=f"Market snapshot as of {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    color=discord.Color.blue()
                )
                
                # Process each asset and add to the summary
                for asset in assets:
                    try:
                        # Get analysis but only need basic price data
                        analysis = self.analyzer.analyze_asset(
                            asset['type'], asset['symbol'], '1d', '1d'
                        )
                        
                        if 'error' in analysis:
                            embed.add_field(
                                name=f"{asset['name']}",
                                value=f"⚠️ Error: {analysis['error']}",
                                inline=False
                            )
                            continue
                        
                        # Extract relevant data
                        last_price = analysis['market_summary']['last_price']
                        day_change = analysis['market_summary']['day_change_percent']
                        signal = analysis['technical_analysis']['signal']
                        
                        # Format the change with color indicators
                        change_str = f"{day_change:.2f}%"
                        if day_change > 0:
                            change_str = f"▲ +{change_str}"
                        elif day_change < 0:
                            change_str = f"▼ {change_str}"
                        else:
                            change_str = f"► {change_str}"
                        
                        # Add to embed
                        embed.add_field(
                            name=f"{asset['name']}",
                            value=f"Price: {last_price:.4f}\nChange: {change_str}\nSignal: {signal}",
                            inline=True
                        )
                    
                    except Exception as e:
                        logger.error(f"Error processing {asset['symbol']}: {str(e)}")
                        embed.add_field(
                            name=f"{asset['name']}",
                            value=f"⚠️ Error: {str(e)}",
                            inline=True
                        )
                
                # Add a footer with disclaimer
                embed.set_footer(text="Data is from free APIs and may be delayed. Not financial advice.")
                
                # Send the market summary
                await interaction.followup.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Error in markets command: {str(e)}", exc_info=True)
                await interaction.followup.send(f"⚠️ An error occurred while fetching market data: {str(e)}")

        @self.bot.tree.command(name="trading_help", description="Get help with trading commands")
        async def slash_trading_help(interaction: discord.Interaction):
            """
            Command to display help information for trading commands.
            """
            help_embed = discord.Embed(
                title="📈 Trading Assistant Commands",
                description="Analyze markets and get trading recommendations",
                color=discord.Color.blue()
            )
            
            help_embed.add_field(
                name="/analyze",
                value=(
                    "Analyze a financial asset and provide trading recommendations\n"
                    "**Usage**: `/analyze asset_type:stock symbol:AAPL timeframe:1d period:1mo`\n"
                    "- `asset_type`: stock, crypto, or forex\n"
                    "- `symbol`: Asset symbol (e.g., AAPL, bitcoin, EURUSD)\n"
                    "- `timeframe`: Candle timeframe (1d, 1h, 15m)\n"
                    "- `period`: Historical period (1d, 1wk, 1mo, 3mo, 6mo, 1y)"
                ),
                inline=False
            )
            
            help_embed.add_field(
                name="/markets",
                value=(
                    "Get a summary of major global markets\n"
                    "**Usage**: `/markets`\n"
                    "Shows current prices, daily changes, and trading signals for major indices, "
                    "cryptocurrencies, and forex pairs."
                ),
                inline=False
            )
            
            help_embed.add_field(
                name="🔍 Examples",
                value=(
                    "- `/analyze asset_type:stock symbol:TSLA`\n"
                    "- `/analyze asset_type:crypto symbol:bitcoin period:3mo`\n"
                    "- `/analyze asset_type:forex symbol:EURUSD timeframe:1h period:1wk`"
                ),
                inline=False
            )
            
            help_embed.add_field(
                name="📊 Technical Indicators",
                value=(
                    "Analysis includes these technical indicators:\n"
                    "- Moving Averages (SMA 20, 50, 200)\n"
                    "- RSI (Relative Strength Index)\n"
                    "- MACD (Moving Average Convergence Divergence)\n"
                    "- Bollinger Bands\n"
                    "- Candlestick Patterns (Doji, Engulfing, etc.)"
                ),
                inline=False
            )
            
            help_embed.set_footer(text="Data provided by free APIs. Not financial advice - always do your own research.")
            
            await interaction.response.send_message(embed=help_embed)
        
        logger.info("Trading commands registered")
    
    def _format_analysis_report(self, analysis):
        """
        Format the analysis results as a Discord embed.
        
        Args:
            analysis (dict): Analysis results
            
        Returns:
            discord.Embed: Formatted embed for Discord
        """
        # Get the signal color
        signal = analysis['technical_analysis']['signal']
        if signal == 'BUY':
            color = discord.Color.green()
        elif signal == 'SELL':
            color = discord.Color.red()
        else:  # HOLD
            color = discord.Color.gold()
        
        # Create the main embed
        embed = discord.Embed(
            title=f"📊 Analysis: {analysis['asset']['symbol']} ({analysis['asset']['type']})",
            description=f"**Signal: {signal}** ({analysis['technical_analysis']['confidence']*100:.1f}% confidence)",
            color=color
        )
        
        # Market summary section
        price = analysis['market_summary']['last_price']
        change = analysis['market_summary']['day_change_percent']
        trend = analysis['market_summary']['trend']
        volatility = analysis['market_summary']['volatility_percent']
        
        change_str = f"{change:.2f}%"
        if change > 0:
            change_str = f"+{change_str} ▲"
        elif change < 0:
            change_str = f"{change_str} ▼"
        
        embed.add_field(
            name="📈 Market Summary",
            value=(
                f"**Price**: {price:.6f}\n"
                f"**Change**: {change_str}\n"
                f"**Trend**: {trend}\n"
                f"**Volatility**: {volatility:.2f}%"
            ),
            inline=False
        )
        
        # Technical analysis section
        reasoning = analysis['technical_analysis']['reasoning']
        
        # Add indicators data
        indicators = []
        if analysis['technical_analysis']['indicators']['rsi'] is not None:
            rsi = analysis['technical_analysis']['indicators']['rsi']
            rsi_status = "Oversold" if rsi < 30 else "Overbought" if rsi > 70 else "Neutral"
            indicators.append(f"**RSI**: {rsi:.2f} ({rsi_status})")
        
        if (analysis['technical_analysis']['indicators']['macd'] is not None and 
            analysis['technical_analysis']['indicators']['macd_signal'] is not None):
            macd = analysis['technical_analysis']['indicators']['macd']
            macd_signal = analysis['technical_analysis']['indicators']['macd_signal']
            macd_status = "Bullish" if macd > macd_signal else "Bearish"
            indicators.append(f"**MACD**: {macd:.6f} ({macd_status})")
        
        # Add patterns
        patterns = []
        for pattern, info in analysis['technical_analysis']['patterns'].items():
            patterns.append(f"**{info['type']}**: {info['description']}")
        
        # Combine all technical info
        tech_value = f"**Reasoning**: {reasoning}\n\n"
        
        if indicators:
            tech_value += "**Indicators**:\n" + "\n".join(indicators) + "\n\n"
        
        if patterns:
            tech_value += "**Patterns**:\n" + "\n".join(patterns)
        
        embed.add_field(
            name="🔬 Technical Analysis",
            value=tech_value,
            inline=False
        )
        
        # Risk management section
        if analysis['risk_management'] and 'error' not in analysis['risk_management']:
            rm = analysis['risk_management']
            embed.add_field(
                name="⚠️ Risk Management",
                value=(
                    f"**Entry**: {rm['entry_price']:.6f}\n"
                    f"**Stop Loss**: {rm['stop_loss']:.6f} ({rm['risk_percentage']:.2f}%)\n"
                    f"**Take Profit**: {rm['take_profit']:.6f}\n"
                    f"**Risk/Reward**: {rm['risk_reward_ratio']:.2f}\n"
                    f"**Position Size**: {rm['optimal_position_percentage']:.2f}% of capital"
                ),
                inline=False
            )
        
        # Add timestamp and disclaimer
        embed.set_footer(text=(
            f"Analysis time: {analysis['timestamp']} | "
            "Not financial advice. Always do your own research."
        ))
        
        return embed