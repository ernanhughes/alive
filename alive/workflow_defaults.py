"""Current runtime defaults, separate from the preserved P1 experimental schema."""

from alive.cognitive_schema import CognitiveConfiguration


class RuntimeCognitiveConfiguration(CognitiveConfiguration):
    use_critic: bool = False
