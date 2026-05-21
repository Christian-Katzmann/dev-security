from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import unquote
import hashlib
import uuid

from .decisions import VEX_STATUSES, normalize_case_decision, normalize_vex_status


EXPORT_DECISION_STATUSES = {"false_positive", "accepted_risk"}
EXPORT_VEX_STATUSES = {"affected", "not_affected"}

VEX_STATUS_TO_DECISION_STATUS = {
    "affected": "accepted_risk",
    "not_affected": "false_positive",
    "fixed": "fixed",
    "under_investigation": "verified",
}

IMPORT_STATUS_ALIASES = {
    "exploitable": "affected",
    "false_positive": "not_affected",
    "in_triage": "under_investigation",
    "resolved": "fixed",
    "resolved_with_pedigree": "fixed",
}

OPENVEX_CONTEXT = "https://openvex.dev/ns/v0.2.0"


def build_vex_document(
    decisions: Iterable[dict[str, Any]],
    *,
    tool_version: str,
    repo_name: str | None = None,
) -> dict[str, Any]:
    statements = []
    for raw_decision in decisions:
        decision = normalize_case_decision(dict(raw_decision))
        if repo_name and str(decision.get("repo_name") or "") != repo_name:
            continue
        if not _is_exportable_decision(decision):
            continue
        statements.append(_statement_from_decision(decision))

    timestamp = utc_now()
    return {
        "@context": OPENVEX_CONTEXT,
        "@id": f"urn:uuid:{uuid.uuid4()}",
        "author": "Security Observatory",
        "timestamp": timestamp,
        "version": 1,
        "metadata": {
            "tool": {
                "name": "security-observatory",
                "version": tool_version,
            },
            "supported_subset": "dependency decisions with status affected or not_affected",
            "repo_name": repo_name,
            "exported_decisions": len(statements),
        },
        "statements": statements,
    }


def parse_vex_document(document: dict[str, Any], *, repo_name: str | None = None) -> dict[str, Any]:
    warnings = ["Unsupported VEX fields are ignored; only dependency identity, status, reason, and repository are imported."]
    decisions: list[dict[str, Any]] = []
    skipped = 0

    statements = document.get("statements")
    vulnerabilities = document.get("vulnerabilities")
    if isinstance(statements, list):
        for index, statement in enumerate(statements, start=1):
            parsed = _decisions_from_openvex_statement(statement, index=index, default_repo_name=repo_name)
            decisions.extend(parsed["decisions"])
            skipped += parsed["skipped"]
            warnings.extend(parsed["warnings"])
    elif isinstance(vulnerabilities, list):
        components = _components_by_ref(document.get("components"))
        for index, vulnerability in enumerate(vulnerabilities, start=1):
            parsed = _decisions_from_cyclonedx_vulnerability(
                vulnerability,
                index=index,
                default_repo_name=repo_name,
                components=components,
            )
            decisions.extend(parsed["decisions"])
            skipped += parsed["skipped"]
            warnings.extend(parsed["warnings"])
    else:
        warnings.append("No supported VEX statements were found. Expected OpenVEX-like statements or CycloneDX-like vulnerabilities.")

    return {
        "decisions": decisions,
        "skipped": skipped,
        "warnings": _dedupe(warnings),
    }


def vex_statement_count(document: dict[str, Any]) -> int:
    statements = document.get("statements")
    if isinstance(statements, list):
        return len(statements)
    vulnerabilities = document.get("vulnerabilities")
    if isinstance(vulnerabilities, list):
        return len(vulnerabilities)
    return 0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_exportable_decision(decision: dict[str, Any]) -> bool:
    if decision.get("status") not in EXPORT_DECISION_STATUSES:
        return False
    if decision.get("vex_status") not in EXPORT_VEX_STATUSES:
        return False
    return bool(decision.get("vulnerability_id") and decision.get("package_name"))


def _statement_from_decision(decision: dict[str, Any]) -> dict[str, Any]:
    product_id = str(
        decision.get("package_url")
        or _package_url_from_parts(
            ecosystem=decision.get("package_ecosystem"),
            name=decision.get("package_name"),
            version=decision.get("package_version"),
        )
        or decision.get("component_package_key")
        or decision.get("package_name")
    )
    reason = str(decision.get("vex_justification") or decision.get("note") or _default_reason(decision))
    timestamp = str(decision.get("updated_at") or decision.get("created_at") or utc_now())
    metadata = {
        "repo_name": decision.get("repo_name"),
        "case_id": decision.get("case_id"),
        "decision_status": decision.get("status"),
        "package_name": decision.get("package_name"),
        "package_version": decision.get("package_version"),
        "package_ecosystem": decision.get("package_ecosystem"),
        "package_url": decision.get("package_url"),
        "component_package_key": decision.get("component_package_key"),
        "fixed_version": decision.get("fixed_version"),
        "updated_at": decision.get("updated_at"),
    }
    return {
        "vulnerability": {"name": decision["vulnerability_id"]},
        "products": [{"@id": product_id}],
        "status": decision["vex_status"],
        "impact_statement": reason,
        "timestamp": timestamp,
        "metadata": {key: value for key, value in metadata.items() if value},
    }


def _decisions_from_openvex_statement(statement: Any, *, index: int, default_repo_name: str | None) -> dict[str, Any]:
    if not isinstance(statement, dict):
        return _parse_result(skip=f"statement {index}: ignored because it is not an object.")

    metadata = _object(statement.get("metadata"))
    vulnerability_id = _vulnerability_name(statement.get("vulnerability")) or _text(statement.get("vulnerability_id"))
    vex_status = _normalize_import_vex_status(statement.get("status"))
    if not vex_status or vex_status not in VEX_STATUSES:
        return _parse_result(skip=f"statement {index}: unsupported VEX status {statement.get('status')!r}.")
    if not vulnerability_id:
        return _parse_result(skip=f"statement {index}: missing vulnerability name.")

    products = statement.get("products")
    if not isinstance(products, list) or not products:
        products = [metadata]

    imported: list[dict[str, Any]] = []
    warnings: list[str] = []
    skipped = 0
    for product_index, product in enumerate(products, start=1):
        product_data = _product_identity(product)
        decision = _decision_from_identity(
            index=f"statement {index}, product {product_index}",
            vulnerability_id=vulnerability_id,
            vex_status=vex_status,
            reason=_reason_from_statement(statement),
            default_repo_name=default_repo_name,
            metadata=metadata | product_data,
        )
        if decision["decision"]:
            imported.append(decision["decision"])
        else:
            skipped += 1
            warnings.append(decision["warning"])

    return {"decisions": imported, "skipped": skipped, "warnings": warnings}


def _decisions_from_cyclonedx_vulnerability(
    vulnerability: Any,
    *,
    index: int,
    default_repo_name: str | None,
    components: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(vulnerability, dict):
        return _parse_result(skip=f"vulnerability {index}: ignored because it is not an object.")

    properties = _properties(vulnerability)
    analysis = _object(vulnerability.get("analysis"))
    vulnerability_id = _text(vulnerability.get("id") or vulnerability.get("bom-ref") or properties.get("vulnerability_id"))
    vex_status = _normalize_import_vex_status(analysis.get("state") or vulnerability.get("status") or properties.get("vex_status"))
    if not vex_status or vex_status not in VEX_STATUSES:
        return _parse_result(skip=f"vulnerability {index}: unsupported VEX status {(analysis.get('state') or vulnerability.get('status'))!r}.")
    if not vulnerability_id:
        return _parse_result(skip=f"vulnerability {index}: missing vulnerability id.")

    affects = vulnerability.get("affects")
    if not isinstance(affects, list) or not affects:
        affects = [properties]

    imported: list[dict[str, Any]] = []
    warnings: list[str] = []
    skipped = 0
    for affect_index, affect in enumerate(affects, start=1):
        affect_data = _object(affect)
        ref = _text(affect_data.get("ref") or affect_data.get("@id") or affect_data.get("purl") or affect_data.get("package_url"))
        component = components.get(ref or "") if ref else None
        identity = _properties(affect_data) | _product_identity(component or {}) | _product_identity(affect_data)
        if ref and ref.startswith("pkg:"):
            identity.setdefault("package_url", ref)
        if ref and not identity.get("package_url") and component and _text(component.get("purl")):
            identity["package_url"] = _text(component.get("purl"))
        decision = _decision_from_identity(
            index=f"vulnerability {index}, affect {affect_index}",
            vulnerability_id=vulnerability_id,
            vex_status=vex_status,
            reason=_text(analysis.get("detail") or analysis.get("justification") or properties.get("vex_justification") or properties.get("reason")),
            default_repo_name=default_repo_name,
            metadata=properties | identity,
        )
        if decision["decision"]:
            imported.append(decision["decision"])
        else:
            skipped += 1
            warnings.append(decision["warning"])

    return {"decisions": imported, "skipped": skipped, "warnings": warnings}


def _decision_from_identity(
    *,
    index: str,
    vulnerability_id: str,
    vex_status: str,
    reason: str | None,
    default_repo_name: str | None,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    package_url = _text(metadata.get("package_url") or metadata.get("purl"))
    package_name = _text(metadata.get("package_name") or metadata.get("name")) or _package_name_from_purl(package_url)
    package_version = _text(metadata.get("package_version") or metadata.get("version")) or _package_version_from_purl(package_url)
    package_ecosystem = _text(metadata.get("package_ecosystem") or metadata.get("ecosystem") or metadata.get("type")) or _ecosystem_from_purl(package_url)
    repo_name = _text(metadata.get("repo_name") or metadata.get("repo") or default_repo_name)
    decision_status = VEX_STATUS_TO_DECISION_STATUS.get(vex_status)
    if not decision_status:
        return {"decision": None, "warning": f"{index}: unsupported VEX status {vex_status!r}."}
    if not repo_name:
        return {"decision": None, "warning": f"{index}: missing repository. Re-run import with --repo or include metadata.repo_name."}
    if not package_name:
        return {"decision": None, "warning": f"{index}: missing package name or package URL."}
    if decision_status in EXPORT_DECISION_STATUSES and not reason:
        return {"decision": None, "warning": f"{index}: suppressing decisions need a reason or impact_statement."}

    component_package_key = _text(metadata.get("component_package_key"))
    if not component_package_key and package_url:
        component_package_key = f"purl|{_package_url_without_version(package_url).casefold()}"

    return {
        "decision": {
            "case_id": _text(metadata.get("case_id")) or _generated_case_id(repo_name, vulnerability_id, package_name, package_ecosystem, package_url),
            "repo_name": repo_name,
            "status": decision_status,
            "note": reason,
            "vex_status": vex_status,
            "vex_justification": reason,
            "vulnerability_id": vulnerability_id.upper(),
            "package_name": package_name.casefold(),
            "package_version": package_version,
            "package_ecosystem": package_ecosystem.casefold() if package_ecosystem else None,
            "package_url": package_url,
            "component_package_key": component_package_key,
            "fixed_version": _text(metadata.get("fixed_version")),
        },
        "warning": "",
    }


def _parse_result(*, skip: str) -> dict[str, Any]:
    return {"decisions": [], "skipped": 1, "warnings": [skip]}


def _reason_from_statement(statement: dict[str, Any]) -> str | None:
    return _text(
        statement.get("impact_statement")
        or statement.get("action_statement")
        or statement.get("justification")
        or _object(statement.get("metadata")).get("vex_justification")
        or _object(statement.get("metadata")).get("reason")
    )


def _product_identity(product: Any) -> dict[str, Any]:
    if isinstance(product, str):
        product_id = product
        product = {}
    else:
        product = _object(product)
        product_id = _text(product.get("@id") or product.get("id") or product.get("ref") or product.get("bom-ref") or product.get("purl") or product.get("package_url"))
    identifiers = _object(product.get("identifiers"))
    package_url = _text(product.get("purl") or product.get("package_url") or identifiers.get("purl"))
    if not package_url and product_id and product_id.startswith("pkg:"):
        package_url = product_id
    return _without_empty(
        {
        "package_url": package_url,
        "package_name": _text(product.get("package_name") or product.get("name")) or _package_name_from_purl(package_url),
        "package_version": _text(product.get("package_version") or product.get("version")) or _package_version_from_purl(package_url),
        "package_ecosystem": _text(product.get("package_ecosystem") or product.get("ecosystem") or product.get("type")) or _ecosystem_from_purl(package_url),
        "component_package_key": _text(product.get("component_package_key")),
        }
    )


def _components_by_ref(components: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(components, list):
        return {}
    refs: dict[str, dict[str, Any]] = {}
    for component in components:
        if not isinstance(component, dict):
            continue
        for key in ("bom-ref", "@id", "ref", "purl", "package_url"):
            value = _text(component.get(key))
            if value:
                refs[value] = component
    return refs


def _properties(item: dict[str, Any]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    raw_properties = item.get("properties")
    if not isinstance(raw_properties, list):
        return properties
    for prop in raw_properties:
        if not isinstance(prop, dict):
            continue
        name = _text(prop.get("name"))
        value = _text(prop.get("value"))
        if not name or value is None:
            continue
        clean_name = name.removeprefix("security-observatory:").removeprefix("security_observatory:")
        properties[clean_name] = value
    return properties


def _vulnerability_name(value: Any) -> str | None:
    if isinstance(value, str):
        return _text(value)
    if isinstance(value, dict):
        return _text(value.get("name") or value.get("id"))
    return None


def _package_url_from_parts(*, ecosystem: Any, name: Any, version: Any) -> str | None:
    ecosystem_text = _text(ecosystem)
    name_text = _text(name)
    if not ecosystem_text or not name_text:
        return None
    version_text = _text(version)
    return f"pkg:{ecosystem_text}/{name_text}@{version_text}" if version_text else f"pkg:{ecosystem_text}/{name_text}"


def _package_name_from_purl(package_url: str | None) -> str | None:
    if not package_url or not package_url.startswith("pkg:") or "/" not in package_url:
        return None
    body = package_url[4:].split("/", 1)[1].split("?", 1)[0].split("#", 1)[0]
    if "@" in body:
        head, tail = body.rsplit("@", 1)
        body = body if "/" in tail else head
    return unquote(body).casefold() or None


def _package_version_from_purl(package_url: str | None) -> str | None:
    if not package_url or not package_url.startswith("pkg:") or "@" not in package_url:
        return None
    body = package_url[4:].split("/", 1)[1].split("?", 1)[0].split("#", 1)[0]
    if "@" not in body:
        return None
    _head, tail = body.rsplit("@", 1)
    return None if "/" in tail else unquote(tail) or None


def _ecosystem_from_purl(package_url: str | None) -> str | None:
    if not package_url or not package_url.startswith("pkg:"):
        return None
    return package_url[4:].split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].casefold() or None


def _package_url_without_version(package_url: str) -> str:
    base = package_url.split("?", 1)[0].split("#", 1)[0]
    if "@" not in base:
        return base
    head, tail = base.rsplit("@", 1)
    return head if "/" not in tail else base


def _default_reason(decision: dict[str, Any]) -> str:
    if decision.get("status") == "false_positive":
        return "Marked as not affected in Security Observatory."
    if decision.get("status") == "accepted_risk":
        return "Risk accepted in Security Observatory."
    return "Recorded in Security Observatory."


def _normalize_import_vex_status(value: Any) -> str | None:
    normalized = normalize_vex_status(value)
    if normalized in VEX_STATUSES:
        return normalized
    text = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    return IMPORT_STATUS_ALIASES.get(text)


def _generated_case_id(repo_name: str, vulnerability_id: str, package_name: str, package_ecosystem: str | None, package_url: str | None) -> str:
    identity = "|".join([repo_name, vulnerability_id.upper(), package_name.casefold(), package_ecosystem or "", package_url or ""])
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"vex:{digest}"


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dedupe(items: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _without_empty(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None and value != ""}
