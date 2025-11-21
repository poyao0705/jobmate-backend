import sys
import os

# Add the project root to the python path
sys.path.append(os.path.abspath("/Users/poyaohuang/dev/jobmate/jobmate-backend"))

try:
    from jobmate_agent.agents.master import master_graph
    print("SUCCESS: Master graph compiled successfully!")
    
    # Optional: Print graph structure or nodes to be sure
    print("Graph nodes:", master_graph.nodes.keys())
    
except Exception as e:
    print(f"FAILURE: Could not compile master graph. Error: {e}")
    import traceback
    traceback.print_exc()
