import sys,os
sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/' + '..'))

import unittest
from util.arxiv_api_client import ArxivAPIClient  # Assuming the class is saved in arxiv_api_client.py

class TestArxivAPIClient(unittest.TestCase):

    def setUp(self):
        """Set up the ArxivAPIClient instance for testing."""
        self.client = ArxivAPIClient()

    def test_get_papers_success(self):
        # Call the get_papers method and check the result
        response = self.client.get_papers('machine learning')
        self.assertIn(b'<entry>', response, "The response should contain the 'entry' tag.")

    def test_parse_arxiv_url_valid(self):
        """Test the parse_arxiv_url method with a valid URL."""
        url = 'http://arxiv.org/abs/1234.5678v2'
        idv, raw_id, version = self.client.parse_arxiv_url(url)
        self.assertEqual(idv, '1234.5678v2')
        self.assertEqual(raw_id, '1234.5678')
        self.assertEqual(version, 2)

    def test_parse_arxiv_url_invalid(self):
        """Test the parse_arxiv_url method with an invalid URL."""
        url = 'http://arxiv.org/abs/invalidurl'
        
        with self.assertRaises(ValueError):
            self.client.parse_arxiv_url(url)

    def test_parse_response(self):
        """Test the parse_response method with a sample response."""
        sample_response = b'''<feed>
                                <entry>
                                    <id>http://arxiv.org/abs/1234.5678v1</id>
                                    <updated>2022-09-22T00:00:00Z</updated>
                                    <title>Sample Title</title>
                                    <summary>Sample Summary</summary>
                                </entry>
                              </feed>'''
        
        parsed_papers = self.client.parse_response(sample_response)
        
        self.assertEqual(len(parsed_papers), 1)
        self.assertEqual(parsed_papers[0]['_id'], '1234.5678')
        self.assertEqual(parsed_papers[0]['_version'], 1)
        self.assertEqual(parsed_papers[0]['_time_str'], 'Sep 22 2022')

    def test_filter_latest_versions(self):
        """Test the filter_latest_versions method to retain only the latest versions."""
        idv_list = ['1234.5678v1', '1234.5678v3', '2345.6789v2', '2345.6789v1']
        latest_versions = self.client.filter_latest_versions(idv_list)
        
        self.assertEqual(len(latest_versions), 2)
        self.assertIn('1234.5678v3', latest_versions)
        self.assertIn('2345.6789v2', latest_versions)

if __name__ == '__main__':
    unittest.main()