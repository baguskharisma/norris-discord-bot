from flask import Flask, render_template, request, jsonify
import os
import logging
import datetime

# setup logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "deafult-secret-key")

# to track bot status
BOT_STATUS = {
    "status": "Offline",
    "last_updated": datetime.datetime.now().isoformat(),
    "uptime": None
}

@app.route('/')
def index():
    """home page - simple status page for the Discord bot."""
    return render_template('index.html')

@app.route('/bot-status', methods=['GET'])
def bot_status():
    """API endpoint to get the bot's status."""
    return jsonify(BOT_STATUS)

@app.route('/bot-status/update', methods=['POST'])
def update_bot_status():
    """API endpoint for the bot to update its status."""
    if request.json:
        for key in request.json:
            if key in BOT_STATUS:
                BOT_STATUS[key] = request.json[key]
        
        # always update the last_updated timestamp
        BOT_STATUS["last_updated"] = datetime.datetime.now().isoformat()
        return jsonify({"succcess": True, "status": BOT_STATUS})
    
    return jsonify({"success": False, "error": "Invalid data"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
                    
        