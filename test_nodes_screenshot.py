#!/usr/bin/env python3
"""
Test script for the Nodes workbench screenshot functionality.
This script can be run in FreeCAD's Python console to test the implementation.
"""

import sys
import os

# Add the addon path to sys.path if running from FreeCAD
try:
    import FreeCAD
    import FreeCADGui
    
    # Add the MCP addon to path
    addon_path = os.path.expanduser("~/.FreeCAD/Mod/FreeCADMCP")
    if addon_path not in sys.path:
        sys.path.insert(0, addon_path)
    
    from rpc_server.rpc_server import FreeCADRPC
    
    def test_nodes_screenshot():
        """Test the nodes workbench screenshot functionality."""
        print("Testing Nodes workbench screenshot...")
        
        rpc = FreeCADRPC()
        
        # Test the screenshot method
        result = rpc.get_nodes_workbench_screenshot()
        
        if result is None:
            print("❌ No screenshot captured - Nodes workbench may not be available")
        elif isinstance(result, str) and len(result) > 100:
            print(f"✅ Screenshot captured successfully! ({len(result)} characters of base64 data)")
        else:
            print(f"⚠️  Unexpected result: {result}")
        
        return result
    
    if __name__ == "__main__":
        test_nodes_screenshot()
        
except ImportError as e:
    print(f"This script should be run from within FreeCAD: {e}")
    print("Please copy and paste the test_nodes_screenshot() function into FreeCAD's Python console.") 