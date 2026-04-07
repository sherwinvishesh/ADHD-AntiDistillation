# config.py
# Central configuration for ITRO_Main experiment.
# All paths, model names, and hyperparameters live here.
# Nothing is hardcoded in other files — everything references this.

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────
# MODEL NAMES — HuggingFace identifiers
# ─────────────────────────────────────────────────────────────

TEACHER_MODEL = "Qwen/Qwen2.5-7B-Instruct"
STUDENT_MODEL = "Qwen/Qwen2.5-3B-Instruct"

# Local paths from .env — fall back to HF names for auto-download
# On Sol: set these to /scratch/sjathann/models/...
# On vast.ai: set these to /workspace/models/...
TEACHER_PATH = os.getenv("TEACHER_PATH", TEACHER_MODEL)
STUDENT_PATH = os.getenv("STUDENT_PATH", STUDENT_MODEL)

# ─────────────────────────────────────────────────────────────
# EXPERIMENT PARAMETERS
# ─────────────────────────────────────────────────────────────

# Number of questions used to generate all three datasets
N_SAMPLES = 2000

# Number of questions used for evaluation
EVAL_QUESTIONS = 500

# ─────────────────────────────────────────────────────────────
# DATASET PATHS
# ─────────────────────────────────────────────────────────────

DATASET_A_PATH = "datasets/dataset_A.json"   # clean (control)
DATASET_B_PATH = "datasets/dataset_B.json"   # ADHD-treated (experimental)
DATASET_C_PATH = "datasets/dataset_C.json"   # no-CoT (comparison)

# ─────────────────────────────────────────────────────────────
# MODEL OUTPUT PATHS
# ─────────────────────────────────────────────────────────────

STUDENT_BASELINE_PATH = "models/student_baseline"
STUDENT_ADHD_PATH     = "models/student_adhd"
STUDENT_NOCOT_PATH    = "models/student_nocot"

# ─────────────────────────────────────────────────────────────
# RESULTS PATH
# ─────────────────────────────────────────────────────────────

RESULTS_PATH = "results/"

# ─────────────────────────────────────────────────────────────
# TRAINING HYPERPARAMETERS
# These are IDENTICAL for all three student training runs.
# Only the data changes — this is what makes the comparison valid.
# ─────────────────────────────────────────────────────────────

EPOCHS        = 3
BATCH_SIZE    = 2        # per device
GRAD_ACCUM    = 8        # effective batch size = BATCH_SIZE × GRAD_ACCUM = 16
LEARNING_RATE = 2e-5
MAX_SEQ_LEN   = 512