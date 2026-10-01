"""The only tool the AI Agent needs for provider information.

`search_providers` reads the two local JSON files that act as the mock
database and returns *verified* records. Nothing else in the application is
allowed to answer "which doctors / hospitals do you have?".
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from settings import DATA_DIR

ProviderType = Literal["doctor", "hospital"]

FILES: dict[ProviderType, str] = {
    "doctor": "doctors.json",
    "hospital": "hospitals.json",
}


class MockDataError(RuntimeError):
    """Raised when the mock JSON files are missing or malformed."""


class Doctor(BaseModel):
    id: str
    name: str
    name_ar: str
    specialty: str
    city: str
    hospital_id: str
    languages: list[str]


class Hospital(BaseModel):
    id: str
    name: str
    name_ar: str
    city: str
    address: str
    specialties: list[str]
    emergency_available: bool
    languages: list[str]


# Small alias table so natural Agent phrasing ("cardiologist", "heart doctor")
# still matches the fixed vocabulary of the mock data.
_ALIASES = {
    "cardio": "cardiology",
    "cardiologist": "cardiology",
    "cardiac": "cardiology",
    "heart": "cardiology",
    "orthopaedic": "orthopedic",
    "orthopaedics": "orthopedic",
    "orthopedics": "orthopedic",
    "orthopedist": "orthopedic",
    "child": "pediatrics",
    "children": "pediatrics",
    "pediatrician": "pediatrics",
    "skin": "dermatology",
    "dermatologist": "dermatology",
    "brain": "neurology",
    "neurologist": "neurology",
    "er": "emergency",
    "accident": "emergency",
    "en": "english",
    "eng": "english",
    "ar": "arabic",
    "ur": "urdu",
}

# Words that carry no filtering meaning and would break exact matching.
_GENERIC_TOKENS = {
    "doctor",
    "doctors",
    "specialist",
    "specialists",
    "surgeon",
    "clinic",
    "centre",
    "center",
    "hospital",
    "hospitals",
    "department",
    "medicine",
    "in",
    "near",
    "city",
}


def _tokens(text: str) -> list[str]:
    cleaned = re.sub(r"[^a-z\u0600-\u06FF ]+", " ", text.lower())
    out: list[str] = []
    for token in cleaned.split():
        if token in _GENERIC_TOKENS:
            continue
        out.append(_ALIASES.get(token, token))
    return out


def canon(text: str) -> str:
    """Canonical, comparable form of a specialty / city / language string."""
    return " ".join(_tokens(text))


def _matches(query: str, candidates: list[str]) -> bool:
    wanted = canon(query)
    if not wanted:
        return True  # no filter requested
    for candidate in candidates:
        value = canon(candidate)
        if not value:
            continue
        if wanted == value or wanted in value or value in wanted:
            return True
    return False


class ProviderRepository:
    """Loads and searches the local JSON mock database."""

    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self._data_dir = data_dir
        self.doctors = _load_doctors(data_dir / FILES["doctor"])
        self.hospitals = _load_hospitals(data_dir / FILES["hospital"])
        self._hospitals_by_id = {hospital.id: hospital for hospital in self.hospitals}

    # -- lookups ---------------------------------------------------------
    def known_names(self) -> list[str]:
        """Every doctor / hospital name that legitimately exists in the data."""
        names: list[str] = []
        for doctor in self.doctors:
            names.extend([doctor.name, doctor.name_ar])
        for hospital in self.hospitals:
            names.extend([hospital.name, hospital.name_ar])
        return names

    def facets(self) -> dict[str, list[str]]:
        """Exact filter values available in the mock data (given to the Agent)."""
        return {
            "doctors": {
                "specialties": sorted({doctor.specialty for doctor in self.doctors}),
                "cities": sorted({doctor.city for doctor in self.doctors}),
                "languages": sorted({lang for doctor in self.doctors for lang in doctor.languages}),
            },
            "hospitals": {
                "specialties": sorted({s for hospital in self.hospitals for s in hospital.specialties}),
                "cities": sorted({hospital.city for hospital in self.hospitals}),
                "languages": sorted({lang for hospital in self.hospitals for lang in hospital.languages}),
            },
        }

    # -- search ----------------------------------------------------------
    def search(
        self,
        provider_type: ProviderType,
        specialty: str | None = None,
        city: str | None = None,
        language: str | None = None,
    ) -> list[dict[str, Any]]:
        if provider_type == "doctor":
            return self._search_doctors(specialty, city, language)
        if provider_type == "hospital":
            return self._search_hospitals(specialty, city, language)
        raise ValueError(f"unsupported provider_type: {provider_type!r}")

    def _search_doctors(
        self, specialty: str | None, city: str | None, language: str | None
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for doctor in self.doctors:
            if not _matches(specialty or "", [doctor.specialty]):
                continue
            if not _matches(city or "", [doctor.city]):
                continue
            if not _matches(language or "", doctor.languages):
                continue
            hospital = self._hospitals_by_id.get(doctor.hospital_id)
            results.append(
                {
                    "type": "doctor",
                    "id": doctor.id,
                    "name": doctor.name,
                    "name_ar": doctor.name_ar,
                    "city": doctor.city,
                    "specialties": [doctor.specialty],
                    "languages": doctor.languages,
                    "hospital": hospital.name if hospital else None,
                    "hospital_address": hospital.address if hospital else None,
                    "emergency_available": hospital.emergency_available if hospital else None,
                }
            )
        return results

    def _search_hospitals(
        self, specialty: str | None, city: str | None, language: str | None
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for hospital in self.hospitals:
            if not _matches(specialty or "", hospital.specialties):
                continue
            if not _matches(city or "", [hospital.city]):
                continue
            if not _matches(language or "", hospital.languages):
                continue
            results.append(
                {
                    "type": "hospital",
                    "id": hospital.id,
                    "name": hospital.name,
                    "name_ar": hospital.name_ar,
                    "city": hospital.city,
                    "specialties": hospital.specialties,
                    "languages": hospital.languages,
                    "hospital": None,
                    "hospital_address": hospital.address,
                    "emergency_available": hospital.emergency_available,
                }
            )
        return results


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise MockDataError(f"missing mock data file: {path.name}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise MockDataError(f"invalid JSON in {path.name}: line {exc.lineno}") from exc


def _load_doctors(path: Path) -> list[Doctor]:
    raw = _read_json(path)
    if not isinstance(raw, list):
        raise MockDataError(f"{path.name} must contain a JSON array")
    try:
        doctors = [Doctor(**item) for item in raw]
    except Exception as exc:
        raise MockDataError(f"invalid doctor record in {path.name}") from exc
    if len({doctor.id for doctor in doctors}) != len(doctors):
        raise MockDataError("duplicate doctor ids")
    return doctors


def _load_hospitals(path: Path) -> list[Hospital]:
    raw = _read_json(path)
    if not isinstance(raw, list):
        raise MockDataError(f"{path.name} must contain a JSON array")
    try:
        hospitals = [Hospital(**item) for item in raw]
    except Exception as exc:
        raise MockDataError(f"invalid hospital record in {path.name}") from exc
    if len({hospital.id for hospital in hospitals}) != len(hospitals):
        raise MockDataError("duplicate hospital ids")
    return hospitals


@lru_cache(maxsize=1)
def get_repository() -> ProviderRepository:
    """Cached repository (JSON files are read once per process)."""
    return ProviderRepository()


# --- Tool definitions (OpenAI-compatible function calling schema) ----------

SEARCH_PROVIDERS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_providers",
        "description": (
            "Search the HealTrip demo provider database (5 fictional doctors and "
            "5 fictional hospitals). This is the ONLY source of doctor/hospital "
            "information. Never answer with a doctor, hospital, address, language "
            "or emergency availability that is not returned by this tool."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "provider_type": {
                    "type": "string",
                    "enum": ["doctor", "hospital"],
                    "description": "Search doctors.json or hospitals.json.",
                },
                "specialty": {
                    "type": "string",
                    "description": "e.g. 'Cardiology'. Optional.",
                },
                "city": {"type": "string", "description": "e.g. 'Riyadh'. Optional."},
                "language": {
                    "type": "string",
                    "description": "e.g. 'Arabic' or 'English'. Optional.",
                },
            },
            "required": ["provider_type"],
        },
    },
}

LIST_PROVIDER_FILTERS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "list_provider_filters",
        "description": (
            "Return the exact specialty, city and language values that exist in "
            "the HealTrip demo provider database. Use it before searching so the "
            "filters match the demo data."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}