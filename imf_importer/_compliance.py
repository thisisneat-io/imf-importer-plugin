from urllib.parse import urlparse

def make_concept_compliant(res: dict) -> dict:
    return {
        **res,
        "concept": _make_identifier_compliant(_remove_namespace(res["concept"]))
    }

def make_property_compliant(res: dict) -> dict:
    return {
        **res,
        "concept": _make_identifier_compliant(_remove_namespace(res["concept"])),
        "property_": _make_identifier_compliant(_remove_namespace(res["property_"])),
        "value_type": _remove_namespace(res["value_type"])
    }

def _make_identifier_compliant(string: str) -> str:
    return _add_prefix(_replace_hypen(string))

def _remove_namespace(uri: str) -> str:
    if not _is_uri(uri):
        return uri

    if '#' in uri:
        return uri.split('#')[-1]
    else:
        return uri.rsplit('/', 1)[-1]

def _is_uri(string: str) -> bool:
    parsed = urlparse(string)
    return bool(parsed.scheme and parsed.netloc)

def _add_prefix(term: str) -> str:
    return "IMF_" + term

def _replace_hypen(string: str) -> str:
    return string.replace("-", "_")