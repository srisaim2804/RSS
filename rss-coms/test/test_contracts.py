from coms.contracts import (
    UserPersona, CampaignSpec, KeywordBid, BidControls,
    SlotObservation, ObservationPage, new_correlation_id,
)


def test_persona_defaults():
    u = UserPersona("U1", queries=("wireless mouse",))
    assert u.segment == "general" and u.observed.device_type == "mobile"
    assert u.queries == ("wireless mouse",)


def test_campaign_spec_frozen():
    spec = CampaignSpec("c1", "s1", ("P1",), (KeywordBid("mouse", 1.0),))
    assert spec.target_segments == ("general",)


def test_observation_page_splits():
    page = ObservationPage("q", (
        SlotObservation(0, "ad", "P1", "t", 1.0, 4.0, "Acme", 0.9, is_sponsored=True),
        SlotObservation(1, "organic", "P2", "t2", 2.0, 4.5, "Volt", 0.8)))
    assert len(page.ad_slots) == 1 and len(page.organic_slots) == 1


def test_correlation_ids_unique_monotonic():
    a, b = new_correlation_id(), new_correlation_id()
    assert a != b and a < b
