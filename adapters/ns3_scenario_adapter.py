from models.scenario import ScenarioModel


class Ns3ScenarioAdapter:
    def export(self, scenario: ScenarioModel) -> None:
        raise NotImplementedError("ns-3 export is reserved for a later phase.")
