from flask import Flask, request, jsonify
import numpy as np
import logging
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Prometheus metrics
prediction_counter = Counter('ml_predictions_total', 'Total number of predictions made')
prediction_duration = Histogram('ml_prediction_duration_seconds', 'Time spent processing prediction')

# Simple dummy model (replace with your actual model)
class DummyModel:
    def predict(self, features):
        # Simulate some processing time
        time.sleep(0.1)
        # Return dummy prediction
        return np.random.random()

model = DummyModel()

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'ml-inference'}), 200

@app.route('/predict', methods=['POST'])
def predict():
    """Prediction endpoint"""
    start_time = time.time()

    try:
        # Get features from request
        data = request.get_json()
        if not data or 'features' not in data:
            return jsonify({'error': 'No features provided'}), 400

        features = data['features']
        logger.info(f"Received prediction request with features: {features}")

        # Make prediction
        prediction = model.predict(features)

        # Update metrics
        prediction_counter.inc()
        prediction_duration.observe(time.time() - start_time)

        response = {
            'prediction': float(prediction),
            'model_version': '1.0.0',
            'timestamp': time.time()
        }

        logger.info(f"Prediction completed: {response}")
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        return jsonify({'error': str(e)}), 500

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
    app.run(host='0.0.0.0', port=8001, debug=False)
