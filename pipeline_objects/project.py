from abc import abstractmethod
from typing import Any

from research_object import ResearchObject
from pipeline_objects.pipeline_object import PipelineObject
from pipeline_objects.analysis import Analysis
from action import Action

class Project(PipelineObject):

    prefix = "PJ"    

    @abstractmethod
    def new(name: str):
        pj = Project(name = name)
        return pj
    
    @abstractmethod
    def load(id: str) -> "Project":
        cls = Project
        ResearchObject.load(id = id, cls = cls)

    @abstractmethod
    def new_current(name: str):
        action = Action.new(name = "Init")
        pj = Project.new(name = name)
        an = Analysis.new_current(name = pj.name + "_Default")
        pj.set_current_analysis(an.id)
        action.close()

    def set_current_analysis(self, id: str):
        """Set an analysis as the current one for the project."""
        self.current_analysis_id = id

if __name__=="__main__":
    pj = Project.new_current(name = "Test")
    print(pj)