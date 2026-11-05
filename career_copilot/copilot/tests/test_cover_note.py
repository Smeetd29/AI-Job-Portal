from unittest.mock import MagicMock, patch
import pytest
import anthropic
from copilot.services.cover_note import (
    generate_cover_note,
    validate_note,
    CoverNoteError,
    SYSTEM_PROMPT,
)
from .factories import CandidateProfileFactory, JobFactory


@pytest.fixture
def sample_data(db):
    profile = CandidateProfileFactory(
        full_name="Jane Doe",
        headline="Staff Platform Engineer",
        resume_text="Jane Doe. 8 years architecting distributed Kubernetes and Python clusters.",
    )
    job = JobFactory(
        title="Senior Infrastructure Engineer",
        company="NexTech Global",
        description="Looking for an engineer to lead our Kubernetes and Python infrastructure.",
    )
    return profile, job


def test_validate_note():
    profile = CandidateProfileFactory.build()

    # Valid note
    valid = "Dear NexTech team, I was thrilled to see your opening for Senior Infrastructure Engineer. Alex Candidate"
    assert validate_note(valid, profile)

    # Brackets / placeholders rejected
    assert not validate_note("Dear [Company] team, I am applying for [Role].", profile)

    # Lorem ipsum rejected
    assert not validate_note("Lorem ipsum dolor sit amet, consectetur adipiscing elit.", profile)

    # Overly long note (> 1400 chars) rejected
    assert not validate_note("A" * 1401, profile)

    # Empty note rejected
    assert not validate_note("", profile)


def test_generate_cover_note_happy_path(sample_data, settings):
    profile, job = sample_data
    settings.ANTHROPIC_API_KEY = "sk-ant-test-key"
    settings.ANTHROPIC_MODEL = "claude-sonnet-5-5"

    mock_client = MagicMock()
    mock_resp = MagicMock()
    content_mock = MagicMock()
    content_mock.text = (
        "Dear NexTech Global team,\n\n"
        "I was excited to see your Senior Infrastructure Engineer opening. At TechCorp, I architected "
        "asynchronous distributed systems and led database optimizations that cut query latency by 40%. "
        "My deep background in Python, PostgreSQL, and scalable microservices aligns closely with the goals "
        "of your infrastructure group. I look forward to contributing to your engineering initiatives.\n\n"
        "Jane Doe"
    )
    mock_resp.content = [content_mock]
    mock_client.messages.create.return_value = mock_resp

    with patch("anthropic.Anthropic", return_value=mock_client):
        note, model = generate_cover_note(job, profile)

    assert model == "claude-sonnet-5-5"
    assert "NexTech Global" in note
    assert "Jane Doe" in note

    # Check the call arguments
    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-sonnet-5-5"
    assert call_kwargs["system"] == SYSTEM_PROMPT

    user_content = call_kwargs["messages"][0]["content"]
    assert "<job>" in user_content
    assert "<candidate>" in user_content
    assert "Senior Infrastructure Engineer" in user_content
    assert "NexTech Global" in user_content
    assert "Jane Doe" in user_content


def test_generate_cover_note_retry_on_invalid_output(sample_data, settings):
    profile, job = sample_data
    settings.ANTHROPIC_API_KEY = "sk-ant-test-key"

    mock_client = MagicMock()
    # First response contains placeholder [Company]
    resp_invalid = MagicMock()
    item_invalid = MagicMock()
    item_invalid.text = "Dear Hiring Manager at [Company], I want to apply."
    resp_invalid.content = [item_invalid]

    # Second response is valid
    resp_valid = MagicMock()
    item_valid = MagicMock()
    item_valid.text = "Dear NexTech Global, I am excited about the Senior Infrastructure Engineer role. Jane Doe"
    resp_valid.content = [item_valid]

    mock_client.messages.create.side_effect = [resp_invalid, resp_valid]

    with patch("anthropic.Anthropic", return_value=mock_client):
        note, model = generate_cover_note(job, profile)

    assert note == "Dear NexTech Global, I am excited about the Senior Infrastructure Engineer role. Jane Doe"
    assert mock_client.messages.create.call_count == 2


def test_generate_cover_note_raises_on_persistent_failure(sample_data, settings):
    profile, job = sample_data
    settings.ANTHROPIC_API_KEY = "sk-ant-test-key"

    mock_client = MagicMock()
    # Always returns placeholder
    resp_invalid = MagicMock()
    item_invalid = MagicMock()
    item_invalid.text = "Hello [Company], please hire me."
    resp_invalid.content = [item_invalid]
    mock_client.messages.create.return_value = resp_invalid

    with patch("anthropic.Anthropic", return_value=mock_client):
        with pytest.raises(CoverNoteError):
            generate_cover_note(job, profile)
