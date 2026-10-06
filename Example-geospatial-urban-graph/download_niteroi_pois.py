#!/usr/bin/env python3
"""Download and normalize official Niterói POIs from the municipal SIGeo ArcGIS services.

Output columns:
external_id,kind,category,name,address,bairro,cep,latitude,longitude,source,source_layer

The downloader uses public ArcGIS REST layers from Prefeitura Municipal de Niterói.
"""

from __future__ import annotations

import argparse
import csv
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    import certifi
except ImportError:  # pragma: no cover - handled with a clear runtime message.
    certifi = None

try:
    import truststore
except ImportError:  # pragma: no cover - optional but preferred on Windows.
    truststore = None


LAYERS = [
    {
        "service": "https://geo.niteroi.rj.gov.br/arcgis/rest/services/dadosabertos/AS_SMF_CLIN_CULT_EDUC_LIMPOL/MapServer",
        "layer": 5,
        "kind": "facility",
        "category": "social_assistance",
        "name_fields": ["Nome", "tx_nome"],
        "address_fields": ["Logradouro", "tx_endereco", "tx_end"],
        "number_fields": ["numero", "tx_numero"],
        "bairro_fields": ["tx_bairro", "BAIRRO", "bairro"],
        "cep_fields": ["cep", "CEP"],
        "label": "Equipamentos da Assistência Social",
    },
    {
        "service": "https://geo.niteroi.rj.gov.br/arcgis/rest/services/dadosabertos/AS_SMF_CLIN_CULT_EDUC_LIMPOL/MapServer",
        "layer": 10,
        "kind": "facility",
        "category": "women_support",
        "name_fields": ["tx_nome", "Nome"],
        "address_fields": ["tx_end", "tx_endereco", "Endereco"],
        "number_fields": ["tx_numero", "numero"],
        "bairro_fields": ["tx_bairro", "BAIRRO", "bairro"],
        "cep_fields": ["cep", "CEP"],
        "label": "Rede de atendimento à Mulher",
    },
    {
        "service": "https://geo.niteroi.rj.gov.br/arcgis/rest/services/dadosabertos/AS_SMF_CLIN_CULT_EDUC_LIMPOL/MapServer",
        "layer": 50,
        "kind": "facility",
        "category": "culture",
        "name_fields": ["Nome", "tx_nome"],
        "address_fields": ["Endereco", "ENDERECO", "tx_endereco"],
        "number_fields": ["numero", "tx_numero"],
        "bairro_fields": ["tx_bairro", "BAIRRO", "bairro"],
        "cep_fields": ["cep", "CEP"],
        "label": "Patrimônios e Equipamentos Culturais",
    },
    {
        "service": "https://geo.niteroi.rj.gov.br/arcgis/rest/services/dadosabertos/AS_SMF_CLIN_CULT_EDUC_LIMPOL/MapServer",
        "layer": 55,
        "kind": "facility",
        "category": "education_childhood",
        "name_fields": ["tx_nome", "tx_escola", "Nome"],
        "address_fields": ["tx_endereco", "Endereco", "ENDERECO"],
        "number_fields": ["tx_numero", "numero"],
        "bairro_fields": ["tx_bairro", "BAIRRO", "bairro"],
        "cep_fields": ["cep", "CEP"],
        "label": "Unidade Municipal de Ensino Infantil",
    },
    {
        "service": "https://geo.niteroi.rj.gov.br/arcgis/rest/services/dadosabertos/AS_SMF_CLIN_CULT_EDUC_LIMPOL/MapServer",
        "layer": 60,
        "kind": "facility",
        "category": "education_municipal",
        "name_fields": ["tx_nome", "tx_escola", "Nome"],
        "address_fields": ["tx_endereco", "Endereco", "ENDERECO"],
        "number_fields": ["tx_numero", "numero"],
        "bairro_fields": ["tx_bairro", "BAIRRO", "bairro"],
        "cep_fields": ["cep", "CEP"],
        "label": "Escolas Municipais",
    },
    {
        "service": "https://geo.niteroi.rj.gov.br/arcgis/rest/services/dadosabertos/AS_SMF_CLIN_CULT_EDUC_LIMPOL/MapServer",
        "layer": 65,
        "kind": "facility",
        "category": "education_state",
        "name_fields": ["tx_nome", "tx_escola", "Nome"],
        "address_fields": ["tx_endereco", "Endereco", "ENDERECO"],
        "number_fields": ["tx_numero", "numero"],
        "bairro_fields": ["tx_bairro", "BAIRRO", "bairro"],
        "cep_fields": ["cep", "CEP"],
        "label": "Escolas Estaduais",
    },
    {
        "service": "https://geo.niteroi.rj.gov.br/arcgis/rest/services/dadosabertos/SMARHS_SMDCG_SMS_SMU/MapServer",
        "layer": 105,
        "kind": "facility",
        "category": "hospital",
        "name_fields": ["name", "nome", "NOME"],
        "address_fields": ["address", "endereco", "ENDERECO", "lograd"],
        "number_fields": ["numrop", "numero"],
        "bairro_fields": ["bairro", "BAIRRO"],
        "cep_fields": ["cep", "CEP"],
        "label": "Hospitais",
    },
    {
        "service": "https://geo.niteroi.rj.gov.br/arcgis/rest/services/dadosabertos/SMARHS_SMDCG_SMS_SMU/MapServer",
        "layer": 110,
        "kind": "facility",
        "category": "health",
        "name_fields": ["nome", "NOME", "nomegen"],
        "address_fields": ["lograd", "ENDERECO", "endereco"],
        "number_fields": ["numrop", "numero"],
        "bairro_fields": ["bairro", "BAIRRO"],
        "cep_fields": ["cep", "CEP"],
        "label": "Rede de Saúde",
    },
    {
        "service": "https://geo.niteroi.rj.gov.br/arcgis/rest/services/dadosabertos/SMARHS_SMDCG_SMS_SMU/MapServer",
        "layer": 115,
        "kind": "facility",
        "category": "family_health",
        "name_fields": ["NOME", "nome", "NOMEABREV"],
        "address_fields": ["ENDERECO", "endereco", "LOCALIDADE"],
        "number_fields": ["numero", "numrop"],
        "bairro_fields": ["BAIRRO", "bairro"],
        "cep_fields": ["cep", "CEP"],
        "label": "Rede Programa Médico de Família",
    },
]


def first_value(props: dict, fields: list[str]) -> str:
    for field in fields:
        value = props.get(field)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def build_ssl_context(
    ca_bundle: Path | None,
    insecure: bool,
    tls_mode: str,
) -> ssl.SSLContext:
    """Build an explicit TLS context.

    tls_mode:
    - auto: prefer OS trust store via truststore, then certifi, then stdlib;
    - system: require OS trust store via truststore;
    - certifi: require Mozilla CA bundle from certifi.
    """
    if insecure:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    if ca_bundle is not None:
        if not ca_bundle.exists():
            raise FileNotFoundError(f"CA bundle not found: {ca_bundle}")
        return ssl.create_default_context(cafile=str(ca_bundle))

    if tls_mode not in {"auto", "system", "certifi"}:
        raise ValueError("tls_mode must be auto, system, or certifi")

    if tls_mode in {"auto", "system"} and truststore is not None:
        # truststore uses the native certificate store (Windows CryptoAPI on
        # Windows), matching what browsers and many desktop applications trust.
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    if tls_mode == "system":
        raise RuntimeError(
            "TLS mode 'system' requires the 'truststore' package. "
            "Install it with: python -m pip install -U truststore"
        )

    if tls_mode in {"auto", "certifi"} and certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())

    if tls_mode == "certifi":
        raise RuntimeError(
            "TLS mode 'certifi' requires certifi. "
            "Install it with: python -m pip install -U certifi"
        )

    return ssl.create_default_context()


def download_geojson(
    base: str,
    layer: int,
    context: ssl.SSLContext,
    retries: int = 3,
) -> dict:
    query = urllib.parse.urlencode(
        {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
        }
    )
    url = f"{base}/{layer}/query?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "NexusDB-geospatial-example/1.0",
            "Accept": "application/geo+json, application/json",
        },
    )

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(
                req,
                timeout=120,
                context=context,
            ) as response:
                content_type = response.headers.get("Content-Type", "")
                payload = response.read().decode("utf-8")
                data = json.loads(payload)

                if isinstance(data, dict) and data.get("error"):
                    raise RuntimeError(
                        f"ArcGIS layer {layer} returned an error: "
                        f"{json.dumps(data['error'], ensure_ascii=False)}"
                    )

                if "json" not in content_type.lower() and not isinstance(data, dict):
                    raise RuntimeError(
                        f"Unexpected response for ArcGIS layer {layer}: {content_type}"
                    )
                return data

        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * attempt)

    assert last_error is not None
    if isinstance(last_error, urllib.error.URLError):
        reason = getattr(last_error, "reason", last_error)
        if isinstance(reason, ssl.SSLCertVerificationError) or (
            "CERTIFICATE_VERIFY_FAILED" in str(reason)
        ):
            raise RuntimeError(
                "TLS certificate validation failed while accessing SIGeo. "
                "On Windows, install truststore and retry with '--tls-mode system': "
                "'python -m pip install -U truststore'. You can also use "
                "'--tls-mode certifi', pass --ca-bundle PATH for a custom CA, "
                "or use --insecure only for a controlled diagnostic run."
            ) from last_error

    raise RuntimeError(
        f"Could not download ArcGIS layer {layer} after {retries} attempts: "
        f"{last_error}"
    ) from last_error


def normalize_feature(source: dict, feature: dict, index: int) -> dict:
    props = feature.get("properties") or {}
    geom = feature.get("geometry") or {}
    coords = geom.get("coordinates") or [None, None]
    lon = coords[0] if len(coords) >= 2 else None
    lat = coords[1] if len(coords) >= 2 else None

    name = first_value(props, source["name_fields"])
    address = first_value(props, source["address_fields"])
    number = first_value(props, source["number_fields"])
    if address and number and number.lower() not in address.lower():
        address = f"{address}, {number}"

    object_id = (
        props.get("OBJECTID")
        or props.get("OBJECTID_1")
        or props.get("FID")
        or index
    )

    return {
        "external_id": f"NIT-{source['layer']}-{object_id}",
        "kind": source["kind"],
        "category": source["category"],
        "name": name or f"{source['label']} #{object_id}",
        "address": address,
        "bairro": first_value(props, source["bairro_fields"]),
        "cep": first_value(props, source["cep_fields"]),
        "latitude": lat,
        "longitude": lon,
        "source": "Prefeitura Municipal de Niterói / SIGeo",
        "source_layer": source["label"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download and normalize official Niterói SIGeo POIs."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("niteroi_pois.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--ca-bundle",
        type=Path,
        help="Optional PEM CA bundle (useful behind corporate TLS inspection).",
    )
    parser.add_argument(
        "--tls-mode",
        choices=("auto", "system", "certifi"),
        default="auto",
        help=(
            "TLS trust source: auto prefers the OS trust store via truststore, "
            "then certifi; system forces the OS trust store; certifi forces "
            "the Mozilla CA bundle."
        ),
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification. Diagnostic use only.",
    )
    parser.add_argument(
        "--skip-failed-layers",
        action="store_true",
        help="Continue when one ArcGIS layer fails and write the remaining POIs.",
    )
    args = parser.parse_args()

    if (
        truststore is None
        and certifi is None
        and not args.insecure
        and args.ca_bundle is None
    ):
        print(
            "WARNING: neither truststore nor certifi is installed; falling "
            "back to Python's default CA discovery."
        )

    context = build_ssl_context(
        args.ca_bundle,
        args.insecure,
        args.tls_mode,
    )
    output = args.output
    rows: list[dict] = []
    failed_layers: list[tuple[str, str]] = []

    for source in LAYERS:
        print(f"Downloading {source['label']} (layer {source['layer']})...")
        try:
            data = download_geojson(
                source["service"],
                source["layer"],
                context=context,
            )
        except Exception as exc:
            if not args.skip_failed_layers:
                raise
            failed_layers.append((source["label"], str(exc)))
            print(f"  WARNING: skipped: {exc}")
            continue
        features = data.get("features", [])
        print(f"  {len(features)} features")
        for i, feature in enumerate(features, 1):
            row = normalize_feature(source, feature, i)
            if row["latitude"] is None or row["longitude"] is None:
                continue
            rows.append(row)

    rows.sort(key=lambda r: (r["category"], r["name"], r["external_id"]))

    fields = [
        "external_id",
        "kind",
        "category",
        "name",
        "address",
        "bairro",
        "cep",
        "latitude",
        "longitude",
        "source",
        "source_layer",
    ]
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print()
    print(f"Wrote {len(rows)} POIs to {output.resolve()}")
    if args.insecure:
        print("WARNING: TLS verification was disabled for this run.")
    if failed_layers:
        print(f"Skipped {len(failed_layers)} layer(s):")
        for label, message in failed_layers:
            print(f"  - {label}: {message}")


if __name__ == "__main__":
    main()
