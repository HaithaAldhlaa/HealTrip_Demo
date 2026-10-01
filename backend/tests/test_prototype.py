"""Unit tests for the deterministic layers (mock search, safety, guard).

They do not call the LLM, so they run offline.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from guard import enforce_grounding, find_unverified_names  # noqa: E402
from safety import detect_language, is_emergency, mentions_symptom  # noqa: E402
from tools.search_providers import MockDataError, ProviderRepository  # noqa: E402


@pytest.fixture()
def repo() -> ProviderRepository:
    return ProviderRepository()


# --- mock database -------------------------------------------------------

def test_exactly_five_records_each(repo: ProviderRepository) -> None:
    assert len(repo.doctors) == 5
    assert len(repo.hospitals) == 5


def test_search_doctor_by_specialty_and_city(repo: ProviderRepository) -> None:
    results = repo.search("doctor", specialty="Cardiology", city="Riyadh")
    assert [item["name"] for item in results] == ["Dr. Ahmed Salem"]
    assert results[0]["hospital"] == "Al-Noor Demo Hospital"


def test_search_doctor_resolves_hospital_relationship(repo: ProviderRepository) -> None:
    results = repo.search("doctor", specialty="Neurology")
    assert results[0]["hospital"] == "Capital Demo Hospital"
    assert results[0]["hospital_address"] == "Al Malqa District"
    assert results[0]["emergency_available"] is True


def test_search_hospital(repo: ProviderRepository) -> None:
    results = repo.search("hospital", city="Jeddah", specialty="Emergency Medicine")
    assert [item["name"] for item in results] == ["Red Sea Demo Hospital"]
    assert results[0]["emergency_available"] is True


def test_search_with_natural_phrasing(repo: ProviderRepository) -> None:
    assert repo.search("doctor", specialty="cardiologist", city="riyadh saudi arabia")


def test_no_match_returns_empty(repo: ProviderRepository) -> None:
    assert repo.search("doctor", specialty="Dermatology", city="Riyadh") == []
    assert repo.search("hospital", specialty="Oncology") == []


def test_language_filter(repo: ProviderRepository) -> None:
    assert repo.search("doctor", specialty="Orthopedics", language="English")
    assert repo.search("doctor", specialty="Orthopedics", language="Arabic")
    assert repo.search("doctor", specialty="Cardiology", language="French") == []


# --- mock database errors -------------------------------------------------

def test_invalid_json_is_reported(tmp_path: Path) -> None:
    (tmp_path / "doctors.json").write_text("{ not json", encoding="utf-8")
    (tmp_path / "hospitals.json").write_text("[]", encoding="utf-8")
    with pytest.raises(MockDataError):
        ProviderRepository(tmp_path)


def test_missing_required_field_is_reported(tmp_path: Path) -> None:
    (tmp_path / "doctors.json").write_text(json.dumps([{"id": "d1"}]), encoding="utf-8")
    (tmp_path / "hospitals.json").write_text("[]", encoding="utf-8")
    with pytest.raises(MockDataError):
        ProviderRepository(tmp_path)


def test_missing_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(MockDataError):
        ProviderRepository(tmp_path)


# --- agent loop (LLM stubbed, no network) --------------------------------

def test_agent_loop_executes_tool_and_returns_verified_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tool call from the model is answered from the mock JSON, not invented."""
    import agent.agent as agent_module

    replies = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "search_providers",
                        "arguments": '{"provider_type": "doctor", "specialty": "Cardiology", "city": "Riyadh"}',
                    },
                }
            ],
        },
        {"role": "assistant", "content": "Dr. Ahmed Salem works at Al-Noor Demo Hospital."},
    ]
    captured: dict[str, object] = {}

    async def fake_chat_completion(messages, tools):
        captured["tools"] = tools
        captured["last_messages"] = messages
        return replies.pop(0)

    monkeypatch.setattr(agent_module, "chat_completion", fake_chat_completion)
    result = asyncio.run(
        agent_module.run_agent([], "I need a cardiologist in Riyadh.", "en", False, False, ProviderRepository())
    )

    assert result.grounded is True
    assert [p["name"] for p in result.providers] == ["Dr. Ahmed Salem"]
    assert result.providers[0]["hospital"] == "Al-Noor Demo Hospital"
    assert result.tools_used[0]["name"] == "search_providers"
    assert result.tools_used[0]["result_count"] == 1
    # The tool result handed back to the model is the only source of provider data.
    tool_message = captured["last_messages"][-1]
    assert json.loads(tool_message["content"])["match_count"] == 1


def test_agent_reports_no_match_honestly(monkeypatch: pytest.MonkeyPatch) -> None:
    import agent.agent as agent_module

    replies = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "search_providers",
                        "arguments": '{"provider_type": "doctor", "specialty": "Dermatology", "city": "Riyadh"}',
                    },
                }
            ],
        },
        {"role": "assistant", "content": "No matching provider in the demo data."},
    ]

    async def fake_chat_completion(messages, tools):
        return replies.pop(0)

    monkeypatch.setattr(agent_module, "chat_completion", fake_chat_completion)
    result = asyncio.run(
        agent_module.run_agent([], "Any dermatologist in Riyadh?", "en", False, False, ProviderRepository())
    )

    assert result.grounded is False
    assert result.providers == []
    assert result.tools_used[0]["result_count"] == 0


def test_agent_survives_bad_tool_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    import agent.agent as agent_module

    replies = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "search_providers", "arguments": '{"provider_type": "clinic"}'},
                }
            ],
        },
        {"role": "assistant", "content": "I can only search doctors or hospitals."},
    ]
    tool_payloads: list[dict] = []

    async def fake_chat_completion(messages, tools):
        if messages[-1]["role"] == "tool":
            tool_payloads.append(json.loads(messages[-1]["content"]))
        return replies.pop(0)

    monkeypatch.setattr(agent_module, "chat_completion", fake_chat_completion)
    result = asyncio.run(
        agent_module.run_agent([], "Find me a clinic", "en", False, False, ProviderRepository())
    )

    assert "error" in tool_payloads[0]
    assert result.providers == []


# --- safety --------------------------------------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "I have severe chest pain and cannot breathe",
        "My father fainted and is unconscious",
        "شعرت بألم شديد في الصدر ولا أستطيع التنفس",
    ],
)
def test_emergency_detection(text: str) -> None:
    assert is_emergency(text)


def test_ordinary_message_is_not_emergency() -> None:
    assert not is_emergency("I need a cardiologist in Riyadh")


def test_symptom_detection() -> None:
    assert mentions_symptom("I have chest pain and I'm not sure")
    assert not mentions_symptom("I need a cardiologist in Riyadh")


def test_language_detection() -> None:
    assert detect_language("أريد طبيب قلب في الرياض") == "ar"
    assert detect_language("I want a doctor") == "en"


# --- hallucination guard -------------------------------------------------

def test_guard_allows_real_providers(repo: ProviderRepository) -> None:
    reply = "Dr. Ahmed Salem works at Al-Noor Demo Hospital in Riyadh."
    assert find_unverified_names(reply, repo) == []
    assert enforce_grounding(reply, repo, "en")[0] == reply


def test_guard_blocks_invented_doctor(repo: ProviderRepository) -> None:
    reply, unverified = enforce_grounding("You should see Dr. Sarah Khan.", repo, "en")
    assert unverified
    assert "Sarah Khan" not in reply


def test_guard_blocks_invented_hospital(repo: ProviderRepository) -> None:
    _, unverified = enforce_grounding("Try King Faisal Demo Hospital in Riyadh.", repo, "en")
    assert unverified


def test_guard_ignores_arabic_words_ending_in_dal(repo: ProviderRepository) -> None:
    reply = "هل تشعر بألم شديد. اذهب إلى قسم الطوارئ المحلي (مثل 997 في السعودية)."
    assert find_unverified_names(reply, repo) == []


def test_guard_ignores_generic_arabic_facility_phrases(repo: ProviderRepository) -> None:
    reply = (
        "د. أحمد سالم طبيب قلب في الرياض. يُنصح بحجز موعد أو زيارة المستشفى إذا "
        "كان الأمر طارئًا، والحصول على 서비스를 في أقرب مركز طبي متاح."
    )
    assert find_unverified_names(reply, repo) == []


def test_guard_allows_non_breaking_hyphen_in_names(repo: ProviderRepository) -> None:
    reply = "He works at Al\u2011Noor Demo Hospital in Olaya District."
    assert find_unverified_names(reply, repo) == []


def test_guard_allows_arabic_name_from_data(repo: ProviderRepository) -> None:
    reply = "يمكنك مراجعة د. أحمد سالم في مستشفى النور التوضيحي بالرياض."
    assert find_unverified_names(reply, repo) == []


def test_guard_blocks_invented_arabic_hospital(repo: ProviderRepository) -> None:
    _, unverified = enforce_grounding("اذهب إلى مستشفى الملك فهد في الرياض.", repo, "ar")
    assert unverified