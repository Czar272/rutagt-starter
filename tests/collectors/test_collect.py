import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "pipeline" / "collectors" / "collect.py"
)
SPEC = importlib.util.spec_from_file_location("rutagt_collect", MODULE_PATH)
collect = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = collect
SPEC.loader.exec_module(collect)


class LinkParserTests(unittest.TestCase):
    def test_resolves_relative_urls_and_ignores_data_urls(self):
        parser = collect.LinkParser("https://example.test/catalog/")
        parser.feed(
            '<a href="docs/mapa.pdf">Mapa</a>'
            '<img src="/img/ruta.png">'
            '<img src="data:image/png;base64,AAAA">'
        )
        self.assertEqual(
            parser.links,
            {
                "https://example.test/catalog/docs/mapa.pdf",
                "https://example.test/img/ruta.png",
            },
        )


class ValidationTests(unittest.TestCase):
    def test_reports_missing_fields_and_bad_encoding(self):
        collection = {
            "features": [
                {
                    "geometry": {"type": "Point", "coordinates": [-90.5, 14.6]},
                    "properties": {"Nombre_lug": "Estaci�n", "Codigoruta": None},
                }
            ]
        }
        source = {
            "expected_geometry": ["Point"],
            "required_fields": ["Nombre_lug", "Codigoruta"],
        }
        warnings = collect.validate_geojson(collection, source)
        self.assertTrue(any("Codigoruta" in warning for warning in warnings))
        self.assertTrue(any("Unicode" in warning for warning in warnings))

    def test_rejects_unexpected_geometry(self):
        collection = {
            "features": [
                {
                    "geometry": {"type": "LineString", "coordinates": []},
                    "properties": {},
                }
            ]
        }
        warnings = collect.validate_geojson(
            collection, {"expected_geometry": ["Point"], "required_fields": []}
        )
        self.assertTrue(any("Geometrías" in warning for warning in warnings))


class ConfigurationTests(unittest.TestCase):
    def test_project_configuration_loads(self):
        config = Path(__file__).resolve().parents[2] / "config" / "sources.json"
        sources = collect.load_sources(config)
        self.assertGreaterEqual(len(sources), 4)
        self.assertEqual(len({source["id"] for source in sources}), len(sources))

    def test_write_json_is_utf8_and_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dato.json"
            body = collect.write_json(path, {"nombre": "Línea 13"})
            self.assertEqual(body, path.read_bytes())
            self.assertIn("Línea".encode("utf-8"), body)


if __name__ == "__main__":
    unittest.main()
