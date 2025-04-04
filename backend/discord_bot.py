import os
import logging
import datetime
import asyncio
import discord
import requests
from discord import app_commands
from discord.ext import commands
from document_parser import parse_document
from groq_client import summarize_text, answer_question, store_document, get_document
from trading_commands import TradingCommands

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Constants
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MAX_CHUNK_SIZE = 1900  # Discord message size limit is 2000 characters
FLASK_STATUS_URL = "http://localhost:8080/bot-status/update"  # URL to update bot status
BOT_START_TIME = datetime.datetime.now()

# Function to update bot status on Flask app
def update_bot_status(status="Online", details=None):
    """Update the bot status on the Flask app."""
    try:
        uptime = (datetime.datetime.now() - BOT_START_TIME).total_seconds()
        payload = {
            "status": status,
            "uptime": uptime,
        }
        
        if details:
            payload["details"] = details
            
        response = requests.post(FLASK_STATUS_URL, json=payload)
        if response.status_code == 200:
            logger.info("Bot status updated successfully")
        else:
            logger.warning(f"Failed to update bot status: {response.status_code}")
    except Exception as e:
        logger.error(f"Error updating bot status: {e}")


@bot.event
async def on_ready():
    """Event triggered when the bot is ready and connected to Discord."""
    logger.info(f'Bot connected as {bot.user.name} (ID: {bot.user.id})')
    logger.info('------')
    
    # Initialize trading commands
    try:
        trading_cmds = TradingCommands(bot)
        trading_cmds.register_commands()
        logger.info("Trading commands registered successfully")
    except Exception as e:
        logger.error(f"Failed to register trading commands: {e}")
    
    # Sync slash commands with Discord
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash commands")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")
    
    # Update bot status when ready
    update_bot_status("Online", f"Connected as {bot.user.name}")


@bot.event
async def on_message(message):
    """Event triggered when a message is sent in a channel."""
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return
    
    # Process commands first (for Discord's internal command handling)
    await bot.process_commands(message)
    
    # Check if there's an attachment
    if message.attachments:
        attachment = message.attachments[0]
        file_extension = attachment.filename.split('.')[-1].lower()
        
        # Check if file type is supported
        if file_extension not in ['pdf', 'docx', 'txt']:
            await message.channel.send(f"Unsupported file type: .{file_extension}. Please upload a PDF, DOCX, or TXT file.")
            return
            
        # Inform user processing has started
        await message.channel.send(f"I see you've uploaded {attachment.filename}. I'll process this document for you.")
        
        # Update bot status
        update_bot_status("Working", f"Processing document: {attachment.filename}")
        
        # Initialize file_path variable
        file_path = None
        
        try:
            # Download the file
            file_path = f"temp_{attachment.filename}"
            await attachment.save(file_path)
            
            # Parse the document
            await message.channel.send("Extracting text from document...")
            document_text = parse_document(file_path, file_extension)
            
            if not document_text or document_text.isspace():
                await message.channel.send("Could not extract any text from the document.")
                update_bot_status("Online", f"Failed to extract text from {attachment.filename}")
                return
            
            # Get document summary
            await message.channel.send("Generating summary using Groq API...")
            summary = await summarize_text(document_text)
            
            if not summary:
                await message.channel.send("Failed to generate a summary. Please try again later.")
                update_bot_status("Online", f"Failed to summarize {attachment.filename}")
                return
            
            # Store the document for future questions
            store_document(str(message.channel.id), document_text, attachment.filename)
            
            # Send the summary back to the channel
            await message.channel.send("**Document Summary:**")
            
            # Split summary into chunks to avoid Discord message size limits
            for i in range(0, len(summary), MAX_CHUNK_SIZE):
                chunk = summary[i:i + MAX_CHUNK_SIZE]
                await message.channel.send(chunk)
                
            # Complete
            await message.channel.send("Summary complete! ✅ You can now ask questions about this document using the `/ask` command.")
            update_bot_status("Online", f"Completed summarizing {attachment.filename}")
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}", exc_info=True)
            await message.channel.send(f"An error occurred while processing the document: {str(e)}")
            update_bot_status("Error", f"Error processing document: {str(e)[:50]}...")
        
        finally:
            # Clean up the temporary file
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Temporary file {file_path} removed")
            except Exception as e:
                logger.error(f"Error removing temporary file: {str(e)}")


# Slash Commands Implementation
@bot.tree.command(name="summarize", description="Upload and summarize a document")
@app_commands.describe(file="PDF, DOCX, or TXT file to summarize")
async def slash_summarize(interaction: discord.Interaction, file: discord.Attachment = None):
    """Slash command to upload and summarize a document."""
    await interaction.response.defer(thinking=True)
    
    # If no file is provided, give instructions
    if not file:
        instructions = """
**How to Summarize Documents with this Bot**

Please attach a document when using the `/summarize` command:

1. **Type `/summarize`**
2. **Click on "file" option**
3. **Upload your document** (PDF, DOCX, or TXT)
4. **Wait for processing**

The bot will:
- Extract text from your document
- Generate a summary using Groq's LLM API
- Store the document for future questions

After summarization, you can use `/ask` with your questions.

**Need more help?** Use the `/help` command for additional information.
"""
        await interaction.followup.send(instructions)
        update_bot_status("Online", "Provided summarization instructions")
        return
        
    # Check file extension
    file_extension = file.filename.split('.')[-1].lower()
    
    # Check if file type is supported
    if file_extension not in ['pdf', 'docx', 'txt']:
        await interaction.followup.send(f"Unsupported file type: .{file_extension}. Please upload a PDF, DOCX, or TXT file.")
        return
    
    # Update bot status
    update_bot_status("Working", f"Processing document: {file.filename}")
    
    # Initialize file_path variable
    file_path = None
    
    try:
        # Download the file
        file_path = f"temp_{file.filename}"
        await file.save(file_path)
        
        # Parse the document
        await interaction.followup.send("Extracting text from document...")
        document_text = parse_document(file_path, file_extension)
        
        if not document_text or document_text.isspace():
            await interaction.followup.send("Could not extract any text from the document.")
            update_bot_status("Online", f"Failed to extract text from {file.filename}")
            return
        
        # Get document summary
        await interaction.followup.send("Generating summary using Groq API...")
        summary = await summarize_text(document_text)
        
        if not summary:
            await interaction.followup.send("Failed to generate a summary. Please try again later.")
            update_bot_status("Online", f"Failed to summarize {file.filename}")
            return
            
        # Check if the response starts with "Error:" (indicating API failure)
        if summary.startswith("Error:"):
            await interaction.followup.send(f"Failed to generate a summary: {summary}")
            update_bot_status("Online", f"Failed to summarize {file.filename}")
            return
        
        # Store the document for future questions (both for channel and user)
        store_document(
            str(interaction.channel_id), 
            document_text, 
            file.filename,
            str(interaction.user.id)
        )
        
        # Send the summary back to the channel
        await interaction.followup.send("**Document Summary:**")
        
        # Split summary into chunks to avoid Discord message size limits
        for i in range(0, len(summary), MAX_CHUNK_SIZE):
            chunk = summary[i:i + MAX_CHUNK_SIZE]
            await interaction.followup.send(chunk)
            
        # Complete
        await interaction.followup.send("Summary complete! ✅ You can now ask questions about this document using the `/ask` command.")
        update_bot_status("Online", f"Completed summarizing {file.filename}")
        
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}", exc_info=True)
        await interaction.followup.send(f"An error occurred while processing the document: {str(e)}")
        update_bot_status("Error", f"Error processing document: {str(e)[:50]}...")
    
    finally:
        # Clean up the temporary file
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Temporary file {file_path} removed")
        except Exception as e:
            logger.error(f"Error removing temporary file: {str(e)}")


@bot.tree.command(name="ask", description="Ask a question about a document")
@app_commands.describe(
    question="Your question about the document",
    file="Optional: Upload a new document with your question (PDF, DOCX, or TXT)"
)
async def slash_ask(interaction: discord.Interaction, question: str, file: discord.Attachment = None):
    """Slash command to ask questions about documents or upload and ask."""
    await interaction.response.defer(thinking=True)
    
    # Check if a question was provided
    if not question:
        await interaction.followup.send("Please include your question. For example: `/ask What is the main topic of this document?`")
        return
    
    # If a file is uploaded, process it first
    if file:
        # Check file extension
        file_extension = file.filename.split('.')[-1].lower()
        
        # Check if file type is supported
        if file_extension not in ['pdf', 'docx', 'txt']:
            await interaction.followup.send(f"Unsupported file type: .{file_extension}. Please upload a PDF, DOCX, or TXT file.")
            return
        
        # Update bot status
        update_bot_status("Working", f"Processing document: {file.filename}")
        
        # Initialize file_path variable
        file_path = None
        
        try:
            # Download the file
            file_path = f"temp_{file.filename}"
            await file.save(file_path)
            
            # Parse the document
            await interaction.followup.send("Extracting text from document...")
            document_text = parse_document(file_path, file_extension)
            
            if not document_text or document_text.isspace():
                await interaction.followup.send("Could not extract any text from the document.")
                update_bot_status("Online", f"Failed to extract text from {file.filename}")
                return
            
            # Store the document for future questions (both for channel and user)
            store_document(
                str(interaction.channel_id), 
                document_text, 
                file.filename, 
                str(interaction.user.id)
            )
            
            # Let the user know we're using the new document
            await interaction.followup.send(f"✅ Document '{file.filename}' processed successfully! Now answering your question...")
            
            # Now answer the question using the newly uploaded document
            filename = file.filename
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}", exc_info=True)
            await interaction.followup.send(f"An error occurred while processing the document: {str(e)}")
            update_bot_status("Error", f"Error processing document: {str(e)[:50]}...")
            return
            
        finally:
            # Clean up the temporary file
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Temporary file {file_path} removed")
            except Exception as e:
                logger.error(f"Error removing temporary file: {str(e)}")
    
    else:
        # No file provided, use the cached document
        # Get the channel ID
        channel_id = str(interaction.channel.id)
        
        # Check if the user has a document in cache
        user_id = str(interaction.user.id)
        document_data = get_document(channel_id, user_id)
        
        if not document_data:
            # If no user document, check if there's a channel document
            document_data = get_document(channel_id)
            
            if not document_data:
                await interaction.followup.send("No document has been processed in this channel yet. Please upload a document with your question using the file parameter.")
                return
            else:
                await interaction.followup.send("Using the channel's most recent document. To use your own document, upload one with your question.")
        else:
            await interaction.followup.send(f"Using your document: {document_data['filename']}")
        
        # Get document text and filename from the cached document
        document_text = document_data["text"]
        filename = document_data["filename"]
    
    # Update bot status
    update_bot_status("Working", f"Answering question about {filename}")
    
    try:
        # Generate answer using Groq API
        await interaction.followup.send(f"Generating answer about {filename}... This might take a moment.")
        answer = await answer_question(document_text, question)
        
        if not answer:
            await interaction.followup.send("Failed to generate an answer. Please try again later.")
            update_bot_status("Online", f"Failed to answer question about {filename}")
            return
            
        # Check if the response starts with "Error:" (indicating API failure)
        if answer.startswith("Error:"):
            await interaction.followup.send(f"Failed to generate an answer: {answer}")
            update_bot_status("Online", f"Failed to answer question about {filename}")
            return
        
        # Send the answer back to the channel
        await interaction.followup.send(f"**Question:** {question}\n\n**Answer:**")
        
        # Split answer into chunks if necessary
        for i in range(0, len(answer), MAX_CHUNK_SIZE):
            chunk = answer[i:i + MAX_CHUNK_SIZE]
            await interaction.followup.send(chunk)
        
        # Complete
        update_bot_status("Online", f"Answered question about {filename}")
    
    except Exception as e:
        logger.error(f"Error answering question: {str(e)}", exc_info=True)
        await interaction.followup.send(f"An error occurred while answering the question: {str(e)}")
        update_bot_status("Error", f"Error answering question: {str(e)[:50]}...")


@bot.tree.command(name="help", description="Display help information for the bot")
async def slash_help(interaction: discord.Interaction):
    """Slash command to display help information."""
    help_text = """
**Discord Assistant Bot**

**Document Processing Commands:**
`/help` - Display this help message.
`/summarize [file]` - Upload and summarize a document.
`/ask <question> [file]` - Ask a question about a document. Optionally upload a new document.

**Trading Assistant Commands:**
`/analyze <asset_type> <symbol> [timeframe] [period]` - Analyze a financial asset and get trading recommendations.
`/markets` - Get a summary of major financial markets.
`/trading_help` - Display detailed help for trading commands.

**Supported Document Types:**
- PDF (.pdf)
- Word Documents (.docx)
- Text Files (.txt)

**How to Use Document Features:**

**Option 1: Summarize a Document**
1. Type `/summarize`
2. Click the "file" option and upload your document
3. The bot will process the document and provide a summary

**Option 2: Ask About a Document**
1. Type `/ask`
2. Enter your question in the "question" field
3. Optionally attach a document in the "file" field
4. If no document is attached, the bot will use the most recently processed document in the channel

**How to Use Trading Features:**

**Option 1: Analyze an Asset**
1. Type `/analyze`
2. Select asset type (stock, crypto, forex)
3. Enter symbol (e.g., AAPL, bitcoin, EURUSD=X)
4. Optionally specify timeframe and period
5. Receive comprehensive analysis with charts and recommendations

**Note:**
- Documents are stored per user as well as per channel for 24 hours.
- The bot will prioritize your personal documents when answering questions.
- If you don't have a personal document, the bot will use the channel's most recent document.
- If you encounter any errors, they will include detailed information to help troubleshoot issues with the Groq API.

Powered by Groq's LLM API for advanced document understanding.
    """
    await interaction.response.send_message(help_text)
    update_bot_status("Online", "Displayed help message")


def run_bot():
    """Run the Discord bot."""
    try:
        if not DISCORD_TOKEN:
            logger.error("DISCORD_TOKEN environment variable not set")
            raise ValueError("DISCORD_TOKEN environment variable not set")
        
        # Update initial status
        update_bot_status("Starting", "Bot is initializing...")
        
        # Run the bot
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        update_bot_status("Offline", f"Failed to start: {str(e)[:50]}...")


if __name__ == "__main__":
    run_bot()