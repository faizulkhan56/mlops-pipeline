import unittest
import json
import sys
import os

# Add the parent directory to Python path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app import app
except ImportError:
    # If direct import fails, try relative import
    import app as app_module
    app = app_module.app

class TestDataIngestion(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_health_endpoint(self):
        response = self.app.get('/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'healthy')

    def test_ingest_endpoint(self):
        test_data = {'sensor': 'temp01', 'value': 25.5}
        response = self.app.post('/ingest',
                                data=json.dumps(test_data),
                                content_type='application/json')
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertIn('id', data)

    def test_get_data_endpoint(self):
        # First ingest some data
        test_data = {'sensor': 'temp01', 'value': 25.5}
        response = self.app.post('/ingest',
                                data=json.dumps(test_data),
                                content_type='application/json')
        data_id = json.loads(response.data)['id']

        # Then retrieve it
        response = self.app.get(f'/data/{data_id}')
        self.assertEqual(response.status_code, 200)

if __name__ == '__main__':
    unittest.main()
