from src.ResearchOS.pipeline_objects.pipeline_object import PipelineObject
from src.ResearchOS.action import Action

class Logsheet(PipelineObject):

    prefix = "LG"
    
    def new(name: str) -> "Logsheet":
        action = Action(name = "New Logsheet" + name)
        lg = Logsheet(name = name)
        action.close()
        return lg