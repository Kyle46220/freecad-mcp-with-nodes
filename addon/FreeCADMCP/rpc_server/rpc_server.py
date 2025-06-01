import FreeCAD
import FreeCADGui
import ObjectsFem

import contextlib
import queue
import base64
import io
import os
import tempfile
import threading
from dataclasses import dataclass, field
from typing import Any
from xmlrpc.server import SimpleXMLRPCServer

from PySide import QtCore

from .parts_library import get_parts_list, insert_part_from_library
from .serialize import serialize_object

rpc_server_thread = None
rpc_server_instance = None

# GUI task queue
rpc_request_queue = queue.Queue()
rpc_response_queue = queue.Queue()


def process_gui_tasks():
    while not rpc_request_queue.empty():
        task = rpc_request_queue.get()
        res = task()
        if res is not None:
            rpc_response_queue.put(res)
    QtCore.QTimer.singleShot(500, process_gui_tasks)


@dataclass
class Object:
    name: str
    type: str | None = None
    analysis: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)


def set_object_property(
    doc: FreeCAD.Document, obj: FreeCAD.DocumentObject, properties: dict[str, Any]
):
    for prop, val in properties.items():
        try:
            if prop in obj.PropertiesList:
                if prop == "Placement" and isinstance(val, dict):
                    if "Base" in val:
                        pos = val["Base"]
                    elif "Position" in val:
                        pos = val["Position"]
                    else:
                        pos = {}
                    rot = val.get("Rotation", {})
                    placement = FreeCAD.Placement(
                        FreeCAD.Vector(
                            pos.get("x", 0),
                            pos.get("y", 0),
                            pos.get("z", 0),
                        ),
                        FreeCAD.Rotation(
                            FreeCAD.Vector(
                                rot.get("Axis", {}).get("x", 0),
                                rot.get("Axis", {}).get("y", 0),
                                rot.get("Axis", {}).get("z", 1),
                            ),
                            rot.get("Angle", 0),
                        ),
                    )
                    setattr(obj, prop, placement)

                elif isinstance(getattr(obj, prop), FreeCAD.Vector) and isinstance(
                    val, dict
                ):
                    vector = FreeCAD.Vector(
                        val.get("x", 0), val.get("y", 0), val.get("z", 0)
                    )
                    setattr(obj, prop, vector)

                elif prop in ["Base", "Tool", "Source", "Profile"] and isinstance(
                    val, str
                ):
                    ref_obj = doc.getObject(val)
                    if ref_obj:
                        setattr(obj, prop, ref_obj)
                    else:
                        raise ValueError(f"Referenced object '{val}' not found.")

                elif prop == "References" and isinstance(val, list):
                    refs = []
                    for ref_name, face in val:
                        ref_obj = doc.getObject(ref_name)
                        if ref_obj:
                            refs.append((ref_obj, face))
                        else:
                            raise ValueError(f"Referenced object '{ref_name}' not found.")
                    setattr(obj, prop, refs)

                else:
                    setattr(obj, prop, val)
            # ShapeColor is a property of the ViewObject
            elif prop == "ShapeColor" and isinstance(val, (list, tuple)):
                setattr(obj.ViewObject, prop, (float(val[0]), float(val[1]), float(val[2]), float(val[3])))

            elif prop == "ViewObject" and isinstance(val, dict):
                for k, v in val.items():
                    if k == "ShapeColor":
                        setattr(obj.ViewObject, k, (float(v[0]), float(v[1]), float(v[2]), float(v[3])))
                    else:
                        setattr(obj.ViewObject, k, v)

            else:
                setattr(obj, prop, val)

        except Exception as e:
            FreeCAD.Console.PrintError(f"Property '{prop}' assignment error: {e}\n")


class FreeCADRPC:
    """RPC server for FreeCAD"""

    def ping(self):
        return True

    def create_document(self, name="New_Document"):
        rpc_request_queue.put(lambda: self._create_document_gui(name))
        res = rpc_response_queue.get()
        if res is True:
            return {"success": True, "document_name": name}
        else:
            return {"success": False, "error": res}

    def create_object(self, doc_name, obj_data: dict[str, Any]):
        obj = Object(
            name=obj_data.get("Name", "New_Object"),
            type=obj_data["Type"],
            analysis=obj_data.get("Analysis", None),
            properties=obj_data.get("Properties", {}),
        )
        rpc_request_queue.put(lambda: self._create_object_gui(doc_name, obj))
        res = rpc_response_queue.get()
        if res is True:
            return {"success": True, "object_name": obj.name}
        else:
            return {"success": False, "error": res}

    def edit_object(self, doc_name: str, obj_name: str, properties: dict[str, Any]) -> dict[str, Any]:
        obj = Object(
            name=obj_name,
            properties=properties.get("Properties", {}),
        )
        rpc_request_queue.put(lambda: self._edit_object_gui(doc_name, obj))
        res = rpc_response_queue.get()
        if res is True:
            return {"success": True, "object_name": obj.name}
        else:
            return {"success": False, "error": res}

    def delete_object(self, doc_name: str, obj_name: str):
        rpc_request_queue.put(lambda: self._delete_object_gui(doc_name, obj_name))
        res = rpc_response_queue.get()
        if res is True:
            return {"success": True, "object_name": obj_name}
        else:
            return {"success": False, "error": res}

    def execute_code(self, code: str) -> dict[str, Any]:
        output_buffer = io.StringIO()
        def task():
            try:
                with contextlib.redirect_stdout(output_buffer):
                    exec(code, globals())
                FreeCAD.Console.PrintMessage("Python code executed successfully.\n")
                return True
            except Exception as e:
                FreeCAD.Console.PrintError(
                    f"Error executing Python code: {e}\n"
                )
                return f"Error executing Python code: {e}\n"

        rpc_request_queue.put(task)
        res = rpc_response_queue.get()
        if res is True:
            return {
                "success": True,
                "message": "Python code execution scheduled. \nOutput: " + output_buffer.getvalue()
            }
        else:
            return {"success": False, "error": res}

    def get_objects(self, doc_name):
        doc = FreeCAD.getDocument(doc_name)
        if doc:
            return [serialize_object(obj) for obj in doc.Objects]
        else:
            return []

    def get_object(self, doc_name, obj_name):
        doc = FreeCAD.getDocument(doc_name)
        if doc:
            return serialize_object(doc.getObject(obj_name))
        else:
            return None

    def insert_part_from_library(self, relative_path):
        rpc_request_queue.put(lambda: self._insert_part_from_library(relative_path))
        res = rpc_response_queue.get()
        if res is True:
            return {"success": True, "message": "Part inserted from library."}
        else:
            return {"success": False, "error": res}

    def list_documents(self):
        return list(FreeCAD.listDocuments().keys())

    def get_parts_list(self):
        return get_parts_list()

    def get_active_screenshot(self, view_name: str = "Isometric") -> str:
        """Get a screenshot of the active view.
        
        Returns a base64-encoded string of the screenshot or None if a screenshot
        cannot be captured (e.g., when in TechDraw or Spreadsheet view).
        """
        # First check if the active view supports screenshots
        def check_view_supports_screenshots():
            try:
                active_view = FreeCADGui.ActiveDocument.ActiveView
                if active_view is None:
                    FreeCAD.Console.PrintWarning("No active view available\n")
                    return False
                
                view_type = type(active_view).__name__
                has_save_image = hasattr(active_view, 'saveImage')
                FreeCAD.Console.PrintMessage(f"View type: {view_type}, Has saveImage: {has_save_image}\n")
                return has_save_image
            except Exception as e:
                FreeCAD.Console.PrintError(f"Error checking view capabilities: {e}\n")
                return False
                
        rpc_request_queue.put(check_view_supports_screenshots)
        supports_screenshots = rpc_response_queue.get()
        
        if not supports_screenshots:
            FreeCAD.Console.PrintWarning("Current view does not support screenshots\n")
            return None
            
        # If view supports screenshots, proceed with capture
        fd, tmp_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        rpc_request_queue.put(
            lambda: self._save_active_screenshot(tmp_path, view_name)
        )
        res = rpc_response_queue.get()
        if res is True:
            try:
                with open(tmp_path, "rb") as image_file:
                    image_bytes = image_file.read()
                    encoded = base64.b64encode(image_bytes).decode("utf-8")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            return encoded
        else:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            FreeCAD.Console.PrintWarning(f"Failed to capture screenshot: {res}\n")
            return None

    def get_nodes_workbench_screenshot(self) -> str:
        """Get a screenshot of the Nodes workbench interface.
        
        Returns a base64-encoded string of the screenshot or None if the Nodes
        workbench is not active or no node editor window is available.
        """
        def check_nodes_workbench_available():
            try:
                from PySide import QtWidgets, QtGui
                
                # Check if the Nodes workbench is loaded
                wb = FreeCADGui.activeWorkbench()
                if wb and hasattr(wb, 'MenuText') and 'Nodes' in wb.MenuText:
                    FreeCAD.Console.PrintMessage("Nodes workbench is active\n")
                else:
                    # Try to find nodes workbench even if not currently active
                    workbenches = FreeCADGui.listWorkbenches()
                    nodes_available = any('nodes' in wb.lower() for wb in workbenches.keys())
                    if not nodes_available:
                        FreeCAD.Console.PrintWarning("Nodes workbench is not available\n")
                        return False
                
                # Look for the node editor widget in the application
                app = QtWidgets.QApplication.instance()
                if not app:
                    FreeCAD.Console.PrintWarning("No QApplication instance found\n")
                    return False
                
                # Search for node editor windows/widgets
                for widget in app.allWidgets():
                    widget_class = widget.__class__.__name__
                    widget_module = widget.__class__.__module__ if hasattr(widget.__class__, '__module__') else ''
                    
                    # Look for FCN (FreeCAD Nodes) widgets specifically
                    if widget_class.startswith('FCN') and widget.isVisible():
                        FreeCAD.Console.PrintMessage(f"Found FCN widget: {widget_class} from {widget_module}\n")
                        return widget
                    
                    # Look for other node editor related widgets
                    if any(keyword in widget_class.lower() for keyword in ['node', 'graph', 'scene']):
                        if widget.isVisible() and any(keyword in widget_module.lower() for keyword in ['node', 'graph']):
                            FreeCAD.Console.PrintMessage(f"Found potential node editor widget: {widget_class} from {widget_module}\n")
                            return widget
                    
                    # Also check for main windows with node-related titles
                    if hasattr(widget, 'windowTitle') and widget.windowTitle():
                        title = widget.windowTitle().lower()
                        if any(keyword in title for keyword in ['node', 'nodes', 'graph', 'visual', 'scripting']) and widget.isVisible():
                            FreeCAD.Console.PrintMessage(f"Found node editor window: {widget.windowTitle()}\n")
                            return widget
                
                FreeCAD.Console.PrintWarning("No active node editor interface found\n")
                return False
                
            except Exception as e:
                FreeCAD.Console.PrintError(f"Error checking Nodes workbench: {e}\n")
                return False
        
        rpc_request_queue.put(check_nodes_workbench_available)
        nodes_widget = rpc_response_queue.get()
        
        if not nodes_widget:
            FreeCAD.Console.PrintWarning("Nodes workbench interface not available\n")
            return None
        
        # Create screenshots directory if it doesn't exist
        screenshots_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'screenshots', 'nodes')
        os.makedirs(screenshots_dir, exist_ok=True)
        
        # Create temporary file for screenshot
        fd, tmp_path = tempfile.mkstemp(suffix=".png", dir=screenshots_dir)
        os.close(fd)
        
        rpc_request_queue.put(
            lambda: self._save_nodes_workbench_screenshot(tmp_path, nodes_widget)
        )
        res = rpc_response_queue.get()
        
        if res is True:
            try:
                with open(tmp_path, "rb") as image_file:
                    image_bytes = image_file.read()
                    encoded = base64.b64encode(image_bytes).decode("utf-8")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            return encoded
        else:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            FreeCAD.Console.PrintWarning(f"Failed to capture nodes workbench screenshot: {res}\n")
            return None

    def nodes_create_node(self, node_type_op_code: str, title: str | None, x_pos: float, y_pos: float):
        rpc_request_queue.put(lambda: self._nodes_create_node_gui(node_type_op_code, title, x_pos, y_pos))
        res = rpc_response_queue.get()
        return res

    def _nodes_create_node_gui(self, node_type_op_code: str, title: str | None, x_pos: float, y_pos: float):
        FreeCAD.Console.PrintMessage(f"Attempting to create node: {node_type_op_code} at ({x_pos}, {y_pos}) with title '{title}'\n")
        try:
            # Check if Nodes workbench is active
            current_wb = FreeCADGui.activeWorkbench()
            if not hasattr(current_wb, "name") or "Nodes" not in current_wb.name():
                # Attempt to activate Nodes workbench if available
                workbenches = FreeCADGui.listWorkbenches()
                nodes_wb_key = next((key for key, wb in workbenches.items() if "Nodes" in wb.MenuText), None)
                if nodes_wb_key:
                    FreeCADGui.activateWorkbench(nodes_wb_key)
                    FreeCAD.Console.PrintMessage("Activated Nodes workbench.\n")
                else:
                    return {"success": False, "node_id": None, "title": None, "message": "Nodes workbench is not available."}

            # Get active document
            doc = FreeCAD.ActiveDocument
            if not doc:
                return {"success": False, "node_id": None, "title": None, "message": "No active document."}

            # Get Nodes editor/graph
            # This is a common way, but might need adjustment based on FCNodes API
            view = FreeCADGui.ActiveDocument.ActiveView
            if not hasattr(view, "getGraph"):
                 # Attempt to find the graph view provider if not directly on ActiveView
                graph_view_provider = None
                for vp in doc.ViewObjects:
                    if hasattr(vp, "ScriptObjectName") and vp.ScriptObjectName == "ViewProviderGraph": # Common name for graph view providers
                        graph_view_provider = vp
                        break
                if graph_view_provider and hasattr(graph_view_provider, "graph"): # Access graph if found
                     editor = graph_view_provider.graph
                else: # Fallback or error if no graph view provider found
                    return {"success": False, "node_id": None, "title": None, "message": "Nodes editor/graph not found or graph attribute missing."}
            else:
                editor = view.getGraph()

            if not editor:
                return {"success": False, "node_id": None, "title": None, "message": "Nodes editor/graph not found."}

            # Create node
            # The exact API call might vary. This is a plausible guess.
            # Example: node = editor.createNode("<class 'generators_solid_box.SolidBox'>", "MyBox", 100, 200)
            # The node_type_op_code is expected to be a string like "<class 'some.NodeClass'>"
            # We might need to evaluate this string to get the actual class, or the API handles it.
            # For now, assuming the API takes the string directly.

            # Import the node class dynamically
            # node_type_op_code is like "<class 'generators_arithmetic.Arithmetic'>"
            # We need to extract 'generators_arithmetic.Arithmetic'

            class_path_str = node_type_op_code.split("'")[1]
            module_name, class_name = class_path_str.rsplit('.', 1)

            # This is a potential security risk if node_type_op_code is not trusted.
            # However, in this context, it's assumed to be from a trusted source (the agent).
            mod = __import__(module_name, fromlist=[class_name])
            NodeClass = getattr(mod, class_name)

            if title:
                node = editor.createNode(NodeClass, name=title, pos=[x_pos, y_pos])
            else:
                node = editor.createNode(NodeClass, pos=[x_pos, y_pos])

            if not node:
                return {"success": False, "node_id": None, "title": None, "message": "Failed to create node using Nodes API."}

            # Retrieve node ID and title
            # These attribute names ('name', 'title' or 'label') are guesses and might need verification
            node_id = getattr(node, 'name', None) # 'name' is common for internal ID
            node_title = getattr(node, 'label', None) # 'label' or 'title' for display name
            if hasattr(node, 'name') and hasattr(node.name, 'text'): # some nodes might have a text attribute in name
                node_title = node.name.text()

            if node_title is None and hasattr(node, 'title'): # fallback to title attribute
                 node_title = node.title.text() if hasattr(node.title, 'text') else str(node.title)


            FreeCAD.Console.PrintMessage(f"Node created: ID='{node_id}', Title='{node_title}'\n")
            doc.recompute() # Important to update the document state

            return {"success": True, "node_id": node_id, "title": node_title, "message": "Node created successfully."}

        except Exception as e:
            FreeCAD.Console.PrintError(f"Error creating node: {e}\n")
            import traceback
            FreeCAD.Console.PrintError(traceback.format_exc())
            return {"success": False, "node_id": None, "title": None, "message": f"Error creating node: {str(e)}"}

    def _create_document_gui(self, name):
        doc = FreeCAD.newDocument(name)
        doc.recompute()
        FreeCAD.Console.PrintMessage(f"Document '{name}' created via RPC.\n")
        return True

    def _create_object_gui(self, doc_name, obj: Object):
        doc = FreeCAD.getDocument(doc_name)
        if doc:
            try:
                if obj.type == "Fem::FemMeshGmsh" and obj.analysis:
                    from femmesh.gmshtools import GmshTools
                    res = getattr(doc, obj.analysis).addObject(ObjectsFem.makeMeshGmsh(doc, obj.name))[0]
                    if "Part" in obj.properties:
                        target_obj = doc.getObject(obj.properties["Part"])
                        if target_obj:
                            res.Part = target_obj
                        else:
                            raise ValueError(f"Referenced object '{obj.properties['Part']}' not found.")
                        del obj.properties["Part"]
                    else:
                        raise ValueError("'Part' property not found in properties.")

                    for param, value in obj.properties.items():
                        if hasattr(res, param):
                            setattr(res, param, value)
                    doc.recompute()

                    gmsh_tools = GmshTools(res)
                    gmsh_tools.create_mesh()
                    FreeCAD.Console.PrintMessage(
                        f"FEM Mesh '{res.Name}' generated successfully in '{doc_name}'.\n"
                    )
                elif obj.type.startswith("Fem::"):
                    fem_make_methods = {
                        "MaterialCommon": ObjectsFem.makeMaterialSolid,
                        "AnalysisPython": ObjectsFem.makeAnalysis,
                    }
                    obj_type_short = obj.type.split("::")[1]
                    method_name = "make" + obj_type_short
                    make_method = fem_make_methods.get(obj_type_short, getattr(ObjectsFem, method_name, None))

                    if callable(make_method):
                        res = make_method(doc, obj.name)
                        set_object_property(doc, res, obj.properties)
                        FreeCAD.Console.PrintMessage(
                            f"FEM object '{res.Name}' created with '{method_name}'.\n"
                        )
                    else:
                        raise ValueError(f"No creation method '{method_name}' found in ObjectsFem.")
                    if obj.type != "Fem::AnalysisPython" and obj.analysis:
                        getattr(doc, obj.analysis).addObject(res)
                else:
                    res = doc.addObject(obj.type, obj.name)
                    set_object_property(doc, res, obj.properties)
                    FreeCAD.Console.PrintMessage(
                        f"{res.TypeId} '{res.Name}' added to '{doc_name}' via RPC.\n"
                    )
 
                doc.recompute()
                return True
            except Exception as e:
                return str(e)
        else:
            FreeCAD.Console.PrintError(f"Document '{doc_name}' not found.\n")
            return f"Document '{doc_name}' not found.\n"

    def _edit_object_gui(self, doc_name: str, obj: Object):
        doc = FreeCAD.getDocument(doc_name)
        if not doc:
            FreeCAD.Console.PrintError(f"Document '{doc_name}' not found.\n")
            return f"Document '{doc_name}' not found.\n"

        obj_ins = doc.getObject(obj.name)
        if not obj_ins:
            FreeCAD.Console.PrintError(f"Object '{obj.name}' not found in document '{doc_name}'.\n")
            return f"Object '{obj.name}' not found in document '{doc_name}'.\n"

        try:
            # For Fem::ConstraintFixed
            if hasattr(obj_ins, "References") and "References" in obj.properties:
                refs = []
                for ref_name, face in obj.properties["References"]:
                    ref_obj = doc.getObject(ref_name)
                    if ref_obj:
                        refs.append((ref_obj, face))
                    else:
                        raise ValueError(f"Referenced object '{ref_name}' not found.")
                obj_ins.References = refs
                FreeCAD.Console.PrintMessage(
                    f"References updated for '{obj.name}' in '{doc_name}'.\n"
                )
                # delete References from properties
                del obj.properties["References"]
            set_object_property(doc, obj_ins, obj.properties)
            doc.recompute()
            FreeCAD.Console.PrintMessage(f"Object '{obj.name}' updated via RPC.\n")
            return True
        except Exception as e:
            return str(e)

    def _delete_object_gui(self, doc_name: str, obj_name: str):
        doc = FreeCAD.getDocument(doc_name)
        if not doc:
            FreeCAD.Console.PrintError(f"Document '{doc_name}' not found.\n")
            return f"Document '{doc_name}' not found.\n"

        try:
            doc.removeObject(obj_name)
            doc.recompute()
            FreeCAD.Console.PrintMessage(f"Object '{obj_name}' deleted via RPC.\n")
            return True
        except Exception as e:
            return str(e)

    def _insert_part_from_library(self, relative_path):
        try:
            insert_part_from_library(relative_path)
            return True
        except Exception as e:
            return str(e)

    def _save_active_screenshot(self, save_path: str, view_name: str = "Isometric"):
        try:
            view = FreeCADGui.ActiveDocument.ActiveView
            # Check if the view supports screenshots
            if not hasattr(view, 'saveImage'):
                return "Current view does not support screenshots"
                
            if view_name == "Isometric":
                view.viewIsometric()
            elif view_name == "Front":
                view.viewFront()
            elif view_name == "Top":
                view.viewTop()
            elif view_name == "Right":
                view.viewRight()
            elif view_name == "Back":
                view.viewBack()
            elif view_name == "Left":
                view.viewLeft()
            elif view_name == "Bottom":
                view.viewBottom()
            elif view_name == "Dimetric":
                view.viewDimetric()
            elif view_name == "Trimetric":
                view.viewTrimetric()
            else:
                raise ValueError(f"Invalid view name: {view_name}")
            view.fitAll()
            view.saveImage(save_path, 1)
            return True
        except Exception as e:
            return str(e)

    def _save_nodes_workbench_screenshot(self, save_path: str, nodes_widget):
        try:
            from PySide import QtWidgets, QtGui
            
            # Ensure the widget is valid and visible
            if not nodes_widget or not nodes_widget.isVisible():
                return "Node editor widget is not visible or invalid"
            
            # Capture screenshot of the node editor widget
            pixmap = nodes_widget.grab()
            if pixmap.isNull():
                return "Failed to capture widget content"
            
            # Save the screenshot
            success = pixmap.save(save_path, "PNG")
            if not success:
                return "Failed to save screenshot to file"
            
            FreeCAD.Console.PrintMessage(f"Nodes workbench screenshot saved to: {save_path}\n")
            return True
            
        except Exception as e:
            return str(e)


def start_rpc_server(host="localhost", port=9875):
    global rpc_server_thread, rpc_server_instance

    if rpc_server_instance:
        return "RPC Server already running."

    rpc_server_instance = SimpleXMLRPCServer(
        (host, port), allow_none=True, logRequests=False
    )
    rpc_server_instance.register_instance(FreeCADRPC())

    def server_loop():
        FreeCAD.Console.PrintMessage(f"RPC Server started at {host}:{port}\n")
        rpc_server_instance.serve_forever()

    rpc_server_thread = threading.Thread(target=server_loop, daemon=True)
    rpc_server_thread.start()

    QtCore.QTimer.singleShot(500, process_gui_tasks)

    return f"RPC Server started at {host}:{port}."


def stop_rpc_server():
    global rpc_server_instance, rpc_server_thread

    if rpc_server_instance:
        rpc_server_instance.shutdown()
        rpc_server_thread.join()
        rpc_server_instance = None
        rpc_server_thread = None
        FreeCAD.Console.PrintMessage("RPC Server stopped.\n")
        return "RPC Server stopped."

    return "RPC Server was not running."


class StartRPCServerCommand:
    def GetResources(self):
        return {"MenuText": "Start RPC Server", "ToolTip": "Start RPC Server"}

    def Activated(self):
        msg = start_rpc_server()
        FreeCAD.Console.PrintMessage(msg + "\n")

    def IsActive(self):
        return True


class StopRPCServerCommand:
    def GetResources(self):
        return {"MenuText": "Stop RPC Server", "ToolTip": "Stop RPC Server"}

    def Activated(self):
        msg = stop_rpc_server()
        FreeCAD.Console.PrintMessage(msg + "\n")

    def IsActive(self):
        return True


FreeCADGui.addCommand("Start_RPC_Server", StartRPCServerCommand())
FreeCADGui.addCommand("Stop_RPC_Server", StopRPCServerCommand())