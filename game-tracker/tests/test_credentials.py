import base64
import json
import unittest

from inspect_sheet import key_info

KEY = {"type": "service_account", "client_email": "bot@example.iam.gserviceaccount.com",
       "private_key": "not-a-real-key"}


class KeyInfoTest(unittest.TestCase):
    def test_raw_json(self):
        self.assertEqual(key_info(json.dumps(KEY, indent=2)), KEY)

    def test_base64(self):
        encoded = base64.b64encode(json.dumps(KEY).encode()).decode()
        self.assertEqual(key_info(encoded + " "), KEY)


if __name__ == "__main__":
    unittest.main()
