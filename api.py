import os
from flask import Flask, request, jsonify

# Import your existing competitor radar engine!
import zynd_competitor_radar

app = Flask(__name__)

@app.route('/scan-competitor', methods=['POST'])
def scan_competitor_endpoint():
    data = request.get_json()
    target_url = data.get('target')

    if not target_url:
        return jsonify({"error": "Missing 'target' parameter"}), 400

    try:
        # We pass the URL from Hermes directly into your existing Streamlit engine logic
        # NOTE: We need to use the exact function name from your zynd_competitor_radar.py file
        result = zynd_competitor_radar.run_competitor_scan(target_url) 
        
        return jsonify({"status": "success", "data": result}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
