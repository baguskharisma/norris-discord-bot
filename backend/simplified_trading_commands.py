import io
import discord
from discord import app_commands
import logging
from simplified_market_data import MarketAnalyzer

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
DEFAULT_TIMEFRAME = "1d"  # Daily candles
DEFAULT_PERIOD = "1mo"    # One month of data

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
        logger.info("Trading commands initialized")
        
    def register_commands(self):
        """Register all trading-related commands with the bot."""
        
        @self.bot.tree.command(name="analyze", description="Analyze a financial asset and get trading recommendations")
        @app_commands.describe(
            asset_type="Type of asset to analyze (stock, crypto, forex)",
            symbol="Asset symbol (e.g., AAPL, bitcoin, EURUSD=X)",
            timeframe="Candle timeframe (e.g., 1d, 1h, 15m) - default: 1d",
            period="Historical period to analyze (e.g., 1mo, 3mo, 6mo, 1y) - default: 1mo"
        )
        @app_commands.choices(asset_type=[
            app_commands.Choice(name="Stock", value="stock"),
            app_commands.Choice(name="Cryptocurrency", value="crypto"),
            app_commands.Choice(name="Forex", value="forex")
        ])
        @app_commands.choices(timeframe=[
            app_commands.Choice(name="Daily (1d)", value="1d"),
            app_commands.Choice(name="Hourly (1h)", value="1h"),
            app_commands.Choice(name="15 Minutes (15m)", value="15m")
        ])
        @app_commands.choices(period=[
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
            await interaction.response.defer(thinking=True)
            
            try:
                # Clean up the symbol
                symbol = symbol.strip().upper() if asset_type.lower() != 'crypto' else symbol.strip().lower()
                
                # Send initial message
                await interaction.followup.send(f"Analyzing {asset_type} {symbol} on {timeframe} timeframe... This might take a moment.")
                
                # Perform analysis
                analysis = self.analyzer.analyze_asset(asset_type, symbol, timeframe, period)
                
                if "error" in analysis:
                    await interaction.followup.send(f"Error analyzing {asset_type} {symbol}: {analysis['error']}")
                    return
                
                # Format and send the analysis
                embed = self._format_analysis_report(analysis)
                
                # Send the formatted report
                await interaction.followup.send(embed=embed)
                
                # If we have a chart image, send it
                if 'image' in analysis and analysis['image']:
                    # Create a file from the base64 encoded image
                    import base64
                    import io
                    
                    image_data = base64.b64decode(analysis['image'])
                    file = discord.File(io.BytesIO(image_data), filename="analysis_chart.png")
                    
                    # Send the chart
                    await interaction.followup.send(f"**Technical Analysis Chart for {symbol}**", file=file)
                
                # Send interactive chart HTML as a text file if available
                if 'interactive_chart' in analysis and analysis['interactive_chart']:
                    # Create a file from the HTML
                    html_content = analysis['interactive_chart']
                    file = discord.File(io.BytesIO(html_content.encode()), filename=f"{symbol}_interactive_chart.html")
                    
                    # Send the HTML file
                    await interaction.followup.send(
                        "I've prepared an interactive chart for you. You can download and open this HTML file in any browser.",
                        file=file
                    )
                
            except Exception as e:
                logger.error(f"Error in /analyze command: {str(e)}", exc_info=True)
                await interaction.followup.send(f"An error occurred while analyzing {asset_type} {symbol}: {str(e)}")
        
        @self.bot.tree.command(name="markets", description="Get a summary of major markets")
        async def slash_markets(interaction: discord.Interaction):
            """
            Command to get a summary of major markets.
            """
            await interaction.response.defer(thinking=True)
            
            try:
                # Send initial message
                await interaction.followup.send("Gathering market data... This might take a moment.")
                
                # Get market overview
                overview = self.analyzer.get_market_overview()
                
                if "error" in overview:
                    await interaction.followup.send(f"Error fetching market overview: {overview['error']}")
                    return
                
                # Format and send the market overview
                timestamp = overview.get('timestamp', 'N/A')
                
                # Create embeds for each market category
                stock_embed = discord.Embed(
                    title="Stock Market Overview",
                    description=f"Major indices as of {timestamp}",
                    color=discord.Color.blue()
                )
                
                crypto_embed = discord.Embed(
                    title="Cryptocurrency Market Overview",
                    description=f"Major cryptocurrencies as of {timestamp}",
                    color=discord.Color.gold()
                )
                
                forex_embed = discord.Embed(
                    title="Forex Market Overview",
                    description=f"Major currency pairs as of {timestamp}",
                    color=discord.Color.green()
                )
                
                # Add stock data
                for stock in overview.get('stocks', []):
                    name = stock.get('name', 'Unknown')
                    symbol = stock.get('symbol', 'Unknown')
                    price = stock.get('last_price', 0)
                    change = stock.get('day_change_percent', 0)
                    signal = stock.get('signal', 'HOLD')
                    
                    # Determine emoji based on change
                    emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
                    signal_emoji = "🟢" if signal == "BUY" else "🔴" if signal == "SELL" else "⚪"
                    
                    stock_embed.add_field(
                        name=f"{emoji} {name} ({symbol})",
                        value=f"Price: ${price:,.2f}\nChange: {change:+.2f}%\nSignal: {signal_emoji} {signal}",
                        inline=True
                    )
                
                # Add crypto data
                for crypto in overview.get('crypto', []):
                    name = crypto.get('name', 'Unknown')
                    symbol = crypto.get('symbol', 'Unknown')
                    price = crypto.get('last_price', 0)
                    change = crypto.get('day_change_percent', 0)
                    signal = crypto.get('signal', 'HOLD')
                    
                    # Determine emoji based on change
                    emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
                    signal_emoji = "🟢" if signal == "BUY" else "🔴" if signal == "SELL" else "⚪"
                    
                    crypto_embed.add_field(
                        name=f"{emoji} {name} ({symbol})",
                        value=f"Price: ${price:,.2f}\nChange: {change:+.2f}%\nSignal: {signal_emoji} {signal}",
                        inline=True
                    )
                
                # Add forex data
                for pair in overview.get('forex', []):
                    name = pair.get('name', 'Unknown')
                    symbol = pair.get('symbol', 'Unknown').replace('=X', '')
                    price = pair.get('last_price', 0)
                    change = pair.get('day_change_percent', 0)
                    signal = pair.get('signal', 'HOLD')
                    
                    # Determine emoji based on change
                    emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
                    signal_emoji = "🟢" if signal == "BUY" else "🔴" if signal == "SELL" else "⚪"
                    
                    forex_embed.add_field(
                        name=f"{emoji} {name} ({symbol})",
                        value=f"Price: {price:,.4f}\nChange: {change:+.2f}%\nSignal: {signal_emoji} {signal}",
                        inline=True
                    )
                
                # Add footer with disclaimer
                footer_text = "Data is for informational purposes only. Not financial advice."
                stock_embed.set_footer(text=footer_text)
                crypto_embed.set_footer(text=footer_text)
                forex_embed.set_footer(text=footer_text)
                
                # Send the embeds
                await interaction.followup.send(embed=stock_embed)
                await interaction.followup.send(embed=crypto_embed)
                await interaction.followup.send(embed=forex_embed)
                
            except Exception as e:
                logger.error(f"Error in /markets command: {str(e)}", exc_info=True)
                await interaction.followup.send(f"An error occurred while fetching market overview: {str(e)}")
        
        @self.bot.tree.command(name="trading_help", description="Display help information for trading commands")
        async def slash_trading_help(interaction: discord.Interaction):
            """
            Command to display help information for trading commands.
            """
            help_text = """
**Financial Trading Assistant Commands**

The trading assistant offers sophisticated market analysis across multiple asset classes:

**Commands:**
`/analyze <asset_type> <symbol> [timeframe] [period]` - Analyze a financial asset and get trading recommendations
`/markets` - Get a summary of major markets performance
`/trading_help` - Display this help information

**Asset Types:**
- **Stock**: Public company shares (e.g., AAPL, MSFT, TSLA)
- **Cryptocurrency**: Digital currencies (e.g., bitcoin, ethereum, solana)
- **Forex**: Currency pairs (e.g., EURUSD=X, GBPUSD=X)

**Timeframes:**
- **1d**: Daily candles (default)
- **1h**: Hourly candles
- **15m**: 15-minute candles

**Periods:**
- **1mo**: 1 month of historical data (default)
- **3mo**: 3 months of historical data
- **6mo**: 6 months of historical data
- **1y**: 1 year of historical data

**Examples:**
`/analyze stock AAPL 1d 1mo` - Analyze Apple stock with daily candles for one month
`/analyze crypto bitcoin 1h 3mo` - Analyze Bitcoin with hourly candles for three months
`/analyze forex EURUSD=X 1d 6mo` - Analyze EUR/USD pair with daily candles for six months
`/markets` - Get summary of major indices, cryptocurrencies, and forex pairs

**Features:**
- Technical indicators (RSI, MACD, moving averages, Bollinger Bands)
- Candlestick pattern recognition
- Trading signals with confidence score
- Risk management (stop-loss and take-profit levels)
- Visual charts for technical analysis

**Disclaimer**: Trading signals and analysis are for informational purposes only and should not be considered financial advice.
            """
            await interaction.response.send_message(help_text)
    
    def _format_analysis_report(self, analysis):
        """
        Format the analysis results as a Discord embed.
        
        Args:
            analysis (dict): Analysis results
            
        Returns:
            discord.Embed: Formatted embed for Discord
        """
        try:
            # Create the embed with a title and color based on the signal
            signal = analysis.get('signal', 'HOLD')
            color = discord.Color.green() if signal == 'BUY' else discord.Color.red() if signal == 'SELL' else discord.Color.light_gray()
            
            embed = discord.Embed(
                title=f"Analysis for {analysis.get('symbol', 'Unknown')} ({analysis.get('asset_type', 'asset').capitalize()})",
                description=f"Analysis on {analysis.get('timeframe', '1d')} timeframe",
                color=color
            )
            
            # Add price information
            last_price = analysis.get('last_price', 0)
            day_change = analysis.get('day_change', 0)
            day_change_percent = analysis.get('day_change_percent', 0)
            
            # Format price based on asset type (stock/crypto vs forex)
            price_format = f"${last_price:,.2f}" if analysis.get('asset_type') != 'forex' else f"{last_price:,.4f}"
            day_change_format = f"${day_change:+,.2f}" if analysis.get('asset_type') != 'forex' else f"{day_change:+,.4f}"
            
            # Determine emoji based on price change
            emoji = "🟢" if day_change > 0 else "🔴" if day_change < 0 else "⚪"
            
            embed.add_field(
                name="Price Information",
                value=f"Current Price: {price_format}\nDay Change: {emoji} {day_change_format} ({day_change_percent:+.2f}%)",
                inline=False
            )
            
            # Add trading signal
            confidence = analysis.get('confidence', 0)
            signal_emoji = "🟢" if signal == "BUY" else "🔴" if signal == "SELL" else "⚪"
            
            embed.add_field(
                name="Trading Signal",
                value=f"{signal_emoji} **{signal}** with {confidence:.1f}% confidence",
                inline=False
            )
            
            # Add signal reasons
            reasons = analysis.get('reasons', [])
            if reasons:
                reasons_text = "\n".join([f"• {reason}" for reason in reasons])
                embed.add_field(
                    name="Analysis Reasons",
                    value=reasons_text,
                    inline=False
                )
            
            # Add risk management data if available
            risk_mgmt = analysis.get('risk_management', {})
            if risk_mgmt and risk_mgmt.get('entry_price') is not None:
                # Format values based on asset type
                entry_format = f"${risk_mgmt.get('entry_price'):,.2f}" if analysis.get('asset_type') != 'forex' else f"{risk_mgmt.get('entry_price'):,.4f}"
                sl_format = f"${risk_mgmt.get('stop_loss'):,.2f}" if risk_mgmt.get('stop_loss') and analysis.get('asset_type') != 'forex' else f"{risk_mgmt.get('stop_loss'):,.4f}" if risk_mgmt.get('stop_loss') else "N/A"
                tp_format = f"${risk_mgmt.get('take_profit'):,.2f}" if risk_mgmt.get('take_profit') and analysis.get('asset_type') != 'forex' else f"{risk_mgmt.get('take_profit'):,.4f}" if risk_mgmt.get('take_profit') else "N/A"
                
                risk_reward = risk_mgmt.get('risk_reward_ratio', 'N/A')
                risk_reward_text = f"{risk_reward}:1" if risk_reward != 'N/A' else "N/A"
                
                embed.add_field(
                    name="Risk Management",
                    value=f"Entry Price: {entry_format}\nStop Loss: {sl_format}\nTake Profit: {tp_format}\nRisk-Reward Ratio: {risk_reward_text}",
                    inline=False
                )
            
            # Add candlestick patterns if any were detected
            patterns = analysis.get('patterns', {})
            detected_patterns = [k for k, v in patterns.items() if v]
            
            if detected_patterns:
                pattern_names = []
                for pattern in detected_patterns:
                    # Convert snake_case to Title Case
                    name = ' '.join(word.capitalize() for word in pattern.split('_'))
                    pattern_names.append(name)
                
                embed.add_field(
                    name="Detected Patterns",
                    value=', '.join(pattern_names),
                    inline=False
                )
            
            # Add footer with timestamp and disclaimer
            timestamp = analysis.get('timestamp', 'Unknown')
            embed.set_footer(text=f"Analysis time: {timestamp} | For informational purposes only. Not financial advice.")
            
            return embed
            
        except Exception as e:
            logger.error(f"Error formatting analysis report: {str(e)}")
            # Create a simple embed with the error
            error_embed = discord.Embed(
                title="Error Formatting Analysis",
                description=f"An error occurred while formatting the analysis: {str(e)}",
                color=discord.Color.red()
            )
            return error_embed