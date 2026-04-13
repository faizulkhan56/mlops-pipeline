from flask import Flask, request, jsonify
import logging
import json
import time
from datetime import datetime
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Prometheus metrics
ingestion_counter = Counter('data_ingestion_total', 'Total number of data ingested')
ingestion_duration = Histogram('data_ingestion_duration_seconds', 'Time spent ingesting data')
data_size_histogram = Histogram('data_size_bytes', 'Size of ingested data in bytes')

# Data storage (in production, use a database or message queue)
data_store = []

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'data-ingestion'}), 200

@app.route('/ingest', methods=['POST'])
def ingest():
    """Data ingestion endpoint"""
    start_time = time.time()

    try:
        # Get data from request
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Add metadata
        ingestion_record = {
            'data': data,
            'timestamp': datetime.utcnow().isoformat(),
            'source_ip': request.remote_addr,
            'id': len(data_store) + 1
        }

        # Simulate data processing
        time.sleep(0.05)

        # Store data (in production, save to database)
        data_store.append(ingestion_record)

        # Update metrics
        ingestion_counter.inc()
        ingestion_duration.observe(time.time() - start_time)
        data_size_histogram.observe(len(json.dumps(data)))

        logger.info(f"Data ingested successfully: ID={ingestion_record['id']}")

        return jsonify({
            'status': 'success',
            'id': ingestion_record['id'],
            'timestamp': ingestion_record['timestamp']
        }), 201

    except Exception as e:
        logger.error(f"Ingestion error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/data/<int:data_id>', methods=['GET'])
def get_data(data_id):
    """Retrieve ingested data by ID"""
    for record in data_store:
        if record['id'] == data_id:
            return jsonify(record), 200
    return jsonify({'error': 'Data not found'}), 404

@app.route('/data', methods=['GET'])
def list_data():
    """List all ingested data"""
    limit = request.args.get('limit', 10, type=int)
    return jsonify({
        'total': len(data_store),
        'data': data_store[-limit:]
    }), 200

@app.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus metrics endpoint"""
    try:
        # Return metrics with proper content type
        return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}
    except Exception as e:
        logger.error(f"Metrics error: {str(e)}")
        return "Metrics unavailable", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8002, debug=False)
