import os
import json
import sys

# 1. MOCK STREAMLIT SECRETS: Create a dictionary wrapper to bypass file checks completely
class MockSecrets(dict):
    def __getattr__(self, key):
        return self[key]

import streamlit as st
secrets_dict = MockSecrets()

# 2. Extract keys from Render Environment Variables and inject them into the mock
gcp_json = os.environ.get("GCP_SERVICE_ACCOUNT")
if gcp_json:
    try:
        secrets_dict["gcp_service_account"] = json.loads(gcp_json)
    except Exception:
        secrets_dict["gcp_service_account"] = gcp_json

openrouter_key = os.environ.get("OPENROUTER_API_KEY")
secrets_dict["openrouter"] = {"api_key": openrouter_key or ""}

# 3. Force Streamlit to use our custom memory-based dictionary
st.secrets = secrets_dict

# 4. Now safely import the rest of your app components
from flask import Flask, request, jsonify
import zynd_competitor_radar
import zynd_lead_harvester  # INJECTED: Lead Harvester Module

app = Flask(__name__)
API_KEY = os.environ.get("ZYND_API_KEY", "default-dev-key")

# --- ENDPOINT 1: COMPETITOR RADAR ---
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

# --- ENDPOINT 2: LEAD HARVESTER ---
@app.route('/harvest-leads', methods=['POST'])
def harvest_leads_endpoint():
    auth_header = request.headers.get("Authorization")
    if not auth_header or auth_header != f"Bearer {API_KEY}":
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    target_persona = data.get('persona', 'Product Manager')
    ecosystem = data.get('ecosystem', 'Web3')

    if not target_persona or not ecosystem:
        return jsonify({"error": "Missing 'persona' or 'ecosystem'"}), 400

    try:
        # Trigger your Python script to scrape and extract contact details
        result = zynd_lead_harvester.execute_harvest(target_persona, ecosystem)
        return jsonify({"status": "success", "data": result}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
