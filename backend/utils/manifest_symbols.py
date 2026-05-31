"""Extract autocomplete symbols from a dbt manifest.json dict (issue 16)."""


def extract_symbols(manifest: dict) -> dict:
    nodes = (manifest or {}).get("nodes", {})
    sources = (manifest or {}).get("sources", {})
    macros = (manifest or {}).get("macros", {})

    models = [n["name"] for n in nodes.values()
              if n.get("resource_type") == "model" and n.get("name")]
    source_pairs = [{"source": s.get("source_name"), "table": s.get("name")}
                    for s in sources.values()
                    if s.get("source_name") and s.get("name")]
    macro_names = [m["name"] for m in macros.values() if m.get("name")]

    return {"models": models, "sources": source_pairs, "macros": macro_names}
