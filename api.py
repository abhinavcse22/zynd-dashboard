import os
from flask import Flask, request, jsonify
import streamlit as st

# 1. Mirror the environment variables into streamlit's secrets system for compatibility
import json
gcp_json = os.environ.get("GCP_SERVICE_ACCOUNT")
if gcp_json:
    st.secrets["gcp_service_account"] = json.loads(gcp_json)

openrouter_key = os.environ.get("OPENROUTER_API_KEY")
if openrouter_key:
    st.secrets["openrouter"] = {"api_key": openrouter_key}

# 2. Import your engine AFTER secrets are initialized
import zynd_competitor_radar

app = Flask(__name__)
API_KEY = os.environ.get("ZYND_API_KEY", "default-dev-key")

@app.route('/scan-competitor', methods=['POST'])
def scan_competitor_endpoint():
    auth_header = request.headers.get("Authorization")
    if not auth_header or auth_header != f"Bearer {API_KEY}":
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    target_url = data.get('target')
    competitor_name = data.get('name', 'Unknown Competitor')

    if not target_url:
        return jsonify({"error": "Missing 'target'"}), 400

    try:
        result = zynd_competitor_radar.execute_competitor_radar_sweep(competitor_name, target_url)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
