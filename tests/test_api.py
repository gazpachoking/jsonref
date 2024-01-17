from jsonref import load, loads, dump, dumps


class TestApi(object):
    def test_loads(self):
        json = """{"a": 1, "b": {"$ref": "#/a"}}"""
        assert loads(json) == {"a": 1, "b": 1}

    def test_loads_kwargs(self):
        json = """{"a": 5.5, "b": {"$ref": "#/a"}}"""
        loaded = loads(json, parse_float=lambda x: int(float(x)))
        assert loaded["a"] == loaded["b"] == 5

    def test_load(self, tmpdir):
        json = """{"a": 1, "b": {"$ref": "#/a"}}"""
        tmpdir.join("in.json").write(json)
        assert load(tmpdir.join("in.json")) == {"a": 1, "b": 1}

    def test_dumps(self):
        json = """[1, 2, {"$ref": "#/0"}, 3]"""
        loaded = loads(json)
        # The string version should load the reference
        assert str(loaded) == "[1, 2, 1, 3]"
        # Our dump function should write the original reference
        assert dumps(loaded) == json

    def test_dump(self, tmpdir):
        json = """[1, 2, {"$ref": "#/0"}, 3]"""
        loaded = loads(json)
        # The string version should load the reference
        assert str(loaded) == "[1, 2, 1, 3]"
        dump(loaded, tmpdir.join("out.json"))
        # Our dump function should write the original reference
        assert tmpdir.join("out.json").read() == json
