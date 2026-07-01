import os
from flask import Flask, request, jsonify

# Import your existing engine
import zynd_competitor_radar

app = Flask(__name__)

# Basic security to ensure only Hermes can trigger the engine
API_KEY = os.environ.get("ZYND_API_KEY", "default-dev-key")

@app.route('/scan-competitor', methods=['POST'])
def scan_competitor_endpoint():
    # Verify Hermes authentication
    auth_header = request.headers.get("Authorization")
    if not auth_header or auth_header != f"Bearer {API_KEY}":
        return jsonify({"error": "Unauthorized access"}), 401

    data = request.get_json()
    target_url = data.get('target')
    competitor_name = data.get('name', 'Unknown Competitor')

    if not target_url:
        return jsonify({"error": "Missing 'target' parameter"}), 400

    try:
        # Trigger your exact Streamlit function in the background
        result = zynd_competitor_radar.execute_competitor_radar_sweep(competitor_name, target_url)
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
