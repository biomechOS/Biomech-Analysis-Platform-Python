"""The abstract base class for all data objects. Data objects are the ones not in the digraph, and represent some form of data storage.""" 

import sqlite3, datetime

# from typing import Union, Type, Any
import weakref

from ResearchOS import ResearchObject

class DataObject(ResearchObject):
    """The abstract base class for all data objects. Data objects are the ones not in the digraph, and represent some form of data storage."""    


    