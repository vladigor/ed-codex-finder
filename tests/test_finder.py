import io
import json
import unittest
import urllib.error
from unittest.mock import Mock, patch

from codex_finder import codex, config
from codex_finder.canonn import CanonnClient, CanonnError
from codex_finder.cli import _print_results
from codex_finder.finder import SearchStatus, SystemResult, find_new_codex_bodies
from codex_finder.web import _App


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


class BiologySearchTests(unittest.TestCase):
    def setUp(self):
        exclusions = patch("codex_finder.config.get_biology_excluded_species", return_value=set())
        self.exclusions = exclusions.start()
        self.addCleanup(exclusions.stop)

    def test_exclusions_filter_queries_and_mixed_body_landmarks(self):
        self.exclusions.return_value = {
            "Anemone", "Electricae", "Fumerolas", "Fungoids", "Shards",
            "Bacterium Aurasus",
        }
        excluded = [
            "Puniceum Anemone", "Electricae Pluma", "Fumerola Aquatis",
            "Fungoida Setisis", "Crystalline Shard", "Bacterium Aurasus",
        ]
        spansh = Mock()
        spansh.landmark_subtypes.return_value = excluded + ["Tussock Capillum"]
        spansh.search_bodies.return_value = {"count": 1, "results": [
            {"system_name": "Mixed", "name": "Mixed 1", "distance": 10,
             "landmarks": [{"subtype": name, "variant": "Green"}
                           for name in excluded + ["Tussock Capillum"]]},
        ]}
        results = find_new_codex_bodies(
            spansh, reference_system="Example", category=config.CATEGORY_BIOLOGY,
            found=set(), max_distance=500,
        )
        self.assertEqual(spansh.search_bodies.call_args.kwargs["landmark_subtypes"],
                         ["Tussock Capillum"])
        self.assertEqual(results[0].new_entries, {"Tussock Capillum - Green": "Mixed 1"})

    def test_all_excluded_skips_search(self):
        self.exclusions.return_value = {"Anemone"}
        spansh = Mock()
        spansh.landmark_subtypes.return_value = ["Puniceum Anemone"]
        self.assertEqual(find_new_codex_bodies(
            spansh, reference_system="Example", category=config.CATEGORY_BIOLOGY,
            found=set(),
        ), [])
        spansh.search_bodies.assert_not_called()

    def test_page_cap_status_for_empty_and_partial_results(self):
        for has_new in (False, True):
            with self.subTest(has_new=has_new):
                spansh = Mock()
                spansh.landmark_subtypes.return_value = ["Tussock Capillum"]
                spansh.search_bodies.return_value = {"count": 1300, "results": [
                    {"system_name": "Example", "distance": 10,
                     "landmarks": [{"type": "Tussock", "subtype": "Tussock Capillum",
                                    "variant": "Red" if has_new else "Green"}]},
                ]}
                status = SearchStatus()
                results = find_new_codex_bodies(
                    spansh, reference_system="Example", category=config.CATEGORY_BIOLOGY,
                    found={"Tussock Capillum - Green"}, status=status, max_distance=500,
                )
                self.assertTrue(status.limit_reached)
                self.assertEqual(len(results), int(has_new))
                self.assertEqual(spansh.search_bodies.call_count, 12)

    def test_normal_stops_do_not_report_page_cap(self):
        for count, variant, top_n, expected_pages in (
            (0, None, 10, 1), (1200, "Green", 10, 12),
            (1300, "Red", 1, 1), (1300, "Red", 1, 12),
        ):
            with self.subTest(count=count, variant=variant, expected_pages=expected_pages):
                spansh = Mock()
                spansh.landmark_subtypes.return_value = ["Tussock Capillum"]

                def search_bodies(**kwargs):
                    colour = variant
                    if expected_pages == 12 and variant == "Red" and kwargs["page"] < 11:
                        colour = "Green"
                    return {"count": count, "results": [] if variant is None else [
                        {"system_name": "Example", "distance": 10,
                         "landmarks": [{"type": "Tussock", "subtype": "Tussock Capillum",
                                        "variant": colour}]},
                    ]}

                spansh.search_bodies.side_effect = search_bodies
                status = SearchStatus(limit_reached=True)
                find_new_codex_bodies(
                    spansh, reference_system="Example", category=config.CATEGORY_BIOLOGY,
                    found={"Tussock Capillum - Green"}, status=status, top_n=top_n,
                )
                self.assertFalse(status.limit_reached)
                self.assertEqual(spansh.search_bodies.call_count, expected_pages)

    def test_anemones_are_not_buried_by_found_colour_variants(self):
        spansh = Mock()
        spansh.landmark_subtypes.return_value = [
            "Puniceum Anemone", "Roseum Anemone", "Bark Mounds", "Stratum Tectonicas",
        ]

        def search_bodies(**kwargs):
            if "Puniceum Anemone" in kwargs["landmark_subtypes"]:
                return {"count": 2, "results": [
                    {"system_name": "HD 99897", "name": "HD 99897 B 1 a", "distance": 802.23,
                     "landmarks": [{"type": "Anemone", "subtype": "Puniceum Anemone"}]},
                    {"system_name": "Roseum system", "name": "Roseum system 1", "distance": 900,
                     "landmarks": [{"type": "Anemone", "subtype": "Roseum Anemone"}]},
                ]}
            return {"count": 10000, "results": [
                {"system_name": "Collected", "distance": 100,
                 "landmarks": [{"type": "Stratum", "subtype": "Stratum Tectonicas", "variant": "Green"}]},
            ]}

        spansh.search_bodies.side_effect = search_bodies
        results = find_new_codex_bodies(
            spansh, reference_system="HIP 72344", category=config.CATEGORY_BIOLOGY,
            found={"Bark Mounds", "Stratum Tectonicas - Green"}, max_distance=2000,
        )
        self.assertEqual([result.system for result in results], ["HD 99897", "Roseum system"])
        self.assertEqual(results[0].new_entries, {"Puniceum Anemone": "HD 99897 B 1 a"})
        self.assertEqual(spansh.search_bodies.call_args_list[0].kwargs["landmark_subtypes"],
                         ["Puniceum Anemone", "Roseum Anemone"])
        self.assertTrue(all(call.kwargs["max_distance"] == 2000
                            for call in spansh.search_bodies.call_args_list))

    def test_batches_merge_before_nearest_limit(self):
        spansh = Mock()
        spansh.landmark_subtypes.return_value = ["Puniceum Anemone", "Tussock Capillum"]
        spansh.search_bodies.side_effect = [
            {"count": 1, "results": [
                {"system_name": "Farther", "distance": 802,
                 "landmarks": [{"subtype": "Puniceum Anemone"}]},
            ]},
            {"count": 1, "results": [
                {"system_name": "Nearer", "distance": 100,
                 "landmarks": [{"type": "Tussock", "subtype": "Tussock Capillum", "variant": "Green"}]},
            ]},
        ]
        results = find_new_codex_bodies(
            spansh, reference_system="HIP 72344", category=config.CATEGORY_BIOLOGY,
            found=set(), top_n=1, max_distance=2000,
        )
        self.assertEqual([result.system for result in results], ["Nearer"])
        self.assertEqual(spansh.search_bodies.call_count, 2)


class SearchStatusPresentationTests(unittest.TestCase):
    def test_cli_distinguishes_capped_empty_and_partial_searches(self):
        for results in ([], [SystemResult("Example", 10, {"New entry": "Body"})]):
            with self.subTest(results=results), patch("sys.stdout", new_callable=io.StringIO) as output:
                _print_results("biology", "Origin", 0, results, 500, search_limit_reached=True)
                text = output.getvalue()
                self.assertIn("Search limit reached", text)
                self.assertNotIn("were found within", text)
                if not results:
                    self.assertIn("bodies examined", text)

    def test_cli_normal_empty_search_keeps_radius_message(self):
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            _print_results("biology", "Origin", 0, [], 500)
            self.assertIn("were found within 500 ly", output.getvalue())
            self.assertNotIn("Search limit reached", output.getvalue())

    def test_web_response_propagates_search_status(self):
        app = _App(config.DEFAULT_JOURNAL_DIR)
        app.journal = Mock()
        state = app.journal.scan.return_value
        state.current.system = "Origin"
        state.current.star_pos = None
        state.found = {"biology": set()}
        for capped in (False, True):
            def search(client, **kwargs):
                kwargs["status"].limit_reached = capped
                return []

            with self.subTest(capped=capped), patch("codex_finder.web.find_new_codex_bodies", side_effect=search):
                response = app.search("biology", 500, 10)
                self.assertEqual(response["search_limit_reached"], capped)
                self.assertEqual(response["results"], [])


class BiologyConfigTests(unittest.TestCase):
    def test_supplied_groups_match_api_names(self):
        names = {
            "Amphora Plant": "Amphora Plant", "Anemone": "Roseum Anemone",
            "Bark Mounds": "Bark Mounds", "Brain Tree": "Roseum Brain Tree",
            "Electricae": "Electricae Radialem", "Fumerolas": "Fumerola Aquatis",
            "Fungoids": "Fungoida Setisis", "Radicoida": "Radicoida Unica",
            "Shards": "Crystalline Shard",
        }
        for group, subtype in names.items():
            with self.subTest(group=group):
                self.assertTrue(codex.biology_is_excluded(subtype, {group.lower()}))
        self.assertFalse(codex.biology_is_excluded("Bacterium Aurasus", {"Bacter"}))
        self.assertFalse(codex.biology_is_excluded("Bacterium Acies", {"Bacterium Aurasus"}))

    def test_config_is_reread_and_can_be_overridden(self):
        with patch.dict("os.environ", {"CODEX_FINDER_CONFIG": "/user/settings.json"}), patch(
            "pathlib.Path.read_text", side_effect=[
                '{"biology_excluded_species": [" Anemone "]}',
                '{"biology_excluded_species": ["Electricae"]}',
            ],
        ) as read:
            self.assertEqual(config.get_biology_excluded_species(), {"Anemone"})
            self.assertEqual(config.get_biology_excluded_species(), {"Electricae"})
            self.assertEqual(read.call_count, 2)

    def test_missing_default_is_optional_but_missing_override_is_error(self):
        with patch.dict("os.environ", {}, clear=True), patch(
            "pathlib.Path.read_text", side_effect=FileNotFoundError,
        ):
            self.assertEqual(config.get_biology_excluded_species(), set())
            with patch.dict("os.environ", {"CODEX_FINDER_CONFIG": "/missing.json"}):
                with self.assertRaisesRegex(ValueError, "Configuration file not found"):
                    config.get_biology_excluded_species()

    def test_invalid_config_is_reported(self):
        for content in ('{', '[]', '{"biology_excluded_species": "Anemone"}',
                        '{"biology_excluded_species": [null]}',
                        '{"biology_excluded_species": [" "]}'):
            with self.subTest(content=content), patch("pathlib.Path.read_text", return_value=content):
                with self.assertRaises(ValueError):
                    config.get_biology_excluded_species()


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