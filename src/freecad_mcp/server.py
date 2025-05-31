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