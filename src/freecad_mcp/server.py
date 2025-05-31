import json
import logging
import xmlrpc.client
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, Literal

from mcp.server.fastmcp import FastMCP, Context
from mcp.types import TextContent, ImageContent

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("FreeCADMCPserver")


_only_text_feedback = False


class FreeCADConnection:
    def __init__(self, host: str = "localhost", port: int = 9875):
        self.server = xmlrpc.client.ServerProxy(f"http://{host}:{port}", allow_none=True)

    def ping(self) -> bool:
        return self.server.ping()

    def create_document(self, name: str) -> dict[str, Any]:
        return self.server.create_document(name)

    def create_object(self, doc_name: str, obj_data: dict[str, Any]) -> dict[str, Any]:
        return self.server.create_object(doc_name, obj_data)

    def edit_object(self, doc_name: str, obj_name: str, obj_data: dict[str, Any]) -> dict[str, Any]:
        return self.server.edit_object(doc_name, obj_name, obj_data)

    def delete_object(self, doc_name: str, obj_name: str) -> dict[str, Any]:
        return self.server.delete_object(doc_name, obj_name)

    def insert_part_from_library(self, relative_path: str) -> dict[str, Any]:
        return self.server.insert_part_from_library(relative_path)

    def execute_code(self, code: str) -> dict[str, Any]:
        return self.server.execute_code(code)

    def get_active_screenshot(self, view_name: str = "Isometric") -> str | None:
        try:
            # Check if we're in a view that supports screenshots
            result = self.server.execute_code("""
import FreeCAD
import FreeCADGui

if FreeCAD.Gui.ActiveDocument and FreeCAD.Gui.ActiveDocument.ActiveView:
    view_type = type(FreeCAD.Gui.ActiveDocument.ActiveView).__name__
    
    # These view types don't support screenshots
    unsupported_views = ['SpreadsheetGui::SheetView', 'DrawingGui::DrawingView', 'TechDrawGui::MDIViewPage']
    
    if view_type in unsupported_views or not hasattr(FreeCAD.Gui.ActiveDocument.ActiveView, 'saveImage'):
        print("Current view does not support screenshots")
        False
    else:
        print(f"Current view supports screenshots: {view_type}")
        True
else:
    print("No active view")
    False
""")

            # If the view doesn't support screenshots, return None
            if not result.get("success", False) or "Current view does not support screenshots" in result.get("message", ""):
                logger.info("Screenshot unavailable in current view (likely Spreadsheet or TechDraw view)")
                return None

            # Otherwise, try to get the screenshot
            return self.server.get_active_screenshot(view_name)
        except Exception as e:
            # Log the error but return None instead of raising an exception
            logger.error(f"Error getting screenshot: {e}")
            return None

    def get_objects(self, doc_name: str) -> list[dict[str, Any]]:
        return self.server.get_objects(doc_name)

    def get_object(self, doc_name: str, obj_name: str) -> dict[str, Any]:
        return self.server.get_object(doc_name, obj_name)

    def get_parts_list(self) -> list[str]:
        return self.server.get_parts_list()

    def get_nodes_workbench_screenshot(self) -> str | None:
        """Get a screenshot of the Nodes workbench interface."""
        try:
            return self.server.get_nodes_workbench_screenshot()
        except Exception as e:
            logger.error(f"Error getting nodes workbench screenshot: {e}")
            return None


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    try:
        logger.info("FreeCADMCP server starting up")
        try:
            _ = get_freecad_connection()
            logger.info("Successfully connected to FreeCAD on startup")
        except Exception as e:
            logger.warning(f"Could not connect to FreeCAD on startup: {str(e)}")
            logger.warning(
                "Make sure the FreeCAD addon is running before using FreeCAD resources or tools"
            )
        yield {}
    finally:
        # Clean up the global connection on shutdown
        global _freecad_connection
        if _freecad_connection:
            logger.info("Disconnecting from FreeCAD on shutdown")
            _freecad_connection.disconnect()
            _freecad_connection = None
        logger.info("FreeCADMCP server shut down")


mcp = FastMCP(
    "FreeCADMCP",
    description="FreeCAD integration through the Model Context Protocol",
    lifespan=server_lifespan,
)


_freecad_connection: FreeCADConnection | None = None


def get_freecad_connection():
    """Get or create a persistent FreeCAD connection"""
    global _freecad_connection
    if _freecad_connection is None:
        _freecad_connection = FreeCADConnection(host="localhost", port=9875)
        if not _freecad_connection.ping():
            logger.error("Failed to ping FreeCAD")
            _freecad_connection = None
            raise Exception(
                "Failed to connect to FreeCAD. Make sure the FreeCAD addon is running."
            )
    return _freecad_connection


# Helper function to safely add screenshot to response
def add_screenshot_if_available(response, screenshot):
    """Safely add screenshot to response only if it's available"""
    if screenshot is not None and not _only_text_feedback:
        response.append(ImageContent(type="image", data=screenshot, mimeType="image/png"))
    elif not _only_text_feedback:
        # Add an informative message that will be seen by the AI model and user
        response.append(TextContent(
            type="text", 
            text="Note: Visual preview is unavailable in the current view type (such as TechDraw or Spreadsheet). "
                 "Switch to a 3D view to see visual feedback."
        ))
    return response


@mcp.tool()
def create_document(ctx: Context, name: str) -> list[TextContent]:
    """Create a new document in FreeCAD.

    Args:
        name: The name of the document to create.

    Returns:
        A message indicating the success or failure of the document creation.

    Examples:
        If you want to create a document named "MyDocument", you can use the following data.
        ```json
        {
            "name": "MyDocument"
        }
        ```
    """
    freecad = get_freecad_connection()
    try:
        res = freecad.create_document(name)
        if res["success"]:
            return [
                TextContent(type="text", text=f"Document '{res['document_name']}' created successfully")
            ]
        else:
            return [
                TextContent(type="text", text=f"Failed to create document: {res['error']}")
            ]
    except Exception as e:
        logger.error(f"Failed to create document: {str(e)}")
        return [
            TextContent(type="text", text=f"Failed to create document: {str(e)}")
        ]


@mcp.tool()
def create_object(
    ctx: Context,
    doc_name: str,
    obj_type: str,
    obj_name: str,
    analysis_name: str | None = None,
    obj_properties: dict[str, Any] = None,
) -> list[TextContent | ImageContent]:
    """Create a new object in FreeCAD.
    Object type is starts with "Part::" or "Draft::" or "PartDesign::" or "Fem::".

    Args:
        doc_name: The name of the document to create the object in.
        obj_type: The type of the object to create (e.g. 'Part::Box', 'Part::Cylinder', 'Draft::Circle', 'PartDesign::Body', etc.).
        obj_name: The name of the object to create.
        obj_properties: The properties of the object to create.

    Returns:
        A message indicating the success or failure of the object creation and a screenshot of the object.

    Examples:
        If you want to create a cylinder with a height of 30 and a radius of 10, you can use the following data.
        ```json
        {
            "doc_name": "MyCylinder",
            "obj_name": "Cylinder",
            "obj_type": "Part::Cylinder",
            "obj_properties": {
                "Height": 30,
                "Radius": 10,
                "Placement": {
                    "Base": {
                        "x": 10,
                        "y": 10,
                        "z": 0
                    },
                    "Rotation": {
                        "Axis": {
                            "x": 0,
                            "y": 0,
                            "z": 1
                        },
                        "Angle": 45
                    }
                },
                "ViewObject": {
                    "ShapeColor": [0.5, 0.5, 0.5, 1.0]
                }
            }
        }
        ```

        If you want to create a circle with a radius of 10, you can use the following data.
        ```json
        {
            "doc_name": "MyCircle",
            "obj_name": "Circle",
            "obj_type": "Draft::Circle",
        }
        ```

        If you want to create a FEM analysis, you can use the following data.
        ```json
        {
            "doc_name": "MyFEMAnalysis",
            "obj_name": "FemAnalysis",
            "obj_type": "Fem::AnalysisPython",
        }
        ```

        If you want to create a FEM constraint, you can use the following data.
        ```json
        {
            "doc_name": "MyFEMConstraint",
            "obj_name": "FemConstraint",
            "obj_type": "Fem::ConstraintFixed",
            "analysis_name": "MyFEMAnalysis",
            "obj_properties": {
                "References": [
                    {
                        "object_name": "MyObject",
                        "face": "Face1"
                    }
                ]
            }
        }
        ```

        If you want to create a FEM mechanical material, you can use the following data.
        ```json
        {
            "doc_name": "MyFEMAnalysis",
            "obj_name": "FemMechanicalMaterial",
            "obj_type": "Fem::MaterialCommon",
            "analysis_name": "MyFEMAnalysis",
            "obj_properties": {
                "Material": {
                    "Name": "MyMaterial",
                    "Density": "7900 kg/m^3",
                    "YoungModulus": "210 GPa",
                    "PoissonRatio": 0.3
                }
            }
        }
        ```

        If you want to create a FEM mesh, you can use the following data.
        The `Part` property is required.
        ```json
        {
            "doc_name": "MyFEMMesh",
            "obj_name": "FemMesh",
            "obj_type": "Fem::FemMeshGmsh",
            "analysis_name": "MyFEMAnalysis",
            "obj_properties": {
                "Part": "MyObject",
                "ElementSizeMax": 10,
                "ElementSizeMin": 0.1,
                "MeshAlgorithm": 2
            }
        }
        ```
    """
    freecad = get_freecad_connection()
    try:
        obj_data = {"Name": obj_name, "Type": obj_type, "Properties": obj_properties or {}, "Analysis": analysis_name}
        res = freecad.create_object(doc_name, obj_data)
        screenshot = freecad.get_active_screenshot()
        
        if res["success"]:
            response = [
                TextContent(type="text", text=f"Object '{res['object_name']}' created successfully"),
            ]
            return add_screenshot_if_available(response, screenshot)
        else:
            response = [
                TextContent(type="text", text=f"Failed to create object: {res['error']}"),
            ]
            return add_screenshot_if_available(response, screenshot)
    except Exception as e:
        logger.error(f"Failed to create object: {str(e)}")
        return [
            TextContent(type="text", text=f"Failed to create object: {str(e)}")
        ]


@mcp.tool()
def edit_object(
    ctx: Context, doc_name: str, obj_name: str, obj_properties: dict[str, Any]
) -> list[TextContent | ImageContent]:
    """Edit an object in FreeCAD.
    This tool is used when the `create_object` tool cannot handle the object creation.

    Args:
        doc_name: The name of the document to edit the object in.
        obj_name: The name of the object to edit.
        obj_properties: The properties of the object to edit.

    Returns:
        A message indicating the success or failure of the object editing and a screenshot of the object.
    """
    freecad = get_freecad_connection()
    try:
        res = freecad.edit_object(doc_name, obj_name, obj_properties)
        screenshot = freecad.get_active_screenshot()
        
        if res["success"]:
            response = [
                TextContent(type="text", text=f"Object '{res['object_name']}' edited successfully"),
            ]
            return add_screenshot_if_available(response, screenshot)
        else:
            response = [
                TextContent(type="text", text=f"Failed to edit object: {res['error']}"),
            ]
            return add_screenshot_if_available(response, screenshot)
    except Exception as e:
        logger.error(f"Failed to edit object: {str(e)}")
        return [
            TextContent(type="text", text=f"Failed to edit object: {str(e)}")
        ]


@mcp.tool()
def delete_object(ctx: Context, doc_name: str, obj_name: str) -> list[TextContent | ImageContent]:
    """Delete an object in FreeCAD.

    Args:
        doc_name: The name of the document to delete the object from.
        obj_name: The name of the object to delete.

    Returns:
        A message indicating the success or failure of the object deletion and a screenshot of the object.
    """
    freecad = get_freecad_connection()
    try:
        res = freecad.delete_object(doc_name, obj_name)
        screenshot = freecad.get_active_screenshot()
        
        if res["success"]:
            response = [
                TextContent(type="text", text=f"Object '{res['object_name']}' deleted successfully"),
            ]
            return add_screenshot_if_available(response, screenshot)
        else:
            response = [
                TextContent(type="text", text=f"Failed to delete object: {res['error']}"),
            ]
            return add_screenshot_if_available(response, screenshot)
    except Exception as e:
        logger.error(f"Failed to delete object: {str(e)}")
        return [
            TextContent(type="text", text=f"Failed to delete object: {str(e)}")
        ]


@mcp.tool()
def execute_code(ctx: Context, code: str) -> list[TextContent | ImageContent]:
    """Execute arbitrary Python code in FreeCAD.

    Args:
        code: The Python code to execute.

    Returns:
        A message indicating the success or failure of the code execution, the output of the code execution, and a screenshot of the object.
    """
    freecad = get_freecad_connection()
    try:
        res = freecad.execute_code(code)
        screenshot = freecad.get_active_screenshot()
        
        if res["success"]:
            response = [
                TextContent(type="text", text=f"Code executed successfully: {res['message']}"),
            ]
            return add_screenshot_if_available(response, screenshot)
        else:
            response = [
                TextContent(type="text", text=f"Failed to execute code: {res['error']}"),
            ]
            return add_screenshot_if_available(response, screenshot)
    except Exception as e:
        logger.error(f"Failed to execute code: {str(e)}")
        return [
            TextContent(type="text", text=f"Failed to execute code: {str(e)}")
        ]


@mcp.tool()
def get_view(ctx: Context, view_name: Literal["Isometric", "Front", "Top", "Right", "Back", "Left", "Bottom", "Dimetric", "Trimetric"]) -> list[ImageContent | TextContent]:
    """Get a screenshot of the active view.

    Args:
        view_name: The name of the view to get the screenshot of.
        The following views are available:
        - "Isometric"
        - "Front"
        - "Top"
        - "Right"
        - "Back"
        - "Left"
        - "Bottom"
        - "Dimetric"
        - "Trimetric"

    Returns:
        A screenshot of the active view.
    """
    freecad = get_freecad_connection()
    screenshot = freecad.get_active_screenshot(view_name)
    
    if screenshot is not None:
        return [ImageContent(type="image", data=screenshot, mimeType="image/png")]
    else:
        return [TextContent(type="text", text="Cannot get screenshot in the current view type (such as TechDraw or Spreadsheet)")]


@mcp.tool()
def get_nodes_workbench_screenshot(ctx: Context) -> list[ImageContent | TextContent]:
    """Get a screenshot of the Nodes workbench interface.

    This tool captures the visual node editor interface from the Nodes workbench,
    showing the node graph with nodes, connections, and the overall visual scripting layout.
    This is useful for understanding complex node setups and providing visual feedback
    on parametric design workflows.

    Returns:
        A screenshot of the Nodes workbench interface, or an informative message
        if the Nodes workbench is not available or active.
    """
    freecad = get_freecad_connection()
    screenshot_data = freecad.get_nodes_workbench_screenshot()

    if screenshot_data:
        if "Nodes workbench interface is not available" in screenshot_data:
             return [TextContent(type="text", text=screenshot_data)]
        return [ImageContent(type="image", data=screenshot_data, mimeType="image/png")]
    else:
        return [TextContent(type="text", text="Failed to get Nodes workbench screenshot or it\'s not available.")]


@mcp.tool()
def mcp_freecad_nodes_create_node(
    ctx: Context, 
    node_type_op_code: str, 
    title: str | None = None, 
    x_pos: float = 0.0, 
    y_pos: float = 0.0
) -> list[TextContent | ImageContent]:
    """
    Creates a new node of a specified type in the FreeCAD Nodes workbench.

    Args:
        node_type_op_code: The operation code (string representation of the class) 
                           for the type of node to create (e.g., "<class 'generators_solid_box.SolidBox'>").
        title: Optional title for the new node. If None or empty, a default title may be used.
        x_pos: The x-coordinate for the node's position in the graph.
        y_pos: The y-coordinate for the node's position in the graph.

    Returns:
        A message indicating success or failure, and a screenshot of the Nodes workbench.
    """
    freecad = get_freecad_connection()

    # Construct the Python code to be executed in FreeCAD
    # Ensure string formatting correctly handles quotes in title and op_code if they were to appear,
    # though op_code format is fixed and title is generally simple.
    
    # Sanitize title for use in a Python string literal within the script
    safe_title_str = "None" # Default to Python's None if title is None
    if title is not None:
        # Escape backslashes and single quotes for the Python string
        escaped_title = title.replace("\\\\", "\\\\\\\\").replace("'", "\\\\'")
        safe_title_str = f"'{escaped_title}'"

    script = f"""
from PySide import QtWidgets
# QPointF is not strictly needed if setPos takes x, y directly
import FreeCADGui
import sys
import traceback

print(f"--- MCP: Creating Node ---")
print(f"OpCode: {node_type_op_code!r}, Title: {title}, Position: ({x_pos}, {y_pos})")

fcn_sub_window_widget = None
scene = None
node_created_message = "Node creation status unknown."

app = QtWidgets.QApplication.instance()
if app:
    all_widgets = app.allWidgets()
    for w in all_widgets:
        if w.__class__.__name__ == 'FCNSubWindow' and w.isVisible():
            fcn_sub_window_widget = w
            break 
    
    if fcn_sub_window_widget and hasattr(fcn_sub_window_widget, 'scene'):
        scene = fcn_sub_window_widget.scene

if not scene:
    node_created_message = "Error: No active FCNSubWindow (Nodes editor) with a scene found."
    print(node_created_message)
else:
    print(f"Found FCNSubWindow: {{fcn_sub_window_widget}} with scene: {{scene}}")
    NodesStore_class = None
    try:
        from core.nodes_conf import NodesStore as NodesStoreFromImport 
        NodesStore_class = NodesStoreFromImport
        print(f"Successfully imported NodesStore: {{NodesStore_class}}")

        if not NodesStore_class.nodes:
            print("Warning: NodesStore.nodes is empty. Attempting to refresh.")
            NodesStore_class.refresh_nodes_list()
            if NodesStore_class.nodes:
                print(f"NodesStore.nodes refreshed. Count: {{len(NodesStore_class.nodes)}}")
            else:
                print("Error: Failed to refresh NodesStore.nodes after import.")
        
    except ImportError as e_import:
        node_created_message = f"ImportError: Could not import NodesStore: {{str(e_import)}}. Check FreeCAD Python env."
        print(node_created_message)
    except Exception as e_ns_init:
        node_created_message = f"Error initializing NodesStore: {{str(e_ns_init)}}"
        print(node_created_message)
        traceback.print_exc()

    if NodesStore_class and NodesStore_class.nodes:
        actual_op_code_to_use = "{node_type_op_code}" # Use the direct op_code from arg
        
        if actual_op_code_to_use not in NodesStore_class.nodes:
            node_created_message = f"Error: OpCode '{{actual_op_code_to_use}}' not found in NodesStore.nodes."
            print(node_created_message)
            print(f"Available op_codes (first 10): {{list(NodesStore_class.nodes.keys())[:10]}}")
        else:
            try:
                NodeClass = NodesStore_class.get_class_from_opcode(actual_op_code_to_use)
                if not NodeClass:
                    node_created_message = f"Error: get_class_from_opcode returned None for '{{actual_op_code_to_use}}'."
                    print(node_created_message)
                else:
                    print(f"Got NodeClass: {{NodeClass}} for op_code: {{actual_op_code_to_use}}")
                    node_instance = NodeClass(scene)
                    
                    # Use float for positions passed to setPos
                    node_instance.setPos(float({x_pos}), float({y_pos}))
                    
                    node_title_to_set = {safe_title_str} # Use the sanitized title
                    if node_title_to_set is None: # Check for Python None after sanitization
                        node_title_to_set = getattr(NodeClass, 'op_title', f"Node_{{node_instance.id}}")
                    node_instance.title = node_title_to_set
                    
                    scene.history.storeHistory(f"Created node {{node_instance.title}} via MCP", setModified=True)
                    node_created_message = f"Successfully created node: '{{node_instance.title}}' (Type: {{actual_op_code_to_use.split('.')[-1].replace("'>", '')}}), ID: {{node_instance.id}}."
                    print(node_created_message)
            except Exception as e_create:
                node_created_message = f"Error creating node with op_code '{{actual_op_code_to_use}}': {{str(e_create)}}"
                print(node_created_message)
                traceback.print_exc()
    elif not NodesStore_class:
        node_created_message = "Critical Error: NodesStore_class not available after import attempts."
        print(node_created_message)
    elif NodesStore_class and not NodesStore_class.nodes:
         node_created_message = "Error: NodesStore_class.nodes is empty and could not be refreshed."
         print(node_created_message)

print(node_created_message) # Ensure the final message is printed for capture
"""

    # Execute the script
    response_content = []
    try:
        execution_result = freecad.execute_code(script)
        raw_script_output = execution_result.get("message", "").strip()
        output_lines = raw_script_output.split('\\\\n')
        
        # Default message if specific indicators aren't found
        final_status_message = "Node creation script executed. See log for details."
        if output_lines:
            final_status_message = output_lines[-1] # Get the last actual printed line as the primary status

        if "Successfully created node" in raw_script_output: # Check in the whole output
            response_content.append(TextContent(type="text", text=final_status_message))
        elif "Error" in raw_script_output or "Warning" in raw_script_output or "Critical" in raw_script_output :
            # If error indicators are in the output, prioritize showing the full log clearly.
            response_content.append(TextContent(type="text", text=f"Node creation issues detected. Status: '{final_status_message}'. Full Log:\\n{raw_script_output}"))
        else: # Fallback for non-error, non-explicit-success cases
            response_content.append(TextContent(type="text", text=f"Node creation attempt finished. Final line: '{final_status_message}'. Full Log:\\n{raw_script_output}"))

    except Exception as e:
        logger.error(f"MCP tool mcp_freecad_nodes_create_node failed: {{str(e)}}")
        response_content.append(TextContent(type="text", text=f"Failed to execute node creation script: {{str(e)}}"))

    # Add a screenshot
    screenshot_data = freecad.get_nodes_workbench_screenshot()
    if screenshot_data:
        if "Nodes workbench interface is not available" in screenshot_data:
             response_content.append(TextContent(type="text", text=screenshot_data))
        elif not _only_text_feedback: # _only_text_feedback is a global defined in the file
            response_content.append(ImageContent(type="image", data=screenshot_data, mimeType="image/png"))
    
    return response_content


@mcp.tool()
def mcp_freecad_nodes_clear_scene(ctx: Context) -> list[TextContent | ImageContent]:
    """
    Removes all nodes and edges from the current FreeCAD Nodes workbench scene.

    Returns:
        A message indicating success or failure, and a screenshot of the Nodes workbench.
    """
    freecad = get_freecad_connection()

    script = f'''
from PySide import QtWidgets
import FreeCADGui
import traceback

print(f"--- MCP: Clearing Nodes Scene ---")
clear_message = "Scene clearing status unknown."

fcn_sub_window_widget = None
scene = None

app = QtWidgets.QApplication.instance()
if app:
    all_widgets = app.allWidgets()
    for w in all_widgets:
        if w.__class__.__name__ == 'FCNSubWindow' and w.isVisible():
            fcn_sub_window_widget = w
            break
    if fcn_sub_window_widget and hasattr(fcn_sub_window_widget, 'scene'):
        scene = fcn_sub_window_widget.scene

if not scene:
    clear_message = "Error: No active FCNSubWindow (Nodes editor) with a scene found."
    print(clear_message)
else:
    print(f"Found FCNSubWindow with scene: {{scene}}")
    try:
        # Attempt 1: Use a dedicated clear command if it exists (most robust)
        # The exact module and class name might vary. This is a common pattern.
        # Example: workbench_name.module_name.ClassName()
        # Adjust if the specific command for Nodes workbench is known.

        # Trying to find a clear scene command specific to the "Nodes" workbench
        # This is speculative as direct access to workbench commands from here is complex.
        # A more direct approach is to interact with the scene object itself.

        nodes_wb = None
        if FreeCADGui. एक्टिवWorkbench(): # Check if FreeCADGui.ActiveWorkbench is a typo for FreeCADGui.activeWorkbench() or similar
             current_wb_name = FreeCADGui.activeWorkbench().name()
             if current_wb_name == "Nodes": # Assuming "Nodes" is the internal name
                 nodes_wb = FreeCADGui.activeWorkbench()

        # Option A: Look for a 'clearScene' or similar method directly on the scene
        if hasattr(scene, 'clear') and callable(scene.clear):
            print("Attempting to clear scene using scene.clear()")
            scene.clear()
            clear_message = "Successfully cleared scene using scene.clear()."
            scene.history.storeHistory("Scene cleared via MCP (scene.clear)", setModified=True)
        elif hasattr(scene, 'reset') and callable(scene.reset):
            print("Attempting to clear scene using scene.reset()")
            scene.reset() # Some graphics scenes might use reset
            clear_message = "Successfully cleared scene using scene.reset()."
            scene.history.storeHistory("Scene cleared via MCP (scene.reset)", setModified=True)
        # Option B: Manually delete all nodes (edges are usually deleted with nodes)
        elif hasattr(scene, 'nodes') and isinstance(scene.nodes, list):
            print(f"Attempting to clear scene by deleting all {{len(scene.nodes)}} nodes manually.")
            # Iterate over a copy of the list if modifying it (node.delete might remove from scene.nodes)
            for node_item in list(scene.nodes):
                if hasattr(node_item, 'delete') and callable(node_item.delete):
                    print(f"Deleting node {{getattr(node_item, 'title', 'UNTITLED')}} (ID: {{getattr(node_item, 'id', 'NO_ID')}})")
                    node_item.delete()
                elif hasattr(scene, 'removeNode') and callable(scene.removeNode): # Alternative
                    print(f"Removing node {{getattr(node_item, 'title', 'UNTITLED')}} (ID: {{getattr(node_item, 'id', 'NO_ID')}}) using scene.removeNode()")
                    scene.removeNode(node_item)
                else:
                    print(f"Warning: Could not find delete() or scene.removeNode() for node {{node_item}}.")

            # Verify (optional, but good)
            if not scene.nodes and (not hasattr(scene, 'edges') or not scene.edges):
                clear_message = "Successfully cleared scene by deleting all nodes."
                scene.history.storeHistory("Scene cleared via MCP (manual node deletion)", setModified=True)
            else:
                clear_message = f"Warning: Scene clear attempted by deleting nodes, but {{len(scene.nodes)}} nodes and {{len(getattr(scene, 'edges', []))}} edges may remain."
        else:
            clear_message = "Error: Scene found, but no known method to clear it (no clear(), reset(), or scene.nodes list)."

        print(clear_message)

    except Exception as e_clear:
        clear_message = f"Error during scene clearing: {{str(e_clear)}}"
        print(clear_message)
        traceback.print_exc()

print(clear_message) # Final status
'''
    response_content = []
    try:
        execution_result = freecad.execute_code(script)
        raw_script_output = execution_result.get("message", "").strip()
        output_lines = raw_script_output.split('\\n')

        final_status_message = "Scene clearing script executed. See log for details."
        if output_lines:
            for line in reversed(output_lines):
                if line.strip():
                    final_status_message = line.strip()
                    break

        if "Successfully cleared scene" in raw_script_output:
            response_content.append(TextContent(type="text", text=final_status_message))
        elif "Error" in raw_script_output or "Warning" in raw_script_output:
            response_content.append(TextContent(type="text", text=f"Scene clearing issues: '{final_status_message}'. Full Log:\n{raw_script_output}"))
        else:
            response_content.append(TextContent(type="text", text=f"Scene clearing attempt finished. Status: '{final_status_message}'. Full Log:\n{raw_script_output}"))

    except Exception as e:
        logger.error(f"MCP tool mcp_freecad_nodes_clear_scene failed: {str(e)}")
        response_content.append(TextContent(type="text", text=f"Failed to execute scene clearing script: {str(e)}"))

    screenshot_data = freecad.get_nodes_workbench_screenshot()
    if screenshot_data:
        if "Nodes workbench interface is not available" in screenshot_data:
             response_content.append(TextContent(type="text", text=screenshot_data))
        elif not _only_text_feedback:
            response_content.append(ImageContent(type="image", data=screenshot_data, mimeType="image/png"))

    return response_content


@mcp.tool()
def mcp_freecad_nodes_get_graph_state(ctx: Context) -> list[TextContent]:
    """
    Retrieves a JSON string detailing the nodes, their properties, and connections
    in the current FreeCAD Nodes workbench graph.

    Returns:
        A list containing a single TextContent element. This element will contain a JSON string
        of the graph state if successful, or an error message if retrieval fails.
    """
    freecad = get_freecad_connection()

    script = f'''
from PySide import QtWidgets
import FreeCADGui
import traceback
import json

print(f"--- MCP: Getting Node Graph State ---")
result_output = '{{"error": "Graph state retrieval status unknown."}}' # Default error JSON

# Helper to safely get socket name
def get_socket_display_name(socket_obj):
    for attr in ['name', 'label', 'title', 'socket_name']:
        if hasattr(socket_obj, attr):
            val = getattr(socket_obj, attr)
            if callable(val):
                try:
                    return str(val())
                except:
                    continue # Try next attribute if call fails
            return str(val)
    return "UnknownSocketName"

# Helper to get socket type if available
def get_socket_type(socket_obj):
    if hasattr(socket_obj, 'socket_type_name'): # Example attribute
        return str(socket_obj.socket_type_name)
    if hasattr(socket_obj, 'type_name'):
        return str(socket_obj.type_name)
    # Add other common type attributes if known
    return None


# Custom JSON encoder to handle non-serializable objects gracefully
class SafeJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            # For QPointF or similar position objects often found in graphics libraries
            if hasattr(obj, 'x') and hasattr(obj, 'y') and callable(obj.x) and callable(obj.y):
                 return {{"x": obj.x(), "y": obj.y()}}
            # Attempt to convert to string if other types fail
            return str(obj)
        except Exception:
            return f"<Object of type {{type(obj).__name__}} not serializable>"

app = QtWidgets.QApplication.instance()
fcn_sub_window_widget = None
scene = None

if app:
    all_widgets = app.allWidgets()
    for w in all_widgets:
        if w.__class__.__name__ == 'FCNSubWindow' and w.isVisible():
            fcn_sub_window_widget = w
            break
    if fcn_sub_window_widget and hasattr(fcn_sub_window_widget, 'scene'):
        scene = fcn_sub_window_widget.scene

if not scene:
    result_output = '{{"error": "No active FCNSubWindow (Nodes editor) with a scene found."}}'
    print(result_output)
else:
    print(f"Found FCNSubWindow with scene: {{scene}}")
    graph_data = {{"nodes": [], "edges": []}}

    try:
        for node_item in scene.nodes:
            node_dict = {{}}
            try:
                node_dict['id'] = str(node_item.id)
                node_dict['title'] = str(node_item.title)

                node_type = "UnknownType"
                if hasattr(node_item, 'op_code') and node_item.op_code: # Preferred
                    node_type = str(node_item.op_code)
                elif hasattr(node_item, '__class__'):
                    node_type = node_item.__class__.__module__ + "." + node_item.__class__.__name__
                node_dict['type'] = node_type

                if hasattr(node_item, 'pos') and callable(node_item.pos):
                    pos_obj = node_item.pos()
                    node_dict['position'] = {{"x": pos_obj.x(), "y": pos_obj.y()}}
                else:
                    node_dict['position'] = {{"x": None, "y": None}}

                node_dict['inputs'] = []
                # Check common input socket list names: 'inputs', 'valInputs'
                input_socket_lists_names = [l for l in ['inputs', 'valInputs'] if hasattr(node_item, l)]
                for list_name in input_socket_lists_names:
                    sockets = getattr(node_item, list_name)
                    for i, sock in enumerate(sockets):
                        sock_info = {{
                            "name": get_socket_display_name(sock),
                            "index": i,
                            "list_source": list_name # To know if it was from 'inputs' or 'valInputs'
                        }}
                        sock_type = get_socket_type(sock)
                        if sock_type: sock_info["type"] = sock_type
                        node_dict['inputs'].append(sock_info)

                node_dict['outputs'] = []
                # Check common output socket list names: 'outputs', 'valOutputs'
                output_socket_lists_names = [l for l in ['outputs', 'valOutputs'] if hasattr(node_item, l)]
                for list_name in output_socket_lists_names:
                    sockets = getattr(node_item, list_name)
                    for i, sock in enumerate(sockets):
                        sock_info = {{
                            "name": get_socket_display_name(sock),
                            "index": i,
                            "list_source": list_name
                        }}
                        sock_type = get_socket_type(sock)
                        if sock_type: sock_info["type"] = sock_type
                        node_dict['outputs'].append(sock_info)

                graph_data["nodes"].append(node_dict)
            except Exception as e_node:
                print(f"WARNING: Could not fully serialize node {{getattr(node_item, 'id', 'UNKNOWN_ID')}}: {{str(e_node)}}")
                # Add partial data if possible or skip
                if 'id' not in node_dict and hasattr(node_item, 'id'): node_dict['id'] = str(node_item.id)
                if 'title' not in node_dict and hasattr(node_item, 'title'): node_dict['title'] = str(node_item.title)
                node_dict['error'] = f"Partial data due to serialization error: {{str(e_node)}}"
                if node_dict.get('id'): # Only add if we have an ID
                    graph_data["nodes"].append(node_dict)


        if hasattr(scene, 'edges'):
            for edge_item in scene.edges:
                edge_dict = {{}}
                try:
                    start_sock = edge_item.start_socket
                    end_sock = edge_item.end_socket

                    edge_dict['source_node_id'] = str(start_sock.node.id)
                    edge_dict['source_socket_name'] = get_socket_display_name(start_sock)
                    # Finding exact index might require iterating source node's output sockets
                    # This is a simplification; for robustness, one might need to find index by object identity
                    edge_dict['source_socket_index'] = start_sock.index if hasattr(start_sock, 'index') else -1

                    edge_dict['target_node_id'] = str(end_sock.node.id)
                    edge_dict['target_socket_name'] = get_socket_display_name(end_sock)
                    edge_dict['target_socket_index'] = end_sock.index if hasattr(end_sock, 'index') else -1

                    graph_data["edges"].append(edge_dict)
                except Exception as e_edge:
                    print(f"WARNING: Could not fully serialize edge: {{str(e_edge)}}")
                    graph_data["edges"].append({{"error": f"Failed to serialize edge: {{str(e_edge)}}"}})

        result_output = json.dumps(graph_data, indent=2, cls=SafeJSONEncoder)
        print("Graph state successfully serialized.")

    except Exception as e_main:
        result_output = json.dumps({{"error": f"Failed to retrieve graph state: {{str(e_main)}}", "trace": traceback.format_exc()}}, indent=2)
        print(result_output) # Print the error JSON

# This final print is what the MCP tool will capture as the primary output.
print(result_output)
'''
    response_content = []
    try:
        execution_result = freecad.execute_code(script)
        raw_script_output = execution_result.get("message", "").strip()

        final_json_output = ""
        if raw_script_output:
            lines = raw_script_output.split('\\n')
            # The script is designed to print the JSON as its last significant output.
            # We look for the last line that looks like a valid JSON object or array start.
            for line in reversed(lines):
                stripped_line = line.strip()
                if stripped_line.startswith("{{") and stripped_line.endswith("}}") or \
                   stripped_line.startswith("[") and stripped_line.endswith("]"):
                    final_json_output = stripped_line
                    break
            if not final_json_output: # Fallback if no clear JSON found, take the last non-empty line
                 for line in reversed(lines):
                    if line.strip():
                        final_json_output = line.strip()
                        break

        if not final_json_output:
            final_json_output = '{{"error": "Script produced no discernible JSON output."}}'

        response_content.append(TextContent(type="text", text=final_json_output))

    except Exception as e:
        logger.error(f"MCP tool mcp_freecad_nodes_get_graph_state failed: {str(e)}")
        error_json = json.dumps({{"error": f"Failed to execute graph state script: {str(e)}", "trace": traceback.format_exc()}})
        response_content.append(TextContent(type="text", text=error_json))

    return response_content


@mcp.tool()
def mcp_freecad_nodes_get_node_value(
    ctx: Context,
    node_id_or_title: str,
    output_socket_index_or_name_or_property_path: str
) -> list[TextContent]:
    """
    Retrieves the value of an output socket or a direct property of a specified node
    in the FreeCAD Nodes workbench.

    Args:
        node_id_or_title: The ID or title of the node.
        output_socket_index_or_name_or_property_path: The index (as string, e.g., "0"),
                                                     name/label of the output socket, or a
                                                     simple dot-separated property path
                                                     (e.g., "property_name.sub_property").
                                                     Currently, only direct output socket access is prioritized.

    Returns:
        A list containing a single TextContent element. This element will contain a JSON string
        of the retrieved value if successful, or an error message if retrieval fails.
    """
    freecad = get_freecad_connection()

    script = f'''
from PySide import QtWidgets
import FreeCADGui
import traceback
import json

print(f"--- MCP: Getting Node Output/Property Value ---")
node_ref_param = "{node_id_or_title}"
socket_or_prop_ref_param = "{output_socket_index_or_name_or_property_path}"

print(f"Attempting to get value for node '{{node_ref_param}}', output/property '{{socket_or_prop_ref_param}}'.")

fcn_sub_window_widget = None
scene = None
result_output = "ERROR: Value retrieval status unknown." # Default to error

# Helper to find an output socket by index or name/label
# Searches common attribute names for sockets: name, title, label, socket_name
# valOutputs is common for value-only outputs, outputs for general outputs
def find_output_socket(node, ref):
    socket_found = None
    # Try by index first for valOutputs, then outputs
    for output_list_attr_name in ['valOutputs', 'outputs']: # Check common names for output socket lists
        if hasattr(node, output_list_attr_name):
            output_list = getattr(node, output_list_attr_name)
            try:
                idx = int(ref)
                if 0 <= idx < len(output_list):
                    socket_found = output_list[idx]
                    print(f"Found output socket by index {{idx}} in {{output_list_attr_name}}.")
                    return socket_found
            except ValueError: # ref is not an integer
                pass

    # Try by name/label for valOutputs, then outputs
    for output_list_attr_name in ['valOutputs', 'outputs']:
        if hasattr(node, output_list_attr_name):
            output_list = getattr(node, output_list_attr_name)
            for i, s in enumerate(output_list):
                for attr_name in ['name', 'title', 'label', 'socket_name']:
                    if hasattr(s, attr_name):
                        val = getattr(s, attr_name)
                        if callable(val): val = val()
                        if str(val) == ref:
                            print(f"Found output socket by name/label '{{ref}}' (attr: {{attr_name}}) in {{output_list_attr_name}} at index {{i}}.")
                            return s
                if str(i) == ref: # Fallback: string index
                    print(f"Found output socket by string index '{{ref}}' in {{output_list_attr_name}} at index {{i}}.")
                    return s
    print(f"Output socket '{{ref}}' not found by index or name/label in any output list.")
    return None

app = QtWidgets.QApplication.instance()
if app:
    all_widgets = app.allWidgets()
    for w in all_widgets:
        if w.__class__.__name__ == 'FCNSubWindow' and w.isVisible():
            fcn_sub_window_widget = w
            break
    if fcn_sub_window_widget and hasattr(fcn_sub_window_widget, 'scene'):
        scene = fcn_sub_window_widget.scene

if not scene:
    result_output = "ERROR: No active FCNSubWindow (Nodes editor) with a scene found."
    print(result_output)
else:
    print(f"Found FCNSubWindow with scene.")
    target_node = None
    for node_item in scene.nodes:
        if str(node_item.id) == node_ref_param or node_item.title == node_ref_param:
            target_node = node_item
            print(f"Found target node: {{target_node.title}} (ID: {{target_node.id}})")
            break

    if not target_node:
        result_output = f"ERROR: Node '{{node_ref_param}}' not found."
    else:
        output_socket = find_output_socket(target_node, socket_or_prop_ref_param)

        if output_socket:
            socket_display_name = getattr(output_socket, 'name', getattr(output_socket, 'title', lambda: str(output_socket))())
            if callable(socket_display_name): socket_display_name = socket_display_name()
            print(f"Found output socket: {{socket_display_name}} on node {{target_node.title}}")

            retrieved_value = None
            value_found = False
            # Try common ways to get a socket's value
            if hasattr(output_socket, 'value') and callable(output_socket.value):
                retrieved_value = output_socket.value()
                value_found = True
                print(f"Retrieved value using socket.value()")
            elif hasattr(output_socket, 'getValue') and callable(output_socket.getValue):
                retrieved_value = output_socket.getValue()
                value_found = True
                print(f"Retrieved value using socket.getValue()")
            elif hasattr(output_socket, 'currentValue'): # Attribute, not method
                retrieved_value = output_socket.currentValue
                value_found = True
                print(f"Retrieved value using socket.currentValue attribute")
            elif hasattr(output_socket, 'val'): # Attribute, not method
                retrieved_value = output_socket.val
                value_found = True
                print(f"Retrieved value using socket.val attribute")

            if value_found:
                try:
                    # Serialize to JSON. If this fails, it's a non-serializable type.
                    result_output = json.dumps(retrieved_value)
                    # This print is crucial: it's the actual value sent back if successful
                    print(f"Value successfully retrieved and serialized: {{result_output}}")
                except TypeError as e_json_type:
                    result_output = f"ERROR: Value for socket '{{socket_display_name}}' is not JSON serializable: {{str(e_json_type)}}. Type: {{type(retrieved_value)}}."
                    print(result_output)
                except Exception as e_serialize:
                    result_output = f"ERROR: Could not serialize value from socket '{{socket_display_name}}': {{str(e_serialize)}}."
                    print(result_output)
                    traceback.print_exc()
            else:
                result_output = f"ERROR: No known value getter method/attribute found on output socket '{{socket_display_name}}'."
                print(result_output)
        else:
            # Placeholder for future direct property access logic if socket is not found
            # For now, if it's not an output socket, it's an error or unsupported.
            # if "." in socket_or_prop_ref_param:
            #    result_output = f"ERROR: Direct property path access ('{{socket_or_prop_ref_param}}') is not yet implemented."
            # else:
            result_output = f"ERROR: Output socket or property '{{socket_or_prop_ref_param}}' not found on node '{{target_node.title}}'."
            print(result_output)

# The last print statement before potential tracebacks should be the primary result or error.
# If an error occurred above and was printed, that print will be the last one.
# If successful, the json.dumps(value) will be printed.
# This final print ensures that 'result_output' (which holds the latest status/error or JSON value) is the last thing.
print(result_output)
'''
    response_content = []
    try:
        execution_result = freecad.execute_code(script)
        raw_script_output = execution_result.get("message", "").strip()

        # The script is designed so its last non-empty line is either the JSON value or an "ERROR: " prefixed message.
        final_output_line = ""
        if raw_script_output:
            lines = raw_script_output.split('\\n')
            for line in reversed(lines):
                if line.strip():
                    final_output_line = line.strip()
                    break

        # If final_output_line is empty here, it means script produced no discernible output or only empty lines.
        if not final_output_line:
             final_output_line = "ERROR: Script produced no discernible output."

        response_content.append(TextContent(type="text", text=final_output_line))

    except Exception as e:
        logger.error(f"MCP tool mcp_freecad_nodes_get_node_value failed: {str(e)}")
        # Return the exception as the error message
        response_content.append(TextContent(type="text", text=f"ERROR: Failed to execute node value retrieval script: {str(e)}"))

    return response_content


@mcp.tool()
def mcp_freecad_nodes_set_node_value(
    ctx: Context,
    node_id_or_title: str,
    input_socket_index_or_name: str,
    value_json: str
) -> list[TextContent | ImageContent]:
    """
    Sets the value of an input socket on a specified node in the FreeCAD Nodes workbench.

    Args:
        node_id_or_title: The ID or title of the node.
        input_socket_index_or_name: The index (as string, e.g., "0", "1") or name/label
                                     of the input socket on the node.
        value_json: A JSON string representing the value to set.
                    For strings, ensure they are JSON-escaped (e.g., "\"hello world\"").
                    For numbers: "123", "3.14". For booleans: "true", "false".
                    For lists/objects: "[1, 2, 3]", "{\"key\": \"value\"}".

    Returns:
        A message indicating success or failure, and a screenshot of the Nodes workbench.
    """
    freecad = get_freecad_connection()

    # The value_json is passed within triple quotes to the script to handle complex JSON strings.
    script = f'''
from PySide import QtWidgets
import FreeCADGui
import traceback
import json

print(f"--- MCP: Setting Node Input Value ---")
node_ref_param = "{node_id_or_title}"
socket_ref_param = "{input_socket_index_or_name}"
# value_json_param is enclosed in triple single quotes to preserve its content,
# including quotes and newlines, for json.loads()
value_json_param = """{value_json}"""

print(f"Attempting to set value for node '{{node_ref_param}}', socket '{{socket_ref_param}}'. Value JSON: {{value_json_param}}")

fcn_sub_window_widget = None
scene = None
set_value_message = "Node value setting status unknown."

# Helper to find an input socket by index or name/label
# Searches common attribute names for sockets: name, title, label, socket_name
# valInputs is common for value-only inputs, inputs for general inputs
def find_input_socket(node, ref):
    socket_found = None
    # Try by index first for valInputs, then inputs
    for input_list_attr_name in ['valInputs', 'inputs']:
        if hasattr(node, input_list_attr_name):
            input_list = getattr(node, input_list_attr_name)
            try:
                idx = int(ref)
                if 0 <= idx < len(input_list):
                    socket_found = input_list[idx]
                    print(f"Found socket by index {{idx}} in {{input_list_attr_name}}.")
                    return socket_found
            except ValueError: # ref is not an integer, so it's a name/label
                pass # Continue to name search below

    # Try by name/label for valInputs, then inputs
    for input_list_attr_name in ['valInputs', 'inputs']:
        if hasattr(node, input_list_attr_name):
            input_list = getattr(node, input_list_attr_name)
            for i, s in enumerate(input_list):
                # Check common attributes for socket name/label
                for attr_name in ['name', 'title', 'label', 'socket_name']:
                    if hasattr(s, attr_name):
                        val = getattr(s, attr_name)
                        if callable(val): val = val() # Call if it's a method (e.g. title(), label())
                        if str(val) == ref: # Compare string representations
                            print(f"Found socket by name/label '{{ref}}' (attr: {{attr_name}}) in {{input_list_attr_name}} at index {{i}}.")
                            return s
                # Fallback: check if ref is a string representation of the index
                if str(i) == ref:
                    print(f"Found socket by string index '{{ref}}' in {{input_list_attr_name}} at index {{i}}.")
                    return s
    print(f"Socket '{{ref}}' not found by index or name/label in any input list.")
    return None

app = QtWidgets.QApplication.instance()
if app:
    all_widgets = app.allWidgets()
    for w in all_widgets:
        if w.__class__.__name__ == 'FCNSubWindow' and w.isVisible():
            fcn_sub_window_widget = w
            break
    if fcn_sub_window_widget and hasattr(fcn_sub_window_widget, 'scene'):
        scene = fcn_sub_window_widget.scene

if not scene:
    set_value_message = "Error: No active FCNSubWindow (Nodes editor) with a scene found."
    print(set_value_message)
else:
    print(f"Found FCNSubWindow with scene.")

    target_node = None
    for node_item in scene.nodes:
        if str(node_item.id) == node_ref_param or node_item.title == node_ref_param:
            target_node = node_item
            print(f"Found target node: {{target_node.title}} (ID: {{target_node.id}})")
            break

    if not target_node:
        set_value_message = f"Error: Node '{{node_ref_param}}' not found."
    else:
        input_socket = find_input_socket(target_node, socket_ref_param)

        if not input_socket:
            set_value_message = f"Error: Input socket '{{socket_ref_param}}' not found on node '{{target_node.title}}'."
        else:
            socket_display_name = getattr(input_socket, 'name', getattr(input_socket, 'title', lambda: str(input_socket))())
            if callable(socket_display_name): socket_display_name = socket_display_name()

            print(f"Found input socket: {{socket_display_name}} on node {{target_node.title}}")
            try:
                actual_value = json.loads(value_json_param)
                print(f"Successfully parsed JSON value: {{actual_value}} (type: {{type(actual_value)}})")

                setter_method_used = None
                if hasattr(input_socket, 'setValue') and callable(input_socket.setValue):
                    input_socket.setValue(actual_value)
                    setter_method_used = 'setValue'
                elif hasattr(input_socket, 'setCurrentValue') and callable(input_socket.setCurrentValue):
                    input_socket.setCurrentValue(actual_value) # Common in some Nodz-based systems
                    setter_method_used = 'setCurrentValue'
                # Add other potential setters if known, e.g. set_value, val etc.
                # elif hasattr(input_socket, 'val') and not callable(input_socket.val):
                #    input_socket.val = actual_value # Direct attribute access if applicable
                #    setter_method_used = 'val (direct attribute)'

                if setter_method_used:
                    set_value_message = f"Successfully set value '{{actual_value}}' on socket '{{socket_display_name}}' of node '{{target_node.title}}' using {{setter_method_used}}."

                    # Trigger updates if available - this is speculative and depends on the specific Nodes framework
                    if hasattr(target_node, 'update') and callable(target_node.update):
                        print("Calling target_node.update()")
                        target_node.update()
                    if hasattr(target_node, 'eval') and callable(target_node.eval): # Some nodes might have eval
                        print("Calling target_node.eval()")
                        target_node.eval()
                    if hasattr(scene, 'update') and callable(scene.update): # Scene update might be needed
                        print("Calling scene.update()")
                        scene.update()

                    scene.history.storeHistory(f"Set value on {{target_node.title}}.{{socket_display_name}} to {{actual_value}} via MCP", setModified=True)
                else:
                    set_value_message = f"Error: No known value setter method (setValue, setCurrentValue) found on socket '{{socket_display_name}}'."

                print(set_value_message)

            except json.JSONDecodeError as e_json:
                set_value_message = f"Error: Failed to parse value_json: {{str(e_json)}}. JSON received: {{value_json_param}}"
                print(set_value_message)
                traceback.print_exc()
            except Exception as e_set:
                set_value_message = f"Error setting value on socket '{{socket_display_name}}': {{str(e_set)}}"
                print(set_value_message)
                traceback.print_exc()
print(set_value_message)
'''
    response_content = []
    try:
        # Execute the script, passing parameters safely.
        # value_json is already a string, directly embed it.
        # The script itself uses triple quotes for value_json_param to handle its content.
        execution_result = freecad.execute_code(script) # No .format() needed here due to f-string usage with local vars

        raw_script_output = execution_result.get("message", "").strip()
        output_lines = raw_script_output.split('\\n')

        final_status_message = "Node value setting script executed. See log for details."
        if output_lines:
            for line in reversed(output_lines): # Get the last non-empty line
                if line.strip():
                    final_status_message = line.strip()
                    break

        if "Successfully set value" in raw_script_output:
            response_content.append(TextContent(type="text", text=final_status_message))
        elif "Error" in raw_script_output or "Warning" in raw_script_output:
            response_content.append(TextContent(type="text", text=f"Node value setting issues: '{final_status_message}'. Full Log:\n{raw_script_output}"))
        else:
            response_content.append(TextContent(type="text", text=f"Node value setting attempt finished. Status: '{final_status_message}'. Full Log:\n{raw_script_output}"))

    except Exception as e:
        logger.error(f"MCP tool mcp_freecad_nodes_set_node_value failed: {str(e)}")
        response_content.append(TextContent(type="text", text=f"Failed to execute node value setting script: {str(e)}"))

    screenshot_data = freecad.get_nodes_workbench_screenshot()
    if screenshot_data:
        if "Nodes workbench interface is not available" in screenshot_data:
             response_content.append(TextContent(type="text", text=screenshot_data))
        elif not _only_text_feedback: # _only_text_feedback is a global
            response_content.append(ImageContent(type="image", data=screenshot_data, mimeType="image/png"))

    return response_content


@mcp.tool()
def mcp_freecad_nodes_delete_edge(
    ctx: Context,
    source_node_id_or_title: str,
    source_socket_index_or_name: str,
    target_node_id_or_title: str,
    target_socket_index_or_name: str
) -> list[TextContent | ImageContent]:
    """
    Deletes a specific edge between two nodes in the FreeCAD Nodes workbench.
    The edge is identified by the source and target nodes and their respective sockets.

    Args:
        source_node_id_or_title: ID or title of the source node of the edge.
        source_socket_index_or_name: Index or name of the output socket on the source node.
        target_node_id_or_title: ID or title of the target node of the edge.
        target_socket_index_or_name: Index or name of the input socket on the target node.

    Returns:
        A message indicating success or failure, and a screenshot of the Nodes workbench.
    """
    freecad = get_freecad_connection()

    script = f'''
from PySide import QtWidgets
import FreeCADGui
import traceback

print(f"--- MCP: Deleting Edge ---")
src_node_ref = "{source_node_id_or_title}"
src_sock_ref = "{source_socket_index_or_name}"
tgt_node_ref = "{target_node_id_or_title}"
tgt_sock_ref = "{target_socket_index_or_name}"

print(f"Attempting to delete edge: {{src_node_ref}}[{{src_sock_ref}}] -> {{tgt_node_ref}}[{{tgt_sock_ref}}]")

fcn_sub_window_widget = None
scene = None
delete_edge_message = "Edge deletion status unknown."

# Helper to find a socket by index or name
def find_socket(node, socket_ref, socket_list_type):
    try:
        idx = int(socket_ref)
        if 0 <= idx < len(getattr(node, socket_list_type)):
            return getattr(node, socket_list_type)[idx]
    except ValueError: # It's a name
        for s in getattr(node, socket_list_type):
            if (hasattr(s, 'name') and s.name == socket_ref) or \
               (hasattr(s, 'label') and callable(s.label) and s.label() == socket_ref):
                return s
    return None

app = QtWidgets.QApplication.instance()
if app:
    all_widgets = app.allWidgets()
    for w in all_widgets:
        if w.__class__.__name__ == 'FCNSubWindow' and w.isVisible():
            fcn_sub_window_widget = w
            break
    if fcn_sub_window_widget and hasattr(fcn_sub_window_widget, 'scene'):
        scene = fcn_sub_window_widget.scene

if not scene:
    delete_edge_message = "Error: No active FCNSubWindow (Nodes editor) with a scene found."
    print(delete_edge_message)
else:
    print(f"Found FCNSubWindow with scene.")

    source_node, target_node = None, None
    for node_item in scene.nodes:
        if str(node_item.id) == src_node_ref or node_item.title == src_node_ref:
            source_node = node_item
        if str(node_item.id) == tgt_node_ref or node_item.title == tgt_node_ref:
            target_node = node_item
        if source_node and target_node:
            break

    if not source_node:
        delete_edge_message = f"Error: Source node '{{src_node_ref}}' not found."
    elif not target_node:
        delete_edge_message = f"Error: Target node '{{tgt_node_ref}}' not found."
    else:
        print(f"Found source node: {{source_node.title}}, Target node: {{target_node.title}}")
        source_socket = find_socket(source_node, src_sock_ref, 'outputs')
        target_socket = find_socket(target_node, tgt_sock_ref, 'inputs')

        if not source_socket:
            delete_edge_message = f"Error: Source socket '{{src_sock_ref}}' not found on node '{{source_node.title}}'."
        elif not target_socket:
            delete_edge_message = f"Error: Target socket '{{tgt_sock_ref}}' not found on node '{{target_node.title}}'."
        else:
            s_sock_name = getattr(source_socket, 'name', str(source_socket))
            t_sock_name = getattr(target_socket, 'name', str(target_socket))
            print(f"Found source socket: {{s_sock_name}}, Target socket: {{t_sock_name}}")

            edge_to_delete = None
            # Edges are typically stored in the scene or accessible via sockets
            if hasattr(scene, 'edges'): # Nodz stores edges in scene.edges
                for edge in scene.edges:
                    if edge.start_socket == source_socket and edge.end_socket == target_socket:
                        edge_to_delete = edge
                        break
            elif hasattr(source_socket, 'edges'): # Sockets might also hold their edges
                 for edge in source_socket.edges:
                    if edge.start_socket == source_socket and edge.end_socket == target_socket:
                        edge_to_delete = edge
                        break

            if not edge_to_delete:
                delete_edge_message = f"Error: Edge not found between {{source_node.title}}[{{s_sock_name}}] and {{target_node.title}}[{{t_sock_name}}]."
            else:
                try:
                    # In Nodz, edge.delete() or scene.removeEdge(edge)
                    if hasattr(edge_to_delete, 'delete') and callable(edge_to_delete.delete):
                        edge_to_delete.delete()
                        delete_edge_message = f"Successfully deleted edge: {{source_node.title}}[{{s_sock_name}}] -> {{target_node.title}}[{{t_sock_name}}]."
                    elif hasattr(scene, 'removeEdge') and callable(scene.removeEdge):
                        scene.removeEdge(edge_to_delete)
                        delete_edge_message = f"Successfully deleted edge (via scene.removeEdge): {{source_node.title}}[{{s_sock_name}}] -> {{target_node.title}}[{{t_sock_name}}]."
                    else:
                        delete_edge_message = f"Error: Edge found, but no delete() or scene.removeEdge() method available."

                    if "Successfully deleted" in delete_edge_message:
                         scene.history.storeHistory(f"Deleted edge {{source_node.title}}[{{s_sock_name}}] -> {{target_node.title}}[{{t_sock_name}}] via MCP", setModified=True)
                    print(delete_edge_message)
                except Exception as e_del_edge:
                    delete_edge_message = f"Error during deletion of edge: {{str(e_del_edge)}}"
                    print(delete_edge_message)
                    traceback.print_exc()
    print(delete_edge_message)
'''

    response_content = []
    try:
        execution_result = freecad.execute_code(script.format(
            source_node_id_or_title=source_node_id_or_title,
            source_socket_index_or_name=str(source_socket_index_or_name),
            target_node_id_or_title=target_node_id_or_title,
            target_socket_index_or_name=str(target_socket_index_or_name)
        ))
        raw_script_output = execution_result.get("message", "").strip()
        output_lines = raw_script_output.split('\\\\n')

        final_status_message = "Edge deletion script executed. See log for details."
        if output_lines:
            for line in reversed(output_lines):
                if line.strip():
                    final_status_message = line.strip()
                    break

        if "Successfully deleted edge" in raw_script_output:
            response_content.append(TextContent(type="text", text=final_status_message))
        elif "Error" in raw_script_output or "Warning" in raw_script_output:
            response_content.append(TextContent(type="text", text=f"Edge deletion issues: '{{final_status_message}}'. Full Log:\\n{{raw_script_output}}"))
        else:
            response_content.append(TextContent(type="text", text=f"Edge deletion attempt finished. Status: '{{final_status_message}}'. Full Log:\\n{{raw_script_output}}"))

    except Exception as e:
        logger.error(f"MCP tool mcp_freecad_nodes_delete_edge failed: {{str(e)}}")
        response_content.append(TextContent(type="text", text=f"Failed to execute edge deletion script: {{str(e)}}"))

    screenshot_data = freecad.get_nodes_workbench_screenshot()
    if screenshot_data:
        if "Nodes workbench interface is not available" in screenshot_data:
             response_content.append(TextContent(type="text", text=screenshot_data))
        elif not _only_text_feedback:
            response_content.append(ImageContent(type="image", data=screenshot_data, mimeType="image/png"))

    return response_content


@mcp.tool()
def mcp_freecad_nodes_delete_node(
    ctx: Context,
    node_id_or_title: str
) -> list[TextContent | ImageContent]:
    """
    Deletes a specified node from the FreeCAD Nodes workbench graph.

    Args:
        node_id_or_title: The ID or title of the node to delete.

    Returns:
        A message indicating success or failure, and a screenshot of the Nodes workbench.
    """
    freecad = get_freecad_connection()

    script = f'''
from PySide import QtWidgets
import FreeCADGui
import traceback

print(f"--- MCP: Deleting Node ---")
node_id_or_title_val = "{node_id_or_title}"
print(f"Attempting to delete node: {{node_id_or_title_val}}")

fcn_sub_window_widget = None
scene = None
delete_message = "Node deletion status unknown."

app = QtWidgets.QApplication.instance()
if app:
    all_widgets = app.allWidgets()
    for w in all_widgets:
        if w.__class__.__name__ == 'FCNSubWindow' and w.isVisible():
            fcn_sub_window_widget = w
            break
    if fcn_sub_window_widget and hasattr(fcn_sub_window_widget, 'scene'):
        scene = fcn_sub_window_widget.scene

if not scene:
    delete_message = "Error: No active FCNSubWindow (Nodes editor) with a scene found."
    print(delete_message)
else:
    print(f"Found FCNSubWindow: {{fcn_sub_window_widget}} with scene: {{scene}}")

    node_to_delete = None
    node_title = ""
    node_id = -1

    for node_item in scene.nodes: # scene.nodes should be a list of node instances
        if str(node_item.id) == node_id_or_title_val or node_item.title == node_id_or_title_val:
            node_to_delete = node_item
            node_title = node_item.title
            node_id = node_item.id
            print(f"Found node to delete: {{node_title}} (ID: {{node_id}})")
            break

    if not node_to_delete:
        delete_message = f"Error: Node '{{node_id_or_title_val}}' not found for deletion."
        print(delete_message)
    else:
        try:
            # In Nodz, node.delete() handles removing from scene, deleting edges, etc.
            # It might also be scene.removeNode(node_to_delete) or node_to_delete.remove()
            # Let's assume node_to_delete.delete() is the method, as it's common in such libraries
            # for an object to manage its own destruction and cleanup.

            # Check if the node has a delete method
            if hasattr(node_to_delete, 'delete') and callable(node_to_delete.delete):
                node_to_delete.delete()
                # No explicit scene.removeItem(node_to_delete) usually needed if node.delete() is comprehensive
                scene.history.storeHistory(f"Deleted node '{{node_title}}' (ID: {{node_id}}) via MCP", setModified=True)
                delete_message = f"Successfully deleted node: '{{node_title}}' (ID: {{node_id}})."
            elif hasattr(scene, 'removeNode') and callable(scene.removeNode):
                scene.removeNode(node_to_delete) # Alternative if scene manages deletion
                scene.history.storeHistory(f"Deleted node '{{node_title}}' (ID: {{node_id}}) via MCP (scene.removeNode)", setModified=True)
                delete_message = f"Successfully deleted node '{{node_title}}' (ID: {{node_id}}) using scene.removeNode."
            else:
                delete_message = f"Error: Node '{{node_title}}' (ID: {{node_id}}) found, but no delete() method or scene.removeNode() method available."

            print(delete_message)
        except Exception as e_delete:
            delete_message = f"Error during deletion of node '{{node_title}}' (ID: {{node_id}}): {{str(e_delete)}}"
            print(delete_message)
            traceback.print_exc()

print(delete_message)
'''

    response_content = []
    try:
        execution_result = freecad.execute_code(script.format(node_id_or_title=node_id_or_title))
        raw_script_output = execution_result.get("message", "").strip()
        output_lines = raw_script_output.split('\\\\n')

        final_status_message = "Node deletion script executed. See log for details."
        if output_lines:
            for line in reversed(output_lines):
                if line.strip():
                    final_status_message = line.strip()
                    break

        if "Successfully deleted node" in raw_script_output:
            response_content.append(TextContent(type="text", text=final_status_message))
        elif "Error" in raw_script_output or "Warning" in raw_script_output:
            response_content.append(TextContent(type="text", text=f"Node deletion issues: '{{final_status_message}}'. Full Log:\\n{{raw_script_output}}"))
        else:
            response_content.append(TextContent(type="text", text=f"Node deletion attempt finished. Status: '{{final_status_message}}'. Full Log:\\n{{raw_script_output}}"))

    except Exception as e:
        logger.error(f"MCP tool mcp_freecad_nodes_delete_node failed: {{str(e)}}")
        response_content.append(TextContent(type="text", text=f"Failed to execute node deletion script: {{str(e)}}"))

    screenshot_data = freecad.get_nodes_workbench_screenshot()
    if screenshot_data:
        if "Nodes workbench interface is not available" in screenshot_data:
             response_content.append(TextContent(type="text", text=screenshot_data))
        elif not _only_text_feedback:
            response_content.append(ImageContent(type="image", data=screenshot_data, mimeType="image/png"))

    return response_content


@mcp.tool()
def insert_part_from_library(ctx: Context, relative_path: str) -> list[TextContent | ImageContent]:
    """Insert a part from the parts library addon.

    Args:
        relative_path: The relative path of the part to insert.

    Returns:
        A message indicating the success or failure of the part insertion and a screenshot of the object.
    """
    freecad = get_freecad_connection()
    try:
        res = freecad.insert_part_from_library(relative_path)
        screenshot = freecad.get_active_screenshot()
        
        if res["success"]:
            response = [
                TextContent(type="text", text=f"Part inserted from library: {res['message']}"),
            ]
            return add_screenshot_if_available(response, screenshot)
        else:
            response = [
                TextContent(type="text", text=f"Failed to insert part from library: {res['error']}"),
            ]
            return add_screenshot_if_available(response, screenshot)
    except Exception as e:
        logger.error(f"Failed to insert part from library: {str(e)}")
        return [
            TextContent(type="text", text=f"Failed to insert part from library: {str(e)}")
        ]


@mcp.tool()
def get_objects(ctx: Context, doc_name: str) -> list[dict[str, Any]]:
    """Get all objects in a document.
    You can use this tool to get the objects in a document to see what you can check or edit.

    Args:
        doc_name: The name of the document to get the objects from.

    Returns:
        A list of objects in the document and a screenshot of the document.
    """
    freecad = get_freecad_connection()
    try:
        screenshot = freecad.get_active_screenshot()
        response = [
            TextContent(type="text", text=json.dumps(freecad.get_objects(doc_name))),
        ]
        return add_screenshot_if_available(response, screenshot)
    except Exception as e:
        logger.error(f"Failed to get objects: {str(e)}")
        return [
            TextContent(type="text", text=f"Failed to get objects: {str(e)}")
        ]


@mcp.tool()
def get_object(ctx: Context, doc_name: str, obj_name: str) -> dict[str, Any]:
    """Get an object from a document.
    You can use this tool to get the properties of an object to see what you can check or edit.

    Args:
        doc_name: The name of the document to get the object from.
        obj_name: The name of the object to get.

    Returns:
        The object and a screenshot of the object.
    """
    freecad = get_freecad_connection()
    try:
        screenshot = freecad.get_active_screenshot()
        response = [
            TextContent(type="text", text=json.dumps(freecad.get_object(doc_name, obj_name))),
        ]
        return add_screenshot_if_available(response, screenshot)
    except Exception as e:
        logger.error(f"Failed to get object: {str(e)}")
        return [
            TextContent(type="text", text=f"Failed to get object: {str(e)}")
        ]


@mcp.tool()
def get_parts_list(ctx: Context) -> list[str]:
    """Get the list of parts in the parts library addon.
    """
    freecad = get_freecad_connection()
    parts = freecad.get_parts_list()
    if parts:
        return [
            TextContent(type="text", text=json.dumps(parts))
        ]
    else:
        return [
            TextContent(type="text", text=f"No parts found in the parts library. You must add parts_library addon.")
        ]


@mcp.prompt()
def asset_creation_strategy() -> str:
    return """
Asset Creation Strategy for FreeCAD MCP

When creating content in FreeCAD, always follow these steps:

0. Before starting any task, always use get_objects() to confirm the current state of the document.

1. Utilize the parts library:
   - Check available parts using get_parts_list().
   - If the required part exists in the library, use insert_part_from_library() to insert it into your document.

2. If the appropriate asset is not available in the parts library:
   - Create basic shapes (e.g., cubes, cylinders, spheres) using create_object().
   - Adjust and define detailed properties of the shapes as necessary using edit_object().

3. Always assign clear and descriptive names to objects when adding them to the document.

4. Explicitly set the position, scale, and rotation properties of created or inserted objects using edit_object() to ensure proper spatial relationships.

5. After editing an object, always verify that the set properties have been correctly applied by using get_object().

6. If detailed customization or specialized operations are necessary, use execute_code() to run custom Python scripts.

Only revert to basic creation methods in the following cases:
- When the required asset is not available in the parts library.
- When a basic shape is explicitly requested.
- When creating complex shapes requires custom scripting.
"""


@mcp.tool()
def mcp_freecad_nodes_link_nodes(
    ctx: Context,
    source_node_id_or_title: str,
    source_socket_index_or_name: str,
    target_node_id_or_title: str,
    target_socket_index_or_name: str
) -> list[TextContent | ImageContent]:
    """
    Connects an output socket of a source node to an input socket of a target node
    in the FreeCAD Nodes workbench.

    Args:
        source_node_id_or_title: The ID or title of the source node.
        source_socket_index_or_name: The index (as string, e.g., "0", "1") or name of the output socket on the source node.
        target_node_id_or_title: The ID or title of the target node.
        target_socket_index_or_name: The index (as string, e.g., "0", "1") or name of the input socket on the target node.

    Returns:
        A message indicating success or failure, and a screenshot of the Nodes workbench.
    """
    freecad = get_freecad_connection()

    script = f'''
from PySide import QtWidgets
import FreeCADGui
import traceback

print(f"--- MCP: Linking Nodes ---")
source_node_id_or_title_val = "{{source_node_id_or_title}}"
source_socket_val = "{{source_socket_index_or_name}}"
target_node_id_or_title_val = "{{target_node_id_or_title}}"
target_socket_val = "{{target_socket_index_or_name}}"

print(f"Attempting to link: {{source_node_id_or_title_val}}[{{source_socket_val}}] -> {{target_node_id_or_title_val}}[{{target_socket_val}}]")

fcn_sub_window_widget = None
scene = None
link_message = "Link creation status unknown."

try:
    source_socket_index = int(source_socket_val)
    source_socket_is_index = True
except ValueError:
    source_socket_is_index = False

try:
    target_socket_index = int(target_socket_val)
    target_socket_is_index = True
except ValueError:
    target_socket_is_index = False

app = QtWidgets.QApplication.instance()
if app:
    all_widgets = app.allWidgets()
    for w in all_widgets:
        if w.__class__.__name__ == 'FCNSubWindow' and w.isVisible():
            fcn_sub_window_widget = w
            break
    if fcn_sub_window_widget and hasattr(fcn_sub_window_widget, 'scene'):
        scene = fcn_sub_window_widget.scene

if not scene:
    link_message = "Error: No active FCNSubWindow (Nodes editor) with a scene found."
    print(link_message)
else:
    print(f"Found FCNSubWindow: {{fcn_sub_window_widget}} with scene: {{scene}}")

    source_node = None
    target_node = None

    for node_item in scene.nodes:
        if str(node_item.id) == source_node_id_or_title_val or node_item.title == source_node_id_or_title_val:
            source_node = node_item
            print(f"Found source node: {{source_node.title}} (ID: {{source_node.id}})")
        if str(node_item.id) == target_node_id_or_title_val or node_item.title == target_node_id_or_title_val:
            target_node = node_item
            print(f"Found target node: {{target_node.title}} (ID: {{target_node.id}})")
        if source_node and target_node:
            break

    if not source_node:
        link_message = f"Error: Source node '{{source_node_id_or_title_val}}' not found."
        print(link_message)
    elif not target_node:
        link_message = f"Error: Target node '{{target_node_id_or_title_val}}' not found."
        print(link_message)
    else:
        source_socket_obj = None
        if source_socket_is_index:
            if 0 <= source_socket_index < len(source_node.outputs):
                source_socket_obj = source_node.outputs[source_socket_index]
            else:
                link_message = f"Error: Source socket index {{source_socket_index}} out of range for node '{{source_node.title}}'."
                print(link_message)
        else:
            found_s = False
            for s_idx, s in enumerate(source_node.outputs):
                if (hasattr(s, 'name') and s.name == source_socket_val) or \
                   (hasattr(s, 'label') and callable(s.label) and s.label() == source_socket_val):
                    source_socket_obj = s
                    found_s = True
                    break
                # Check if name is actually an index given as string
                try:
                    if s_idx == int(source_socket_val):
                        source_socket_obj = s
                        found_s = True
                        break
                except ValueError:
                    pass # Not an integer string
            if not found_s:
                link_message = f"Error: Source socket '{{source_socket_val}}' not found on node '{{source_node.title}}'."
                print(link_message)

        target_socket_obj = None
        if target_socket_is_index:
            if 0 <= target_socket_index < len(target_node.inputs):
                target_socket_obj = target_node.inputs[target_socket_index]
            else:
                link_message = f"Error: Target socket index {{target_socket_index}} out of range for node '{{target_node.title}}'."
                print(link_message)
        else:
            found_t = False
            for t_idx, s in enumerate(target_node.inputs):
                if (hasattr(s, 'name') and s.name == target_socket_val) or \
                   (hasattr(s, 'label') and callable(s.label) and s.label() == target_socket_val):
                    target_socket_obj = s
                    found_t = True
                    break
                try:
                    if t_idx == int(target_socket_val):
                        target_socket_obj = s
                        found_t = True
                        break
                except ValueError:
                    pass
            if not found_t:
                link_message = f"Error: Target socket '{{target_socket_val}}' not found on node '{{target_node.title}}'."
                print(link_message)

        if source_socket_obj and target_socket_obj:
            s_sock_name = getattr(source_socket_obj, 'name', str(source_socket_obj))
            t_sock_name = getattr(target_socket_obj, 'name', str(target_socket_obj))
            print(f"Found source socket: {{s_sock_name}} on {{source_node.title}}")
            print(f"Found target socket: {{t_sock_name}} on {{target_node.title}}")
            try:
                can_connect = source_socket_obj.can_connect_to(target_socket_obj)
                print(f"Socket compatibility: {{s_sock_name}} can connect to {{t_sock_name}}: {{can_connect}}")

                if can_connect:
                    EdgeClass = None
                    try:
                        from nodz_main.edge import Edge as EdgeNodz
                        EdgeClass = EdgeNodz
                        print("Imported Edge from nodz_main.edge")
                    except ImportError:
                        print("Failed to import Edge from nodz_main.edge, trying from Nodes.nodz_main.edge")
                        try:
                            from Nodes.nodz_main.edge import Edge as EdgeNodesNodz
                            EdgeClass = EdgeNodesNodz
                            print("Imported Edge from Nodes.nodz_main.edge")
                        except ImportError:
                            link_message = "Error: Could not find or import the Edge class."
                            print(link_message)

                    if EdgeClass:
                        edge = EdgeClass(scene=scene, start_socket=source_socket_obj, end_socket=target_socket_obj)
                        # Check if connection was successful (Nodz updates socket.connected_sockets)
                        if target_socket_obj in source_socket_obj.connected_sockets and source_socket_obj in target_socket_obj.connected_sockets:
                            scene.history.storeHistory(f"Linked {{source_node.title}}.{{s_sock_name}} to {{target_node.title}}.{{t_sock_name}} via MCP", setModified=True)
                            link_message = f"Successfully linked {{source_node.title}}[{{s_sock_name}}] to {{target_node.title}}[{{t_sock_name}}]."
                        else:
                            # If Edge constructor doesn't auto-add or if connection failed for other reasons
                            link_message = f"Error: Edge object created but connection failed for {{source_node.title}} to {{target_node.title}}. Sockets might not be truly connected."
                        print(link_message)
                else:
                    link_message = f"Error: Sockets cannot be connected. {{source_node.title}}[{{s_sock_name}}] to {{target_node.title}}[{{t_sock_name}}]. Check compatibility or types."
                    print(link_message)

            except Exception as e_link:
                link_message = f"Error during link creation attempt: {{str(e_link)}}"
                print(link_message)
                traceback.print_exc()
        # elif not source_socket_obj and source_node: pass # Message already set
        # elif not target_socket_obj and target_node: pass # Message already set

print(link_message)
'''

    response_content = []
    try:
        # Parameters are already strings, direct formatting is fine.
        execution_result = freecad.execute_code(script.format(
            source_node_id_or_title=source_node_id_or_title,
            source_socket_index_or_name=source_socket_index_or_name,
            target_node_id_or_title=target_node_id_or_title,
            target_socket_index_or_name=target_socket_index_or_name
        ))
        raw_script_output = execution_result.get("message", "").strip()
        output_lines = raw_script_output.split('\\\\n')

        final_status_message = "Link operation script executed. See log for details."
        if output_lines:
            for line in reversed(output_lines):
                if line.strip():
                    final_status_message = line.strip()
                    break

        if "Successfully linked" in raw_script_output:
            response_content.append(TextContent(type="text", text=final_status_message))
        elif "Error" in raw_script_output or "Warning" in raw_script_output:
            response_content.append(TextContent(type="text", text=f"Link operation issues: '{{final_status_message}}'. Full Log:\\n{{raw_script_output}}"))
        else:
            response_content.append(TextContent(type="text", text=f"Link operation attempt finished. Status: '{{final_status_message}}'. Full Log:\\n{{raw_script_output}}"))

    except Exception as e:
        logger.error(f"MCP tool mcp_freecad_nodes_link_nodes failed: {{str(e)}}")
        response_content.append(TextContent(type="text", text=f"Failed to execute node link script: {{str(e)}}"))

    screenshot_data = freecad.get_nodes_workbench_screenshot()
    if screenshot_data:
        if "Nodes workbench interface is not available" in screenshot_data:
             response_content.append(TextContent(type="text", text=screenshot_data))
        elif not _only_text_feedback: # _only_text_feedback is a global
            response_content.append(ImageContent(type="image", data=screenshot_data, mimeType="image/png"))

    return response_content


def main():
    """Run the MCP server"""
    global _only_text_feedback
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--only-text-feedback", action="store_true", help="Only return text feedback")
    args = parser.parse_args()
    _only_text_feedback = args.only_text_feedback
    logger.info(f"Only text feedback: {_only_text_feedback}")
    mcp.run()