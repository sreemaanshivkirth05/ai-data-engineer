import os
from datetime import datetime

def create_run(module):

    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")

    path = os.path.join("outputs", module, run_id)
    os.makedirs(path, exist_ok=True)

    return path