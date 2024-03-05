"""The base class for all data objects. Data objects are the ones not in the digraph, and represent some form of data storage.""" 
from typing import Any, TYPE_CHECKING
import pickle

if TYPE_CHECKING:
    from ResearchOS.variable import Variable

from ResearchOS.research_object import ResearchObject
from ResearchOS.research_object_handler import ResearchObjectHandler
from ResearchOS.default_attrs import DefaultAttrs
from ResearchOS.action import Action
from ResearchOS.sql.sql_runner import sql_order_result

all_default_attrs = {}

computer_specific_attr_names = []

class DataObject(ResearchObject):
    """The parent class for all data objects. Data objects represent some form of data storage, and approximately map to statistical factors."""    

    def __delattr__(self, name: str, action: Action = None) -> None:
        """Delete an attribute. If it's a builtin attribute, don't delete it.
        If it's a VR, make sure it's "deleted" from the database."""
        default_attrs = DefaultAttrs(self).default_attrs
        if name in default_attrs:
            raise AttributeError("Cannot delete a builtin attribute.")
        if name not in self.__dict__:
            raise AttributeError("No such attribute.")
        if action is None:
            action = Action(name = "delete_attribute")
        vr_id = self.__dict__[name].id        
        params = (action.id, self.id, vr_id)
        if action is None:
            action = Action(name = "delete_attribute")
        action.add_sql_query(self.id, "vr_to_dobj_insert_inactive", params)
        action.execute()
        del self.__dict__[name]

    def load_vr_value(self, vr: "Variable", action: Action) -> Any:
        """Load the value of a VR from the database for this data object.

        Args:
            vr (Variable): ResearchOS Variable object to load the value of.
            action (Action): The Action that this is part of.

        Returns:
            Any: The value of the VR for this data object.
        """
        # 1. Check that the data object & VR are currently associated. If not, throw an error.
        sqlquery_raw = "SELECT action_id FROM vr_dataobjects WHERE dataobject_id = ? AND vr_id = ? AND is_active = 1"
        sqlquery = sql_order_result(action, sqlquery_raw, ["dataobject_id", "vr_id"], single = True, user = True, computer = False)
        params = (self.id, vr.id)
        cursor = action.conn.cursor()
        action_ids = cursor.execute(sqlquery, params).fetchall()
        if len(action_ids) == 0:
            raise ValueError(f"The VR {vr.name} is not currently associated with the data object {self.id}.")
        # 2. Load the data hash from the database.
        sqlquery_raw = "SELECT data_blob_hash FROM data_values WHERE dataobject_id = ? AND vr_id = ?"
        sqlquery = sql_order_result(action, sqlquery_raw, ["dataobject_id", "vr_id"], single = True, user = True, computer = False)
        params = (self.id, vr.id)        
        data_hash = cursor.execute(sqlquery, params).fetchone()[0]
        # 3. Get the value from the data_values table.        
        conn_data = ResearchObjectHandler.pool_data.get_connection()
        cursor_data = conn_data.cursor()
        sqlquery = "SELECT data_blob FROM data_values_blob WHERE data_blob_hash = ?"        
        params = (data_hash,)
        value = cursor_data.execute(sqlquery, params).fetchone()[0]
        ResearchObjectHandler.pool_data.return_connection(conn_data)
        return pickle.loads(value)

    def load_dataobject_vrs(self, action: Action) -> None:
        """Load all current data values for this data object from the database."""
        # 1. Get all of the latest address_id & vr_id combinations (that have not been overwritten) for the current schema for the current database.
        # Get the schema_id.
        # TODO: Put the schema_id into the data_values table.
        # 1. Get all of the VRs for the current object.
        from ResearchOS.variable import Variable

        sqlquery_raw = "SELECT vr_id FROM vr_dataobjects WHERE dataobject_id = ? AND is_active = 1"
        sqlquery = sql_order_result(action, sqlquery_raw, ["dataobject_id", "vr_id"], single = True, user = True, computer = False)
        params = (self.id,)        
        cursor = action.conn.cursor()
        vr_ids = cursor.execute(sqlquery, params).fetchall()        
        vr_ids = [x[0] for x in vr_ids]
        for vr_id in vr_ids:
            vr = Variable(id = vr_id)
            self.__dict__[vr.name] = vr