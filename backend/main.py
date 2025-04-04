# main flask app entry point for Gunicorn
import os
import logging
import threading
import time
from app import app

# set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# define function to run the Discord bot in a seperate thread
def run_discord_bot_in_thread():
    """run the Discord bot in a seperate thread to avoid blocking the Flask app."""
    time.sleep(2) # allow Flask to start up
    try:
        import subprocess
        subprocess.Popen(["python", "discord_bot.py"])
        logger.info("Started Discord bot in a seperate process")
    except Exception as e:
        logger.error(f"Failed to start Discord bot: {e}")
        
# start the Discord bot thread when this module is loaded by Gunicorn
if not os.environ.get("DISCORD_BOT_STARTED"):
    os.environ["DISCORD_BOT_STARTED"] = "1"
    bot_thread = threading.Thread(target=run_discord_bot_in_thread)
    bot_thread.daemon = True # thread will exit when main process exits
    
    bot_thread.start()
    logger.info("Discord bot thread started")
    
# this is the app that Gunicorn will use
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
