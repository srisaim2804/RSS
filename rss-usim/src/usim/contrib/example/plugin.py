"""Example contrib for rss-usim: a choice-model variant.

Registers under the `choice_model` family with a `contrib:` name. Copy `example/` to a
new folder and register your own. Select it in config: `choice_model = "contrib:noisy_funnel"`.
"""
from coms.infra import register

from usim.choice_model import IndependentFunnelChoiceModel


class NoisyFunnelChoiceModel(IndependentFunnelChoiceModel):
    """Same funnel, slightly steeper position decay (users skim less)."""

    def sample(self, user, page, knowledge, rng, position_decay: float = 0.7):
        return super().sample(user, page, knowledge, rng, position_decay * 0.9)


register("choice_model", "contrib:noisy_funnel", lambda cfg: NoisyFunnelChoiceModel())
