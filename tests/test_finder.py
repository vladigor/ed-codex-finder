import io
import json
import unittest
import urllib.error
from unittest.mock import Mock, patch

from codex_finder import config
from codex_finder.canonn import CanonnClient, CanonnError
from codex_finder.finder import find_new_codex_bodies


POD = "Purpureum Rhizome Pod"


class CloudSearchTests(unittest.TestCase):
    def setUp(self):
        self.spansh = Mock()
        self.spansh.landmark_subtypes.return_value = [POD, "Stolon Pod"]
        self.spansh.search_bodies.return_value = {"count": 0, "results": []}
        self.reports = [
            {"english_name": POD, "system": "Hyphaups WM-W d1-0", "distance": "386.17"},
            {"english_name": POD, "system": "Priae Hypae SS-A d1-0", "distance": "492.38"},
            {"english_name": POD, "system": "Hyphaups NI-K d8-0", "distance": "610.21"},
            {"english_name": POD, "system": "Outside", "distance": "1181.98"},
        ]
        self.canonn = patch("codex_finder.finder._canonn_client.nearest_codex")
        self.nearest = self.canonn.start()
        self.addCleanup(self.canonn.stop)
        self.nearest.side_effect = lambda **kwargs: self.reports if kwargs["name"] == POD else []

    def search(self, **kwargs):
        options = dict(
            reference_system="Hyphaups RM-W d1-1",
            reference_coords=(36513.09375, 3.75, 8111.125),
            category=config.CATEGORY_CLOUD,
            found=set(),
            top_n=10,
            max_distance=1000,
        )
        options.update(kwargs)
        return find_new_codex_bodies(self.spansh, **options)

    def test_missing_spansh_reports_are_included_within_radius(self):
        results = self.search()
        self.assertEqual([result.system for result in results], [report["system"] for report in self.reports[:3]])
        self.assertEqual([result.distance for result in results], [386.17, 492.38, 610.21])
        self.assertTrue(all(result.new_entries[POD] == "body not recorded (Canonn)" for result in results))

    def test_found_species_is_not_queried(self):
        self.assertEqual(self.search(found={POD}), [])
        self.assertEqual([call.kwargs["name"] for call in self.nearest.call_args_list], ["Stolon Pod"])

    def test_found_bell_mollusc_alias_is_not_queried_or_returned(self):
        self.spansh.landmark_subtypes.return_value = [POD, "Albens Bell Mollusc"]
        self.spansh.search_bodies.return_value = {
            "count": 1,
            "results": [{"system_name": "Collected", "distance": 10, "landmarks": [{"subtype": "Albens Bell Mollusc"}]}],
        }
        for name in ("Albulus Bell Mollusc", "Albens Bell Mollusc"):
            with self.subTest(found=name):
                self.nearest.reset_mock()
                results = self.search(found={name})
                self.assertNotIn("Collected", [result.system for result in results])
                self.assertEqual(self.spansh.search_bodies.call_args.kwargs["landmark_subtypes"], [POD])
                self.assertEqual([call.kwargs["name"] for call in self.nearest.call_args_list], [POD])

    def test_missing_bell_mollusc_uses_api_name_and_displays_journal_name(self):
        self.spansh.landmark_subtypes.return_value = ["Albens Bell Mollusc"]
        self.spansh.search_bodies.return_value = {
            "count": 1,
            "results": [{"system_name": "Spansh", "name": "Spansh 1", "distance": 10, "landmarks": [{"subtype": "Albens Bell Mollusc"}]}],
        }
        for name in ("Albens Bell Mollusc", "Albulus Bell Mollusc"):
            with self.subTest(report=name):
                self.nearest.side_effect = None
                self.nearest.return_value = [{"english_name": name, "system": "Canonn", "distance": "20"}]
                results = self.search()
                self.assertEqual(self.spansh.search_bodies.call_args.kwargs["landmark_subtypes"], ["Albens Bell Mollusc"])
                self.assertEqual(self.nearest.call_args.kwargs["name"], "Albens Bell Mollusc")
                self.assertEqual([set(result.new_entries) for result in results], [{"Albulus Bell Mollusc"}] * 2)

    def test_merge_precedes_nearest_limit_and_preserves_body(self):
        self.spansh.search_bodies.return_value = {
            "count": 2,
            "results": [
                {"system_name": "Hyphaups NI-K d8-0", "name": "Hyphaups NI-K d8-0 1", "distance": 610.21, "landmarks": [{"subtype": POD}]},
                {"system_name": "Farther", "name": "Farther 1", "distance": 900, "landmarks": [{"subtype": POD}]},
            ],
        }
        results = self.search(top_n=3)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].system, "Hyphaups WM-W d1-0")
        self.assertEqual(results[2].new_entries[POD], "Hyphaups NI-K d8-0 1")

    def test_inexact_name_matches_are_ignored(self):
        self.reports.append({"english_name": "Other Rhizome Pod", "system": "Wrong", "distance": "1"})
        self.assertNotIn("Wrong", [result.system for result in self.search()])

    def test_other_categories_and_missing_coords_do_not_query_canonn(self):
        self.search(category=config.CATEGORY_ANOMALIES)
        self.search(category=config.CATEGORY_BIOLOGY)
        self.search(reference_coords=None)
        self.nearest.assert_not_called()

    def test_canonn_failure_is_not_silently_ignored(self):
        self.nearest.side_effect = CanonnError("unavailable")
        with self.assertRaises(CanonnError):
            self.search()


class CanonnClientTests(unittest.TestCase):
    def test_response_and_encoded_query(self):
        response = io.BytesIO(json.dumps({"nearest": [{"system": "Example"}]}).encode())
        with patch("urllib.request.urlopen", return_value=response) as urlopen:
            results = CanonnClient(min_interval=0).nearest_codex(reference_coords=(1, 2, 3), name=POD, limit=10)
        self.assertEqual(results, [{"system": "Example"}])
        self.assertIn("name=Purpureum+Rhizome+Pod", urlopen.call_args.args[0].full_url)
        self.assertIn("limit=10", urlopen.call_args.args[0].full_url)

    def test_invalid_response_and_network_failure(self):
        for response in ({}, [], {"nearest": None}):
            with self.subTest(response=response), patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(response).encode())):
                with self.assertRaises(CanonnError):
                    CanonnClient(min_interval=0).nearest_codex(reference_coords=(1, 2, 3), name=POD, limit=10)
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            with self.assertRaises(CanonnError):
                CanonnClient(min_interval=0).nearest_codex(reference_coords=(1, 2, 3), name=POD, limit=10)


if __name__ == "__main__":
    unittest.main()