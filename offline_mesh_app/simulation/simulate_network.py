import subprocess
import time
import argparse

def launch_node(id):
    subprocess.Popen(["python", "simulation/virtual_node.py", str(id)])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=2)
    args = parser.parse_args()

    for i in range(args.nodes):
        launch_node(i)
        time.sleep(1)
